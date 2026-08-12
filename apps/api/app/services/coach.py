"""Coach giải thích một câu học viên vừa làm sai.

Ba thứ đáng biết trước khi sửa:

- **Cache là bảng, và `prompt_version` nằm trong khoá.** Bỏ nó ra thì sửa prompt
  xong mọi học viên đã có bản cache vẫn nhận bản cũ vĩnh viễn.
- **Năm khẳng định tất định chạy trước giám khảo LLM.** Chúng bắt phần lớn lỗi
  thật, gần như miễn phí, và khẳng định thứ năm chỉ tồn tại được nhờ bộ nhãn là
  danh sách đóng.
- **Bỏ trống là một trạng thái có thật.** `selected_option_id = None` nghĩa là
  học viên không kịp làm, và nó đáng một lời giải riêng — không phải dữ liệu
  thiếu (ADR-001 §A4.5).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.coach import CoachExplanation
from app.models.labels import QuestionLabel
from app.models.practice import AttemptItem, Question, QuestionOption
from app.services.labels import LABELS
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.router import Tier

__all__ = [
    "FEATURE",
    "FIELDS",
    "CoachContext",
    "CoachUnavailable",
    "NothingToExplain",
    "Explained",
    "build_context",
    "check_output",
    "explain",
    "parse_output",
]

FEATURE = "coach_explain"


class NothingToExplain(RuntimeError):
    """Câu hỏi không mang đủ nội dung để giải thích được điều gì.

    Xảy ra thật: một câu Part 1 không in đề (đúng luật đề thi), phương án chỉ
    đọc bằng audio, và **chưa có lời thoại lẫn giải thích**. Model không thấy gì
    ngoài số part và chữ cái đáp án — nó nói thẳng điều đó trong câu trả lời
    ("phương án A chưa được cung cấp") rồi trượt cổng kiểm một cách thất thường.

    Chặn ở đầu vào chứ không để cổng kiểm bắt: cổng bắt được nghĩa là đã tốn hai
    lượt gọi model cho một câu hỏi không có câu trả lời, và người học nhận một
    thông báo nói sai nguyên nhân.
    """


class CoachUnavailable(RuntimeError):
    """Model không tạo được lời giải ĐẠT sau hai lần thử.

    Là lỗi riêng vì nơi gọi phải phân biệt nó với "nhà cung cấp hỏng": ở đây
    model trả lời bình thường, chỉ là câu trả lời không qua nổi cổng kiểm — và
    thông báo cho người dùng phải khác hẳn.
    """


FIELDS = ("chan_doan", "vi_sao_ban_chon_sai", "vi_sao_dap_an_dung", "quy_tac", "bay_tuong_tu")

# Khoảng độ dài mỗi trường. Cận dưới bắt câu trả lời rỗng nghĩa; cận trên bắt
# model lan man — cả hai đều là hỏng, và cả hai đều trông như văn bản hợp lệ.
MIN_LEN, MAX_LEN = 20, 900

# Ký tự có dấu tiếng Việt. Dùng để phân biệt "trả lời tiếng Việt" với "trả lời
# tiếng Anh trôi chảy", thứ mà một model bị lạc hay làm.
_VN = re.compile(r"[àáâãèéêìíòóôõùúýăđĩũơưạảấầẩậắằẳẵặẹẻếềểệỉịọỏốồổộớờởợụủứừửữựỳỵỷỹ]", re.I)


@dataclass(slots=True)
class CoachContext:
    question: Question
    chosen: QuestionOption | None
    correct: QuestionOption
    labels: dict[str, str]
    # Bao nhiêu học viên khác cũng chọn đúng phương án này. Đây là thứ một
    # chatbot bọc API không có, và nó có được vì `attempt_item.selected_option_id`
    # là khoá ngoại thật (ADR-001 §A4.1).
    distractor_share: float | None


def build_context(
    session: Session, question: Question, selected_option_id: object | None
) -> CoachContext:
    options = sorted(question.options, key=lambda o: o.label)
    correct = next(o for o in options if o.is_correct)
    chosen = next((o for o in options if o.id == selected_option_id), None)

    labels = {
        str(facet): str(code)
        for facet, code in session.execute(
            select(QuestionLabel.facet, QuestionLabel.code).where(
                QuestionLabel.question_id == question.id
            )
        )
    }

    share: float | None = None
    if chosen is not None:
        total = int(
            session.scalar(
                select(func.count(AttemptItem.id)).where(
                    AttemptItem.question_id == question.id,
                    AttemptItem.selected_option_id.is_not(None),
                )
            )
            or 0
        )
        if total:
            same = int(
                session.scalar(
                    select(func.count(AttemptItem.id)).where(
                        AttemptItem.question_id == question.id,
                        AttemptItem.selected_option_id == chosen.id,
                    )
                )
                or 0
            )
            share = round(same / total, 3)
    return CoachContext(question, chosen, correct, labels, share)


def describe(ctx: CoachContext) -> str:
    """Ngữ cảnh gửi cho model — dựng ở PHÍA MÁY CHỦ từ id, không nhận từ client.

    Nhận ngữ cảnh do client gửi lên là để người khác tự viết đề bài cho model.
    """
    q = ctx.question
    lines = [f"Part {q.part}."]
    if q.prompt_text:
        lines.append(f"Đề bài: {q.prompt_text}")
    else:
        lines.append("Đề bài: (không in ra — phần này chỉ đọc bằng audio)")
    if q.audio_script:
        lines.append(f"Lời thoại: {json.dumps(q.audio_script, ensure_ascii=False)}")
    for opt in sorted(q.options, key=lambda o: o.label):
        mark = " ← đáp án đúng" if opt.is_correct else ""
        pick = " ← học viên chọn" if ctx.chosen and opt.id == ctx.chosen.id else ""
        lines.append(f"  {opt.label}. {opt.content or '(chỉ đọc bằng audio)'}{mark}{pick}")
    if ctx.chosen is None:
        lines.append("Học viên BỎ TRỐNG câu này.")
    if q.explanation:
        lines.append(f"Giải thích sẵn có: {q.explanation}")
    for facet, code in sorted(ctx.labels.items()):
        label = LABELS.get(code)
        lines.append(f"Nhãn {facet}: {code}" + (f" ({label.label_vi})" if label else ""))
    if ctx.distractor_share is not None:
        lines.append(
            f"Thống kê: {ctx.distractor_share:.0%} học viên đã trả lời câu này cũng chọn "
            f"phương án {ctx.chosen.label if ctx.chosen else '?'}."
        )
    return "\n".join(lines)


def parse_output(text: str) -> tuple[dict[str, str] | None, str | None]:
    body = text.strip()
    if body.startswith("```"):
        body = body.split("```")[1].removeprefix("json").strip()
    try:
        data = json.loads(body)
    except ValueError:
        return None, "không phải JSON"
    if not isinstance(data, dict):
        return None, "JSON không phải object"
    missing = [f for f in FIELDS if not str(data.get(f, "")).strip()]
    if missing:
        return None, f"thiếu trường: {', '.join(missing)}"
    return {f: str(data[f]).strip() for f in FIELDS}, None


def check_output(body: dict[str, str], ctx: CoachContext) -> list[str]:
    """Năm khẳng định tất định. Trả về danh sách lỗi; rỗng nghĩa là đạt.

    Chạy mỗi lần, gần như miễn phí, và bắt phần lớn lỗi thật. Một lời giải trôi
    chảy nhưng **nêu sai chữ cái đáp án** là lỗi tệ nhất sản phẩm này mắc được,
    và nó bị bắt ở đây bằng một phép so sánh chuỗi.
    """
    problems: list[str] = []
    joined = " ".join(body.values())

    # 1 — có nêu đúng chữ cái đáp án đúng
    if not re.search(rf"\b{re.escape(ctx.correct.label)}\b", body["vi_sao_dap_an_dung"]):
        problems.append(f"không nêu chữ cái đáp án đúng ({ctx.correct.label})")

    # 2 — có nhắc phương án học viên đã chọn (khi có chọn)
    if ctx.chosen is not None and not re.search(
        rf"\b{re.escape(ctx.chosen.label)}\b", body["vi_sao_ban_chon_sai"]
    ):
        problems.append(f"không nhắc phương án đã chọn ({ctx.chosen.label})")

    # 3 — là tiếng Việt, không phải tiếng Anh trôi chảy
    if len(_VN.findall(joined)) < 10:
        problems.append("không phải tiếng Việt")

    # 4 — độ dài từng trường trong khoảng
    for field in FIELDS:
        if not MIN_LEN <= len(body[field]) <= MAX_LEN:
            problems.append(f"trường {field} dài {len(body[field])} ký tự")

    # 5 — không giảng về một điểm ngữ pháp KHÁC với nhãn của câu.
    #
    # Chỉ kiểm được vì bộ nhãn là DANH SÁCH ĐÓNG: nếu văn bản nhắc tên một nhãn
    # `GRAMMAR_*`, nó phải là nhãn của chính câu này. Đây là kiểu hỏng nguy hiểm
    # nhất — một lời giải trôi chảy, đúng ngữ pháp, và giảng sai điểm.
    own = set(ctx.labels.values())
    lowered = joined.lower()
    for code, label in LABELS.items():
        if not code.startswith("GRAMMAR_") or code in own:
            continue
        # CHỈ đối chiếu nhãn có tên ĐỦ ĐẶC TRƯNG.
        #
        # `GRAMMAR_TENSE` tên tiếng Việt là "Thì" — một trong những từ phổ biến
        # nhất tiếng Việt — nên đối chiếu nó sẽ gắn cờ mọi lời giải có chữ "thì",
        # kể cả lời giải hoàn toàn đúng. Một cảnh báo luôn bật là một cảnh báo
        # không ai đọc, nên phép kiểm này cố ý **hẹp mà đúng** thay vì rộng mà sai.
        #
        # Đổi lại nó chỉ bắt được nhóm nhãn nhiều chữ: mệnh đề quan hệ, cấu trúc
        # so sánh, phân từ. Đó cũng đúng là nhóm mà giảng nhầm lộ rõ nhất.
        if len(label.label_vi.split()) < 3:
            continue
        if label.label_vi.lower() in lowered:
            problems.append(f"giảng về {code} trong khi câu này là {sorted(own)}")
            break
    return problems


@dataclass(slots=True)
class Explained:
    explanation: CoachExplanation
    from_cache: bool


def explain(
    session: Session,
    gateway: Gateway,
    *,
    question: Question,
    selected_option_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    request_id: str | None = None,
) -> Explained:
    """Tra cache, gọi model nếu cần, kiểm bằng năm khẳng định, rồi ghi lại.

    **Không cache bản không đạt.** Năm khẳng định là một CỔNG chứ không phải chỉ
    tiêu phần trăm: một lời giải nêu sai chữ cái đáp án là một bài học sai dạy
    cho mọi học viên gặp câu đó về sau, và cache nó lại là biến một lần hỏng
    thành vĩnh viễn. Thà không có gì còn hơn.

    Thử lại **một** lần, có nói rõ sai ở đâu. Gửi lại y nguyên yêu cầu cũ thì
    không có lý do gì để lần hai khác lần một.
    """
    if not _has_content(question):
        raise NothingToExplain("Câu này chưa có lời thoại hay giải thích để dựa vào.")

    prompt = load("coach_explain")
    route = _route_for(session, gateway)
    # `schema` khác None là thứ bật `format: json` ở adapter Ollama. Thiếu nó,
    # model trả JSON lỏng lẻo hơn và cổng kiểm chặn — một khác biệt vô hình giữa
    # bản gọi tay lúc gỡ lỗi và đường chạy thật, và nó đã tốn một vòng chẩn đoán.
    #
    # Ràng buộc phía nhà cung cấp KHÔNG thay cho `check_output`: JSON hợp lệ vẫn
    # có thể nêu sai chữ cái đáp án. Nó chỉ bớt một loại hỏng, không bớt loại nào
    # quan trọng.
    schema: dict[str, object] = {"type": "object", "required": list(FIELDS)}

    cached = session.scalars(
        select(CoachExplanation).where(
            CoachExplanation.question_id == question.id,
            CoachExplanation.selected_option_id == selected_option_id,
            CoachExplanation.prompt_version == prompt.version,
            CoachExplanation.status != "rejected",
        )
    ).first()
    if cached is not None:
        gateway.note_cache_hit(
            feature=FEATURE,
            provider=route[0],
            model=route[1],
            user_id=user_id,
            prompt_version=prompt.version,
            request_id=request_id,
        )
        return Explained(cached, from_cache=True)

    ctx = build_context(session, question, selected_option_id)
    described = describe(ctx)
    correction = ""
    problems: list[str] = []

    for _attempt in (1, 2):
        result = gateway.run(
            LLMRequest(
                # `render()` chứ không phải `.text`: tệp prompt thoát dấu ngoặc bằng
                # `{{` cho `str.format`, nên bản thô cho model nhìn thấy ngoặc kép đôi
                # trong mẫu JSON — một hướng dẫn sai mà không gì báo lỗi.
                system=prompt.render(),
                user=described + correction,
                max_tokens=900,
                schema=schema,
            ),
            feature=FEATURE,
            tier=Tier.STRONG,
            user_id=user_id,
            prompt_version=prompt.version,
            request_id=request_id,
        )
        body, problem = parse_output(result.text)
        if body is None:
            problems = [problem or "không đọc được"]
        else:
            problems = check_output(body, ctx)
            if not problems:
                row = CoachExplanation(
                    question_id=question.id,
                    selected_option_id=selected_option_id,
                    prompt_version=prompt.version,
                    body=body,
                    status="draft",
                )
                session.add(row)
                session.commit()
                return Explained(row, from_cache=False)
        correction = f"\n\nLần trước bạn trả lời không đạt ({'; '.join(problems)}). Sửa lại."

    raise CoachUnavailable("; ".join(problems))


def _has_content(question: Question) -> bool:
    """Có gì để giải thích không.

    Part 1 và 2 không in đề và không in phương án — đó là luật đề thi, không
    phải dữ liệu thiếu. Nhưng khi CẢ lời thoại lẫn giải thích cũng trống thì
    không còn gì cả, và đó là lỗ hổng nội dung.
    """
    if question.prompt_text or question.audio_script or question.explanation:
        return True
    return any(option.content for option in question.options)


def _route_for(session: Session, gateway: Gateway) -> tuple[str, str]:
    """Nhà cung cấp/model đang dùng — để hàng cache-hit ghi đúng tên.

    Ghi "fake" hay để trống ở đây sẽ làm bảng "chi phí theo model" đếm lượt
    phục vụ từ cache vào nhầm model, và tỉ lệ cache trúng theo model thành vô nghĩa.
    """
    override = gateway.resolve_feature(FEATURE) if gateway.resolve_feature else None
    if override is not None:
        return override[0], override[1]
    return gateway.routes[Tier.STRONG]
