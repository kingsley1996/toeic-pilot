"""Viết `question.explanation` cho câu hỏi đã có mà còn thiếu nó.

Vì sao cần: dây chuyền sinh đề nay phủ 100% giải thích (`tp-test-09`: 200/200),
nhưng ba đề cũ đang chạy trên production thì mỗi đề chỉ 30/200. Học viên làm sai
một câu Part 7 rồi không được nói gì cả — vòng học đứt ở đúng chỗ nó phải đóng,
và nó đứt trên phần lớn nội dung đang phục vụ. Đây là công cụ vá 510 câu ấy.

Chạy NGOÀI LUỒNG phục vụ, y như `enrich_skills` và `backfill_audio`, và hàng đợi
cũng lại là một **truy vấn** — "câu nào chưa có giải thích". Không bảng job,
không trạng thái thử lại; chạy lại chỉ tìm thấy ít việc hơn.

**Prompt nằm ở sổ RUNTIME, không ở sổ sinh đề, và đó là một lựa chọn.**
`PROMPT-SYSTEM.md` §0 nói sổ sinh đề không cần ghi `prompt_version` *vì đầu ra
của nó được người duyệt trước khi vào database*. Điều đó không đúng ở đây: 510
lượt gọi ghi thẳng vào `question.explanation` rồi đi thẳng ra màn hình người học,
không ai đọc từng câu. Đó là hồ sơ rủi ro của sổ runtime, nên nó dùng sổ runtime
— và nhờ vậy một câu giải thích tệ trong database truy ngược được về đúng bản
prompt đã sinh ra nó. `enrich_skills` chọn y như thế và vì y một lý do.

**Part 1 làm được, và nó cần `--test`.** Câu Part 1 hỏi về một bức ảnh mà model
không nhìn thấy, nhưng bản mô tả cảnh dùng để dựng bức ảnh ấy vẫn còn ở
`content/generated/<slug>/photos/`. Có nó thì lời giải bám vào dẫn chứng thật;
không có thì câu đó bị **bỏ qua**, vì viết tiếp là bịa.

    uv run python -m app.content.backfill_explanations --test tp-form-06 --dry-run
    uv run python -m app.content.backfill_explanations --test tp-form-06 --limit 5
    uv run python -m app.content.backfill_explanations --test tp-form-06
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.content.exam_cli.paths import blueprint_path, workdir_for
from app.core.database import SessionLocal
from app.models import Question
from app.models.practice import PracticeTest, PracticeTestQuestion
from app.services.llm.base import LLMError, LLMQuotaExhausted, LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.retry import with_backoff as _with_backoff
from app.services.llm.router import Tier

FEATURE = "backfill_explanation"

SEPARATOR = " | "

# Part 1 hỏi về một BỨC ẢNH, và model chỉ nhận được chữ — nên nó cần bản mô tả
# cảnh mà bước lập kế hoạch đã dựng lúc sinh đề, nằm ở
# `content/generated/<slug>/photos/<slot>.txt`.
#
# Không lấy bản ấy thì model phải suy ngược từ phương án đúng rồi mô tả một bức
# ảnh nó chưa từng thấy — bịa dẫn chứng, mà một câu bịa đọc trôi chảy hơn hẳn
# một chỗ trống nên không ai phát hiện. `alt_text` KHÔNG thay thế được: ảnh Part
# 1 cố ý không có (ADR-004), vì mô tả bức ảnh là cho luôn đáp án.
#
# Nên luật ở đây là: có bản mô tả thì làm, không có thì BỎ QUA CÂU ĐÓ và nói ra.
# Từ chối theo từng câu, không từ chối cả part.
PHOTO_DIR = "photos"

# Rộng tay, vì phần lớn hạn mức này là chỗ cho model SUY LUẬN chứ không phải cho
# câu trả lời — bản thân lời giải chỉ vài trăm token.
#
# Model qwen3.8 và GLM đều suy nghĩ trước khi viết, và phần nghĩ ăn vào cùng một
# hạn mức: đo thật ở `openai_compatible.py` là 2 600 token đầu ra cho 10 862 ký
# tự suy nghĩ. Đặt chật thì lượt gọi chết với "hết hạn mức đầu ra khi đang suy
# luận" — mà lỗi ấy đội lốt "model trả lời sai định dạng", nên người sửa sẽ đi
# chỉnh prompt trong khi chỗ cần chỉnh là con số này. 900 đã chết đúng như vậy
# trên Part 7 ngày 2026-09-04.
#
# Rộng tay không tốn thêm tiền: token đầu ra tính theo lượng THẬT SỰ dùng, không
# theo trần.
MAX_TOKENS = 3000


@dataclass(slots=True)
class Outcome:
    text: str | None
    reason: str
    attempts: int


def scene_for(test_slug: str, number: int) -> str | None:
    """Bản mô tả bức ảnh Part 1, đọc từ thư mục làm việc của đề.

    Tra `blueprint.json` để lấy id của slot thay vì tự dựng tên `p1-{number:02d}`:
    quy ước đặt tên là chuyện của đường sinh đề, và đoán nó ở đây nghĩa là hai
    nơi phải cùng đổi khi nó đổi — mà nơi này sẽ không ai nhớ.
    """
    try:
        blueprint = json.loads(blueprint_path(test_slug).read_text())
    except (OSError, ValueError):
        return None
    for part in blueprint.get("parts", []):
        if part.get("part") != 1:
            continue
        for slot in part.get("slots", []):
            if slot.get("number") == number:
                path = workdir_for(test_slug) / PHOTO_DIR / f"{slot.get('id')}.txt"
                try:
                    return path.read_text().strip() or None
                except OSError:
                    return None
    return None


def describe(question: Question, scene: str | None = None) -> str:
    """Mô tả câu hỏi cho model.

    Gần giống `enrich_skills._describe` nhưng KHÁC ở một chỗ quyết định, nên nó
    không dùng chung: bản kia cố tình giấu lời đọc của phương án Part 1/2 và chỉ
    nói "đáp án đúng là X", vì gắn nhãn không cần biết từng phương án nói gì.
    Giải thích thì cần — nó phải trích lại lời của từng phương án. Dùng lại bản
    kia sẽ cho ra những đoạn `(B) phương án này không phù hợp` rỗng tuếch, đúng
    thứ mà hợp đồng định dạng sinh ra để chặn.
    """
    lines = [f"Part {question.part}."]

    # Bức ảnh là toàn bộ ngữ liệu của Part 1, nên nó đứng trước mọi thứ khác.
    #
    # Gọi thẳng nó là "bạn nhìn thấy": model có xu hướng TRÍCH lại đoạn này như
    # một tài liệu — "ảnh ghi 'No sink is visible'" — trong khi học viên chỉ thấy
    # một bức ảnh và câu tiếng Anh ấy không tồn tại ở đâu họ với tới được.
    if scene:
        lines.append(f"Bạn nhìn thấy bức ảnh này: {scene}")

    # Ngữ liệu dùng chung nằm ở `question_set` (ADR-001 §A4.2, §A4.3): part 3, 4
    # treo lời thoại ở đó, part 6, 7 treo đoạn văn. Thiếu nó thì "người viết ngụ
    # ý gì" là câu không trả lời được, và model chỉ còn cách bịa một câu trích.
    group = question.question_set
    if group is not None:
        if group.title:
            lines.append(f"Nhóm: {group.title}")
        if group.audio_script:
            lines.append(f"Lời thoại: {json.dumps(group.audio_script, ensure_ascii=False)}")
        for index, passage in enumerate((group.passage, group.passage_2, group.passage_3), 1):
            if passage:
                lines.append(f"Đoạn văn {index}: {passage}")

    if question.prompt_text:
        lines.append(f"Đề bài: {question.prompt_text}")
    else:
        lines.append("Đề bài: (không in ra — chỉ đọc bằng audio)")
    if question.audio_script:
        lines.append(f"Lời thoại của câu: {json.dumps(question.audio_script, ensure_ascii=False)}")

    lines.append("Các phương án:")
    for opt in sorted(question.options, key=lambda o: o.label):
        # `content` NULL ở Part 1 và 2 vì đề thi không in gì; lời thật nằm ở
        # `spoken_text`. Bỏ qua nhánh này là bỏ trắng đúng hai part đó.
        said = opt.content or opt.spoken_text or "(không có nội dung)"
        mark = "  ← ĐÁP ÁN ĐÚNG" if opt.is_correct else ""
        lines.append(f"  ({opt.label}) {said}{mark}")
    return "\n".join(lines)


def check_shape(text: str, labels: list[str]) -> str | None:
    """Kiểm dạng trả về. Trả `None` là đạt, hoặc một câu nói rõ chỗ sai.

    Từ chối chứ không sửa. Một câu giải thích sai dạng thì máy vá được phần dấu
    ngoặc nhưng không vá được thứ hỏng thật — đoạn `(C)` mô tả nhầm phương án
    `(D)` vẫn là một dòng trôi chảy, đọc xuôi, và sai. Nên chỗ này chỉ đếm và
    nói ra; sửa là việc của lượt gọi lại.

    Câu nói ra sẽ được gửi ngược cho model ở lần thử thứ hai, nên nó phải nói
    được LỆCH Ở ĐÂU chứ không chỉ "sai dạng".
    """
    line = text.strip()
    if not line:
        return "trả về rỗng"
    if "\n" in line:
        return "có xuống dòng; phải nằm trọn trên một dòng"

    parts = [p.strip() for p in line.split(SEPARATOR)]
    expected = len(labels) + 1
    if len(parts) != expected:
        return (
            f"có {len(parts)} đoạn, cần đúng {expected} "
            f"(một đoạn căn cứ + {len(labels)} đoạn cho {len(labels)} phương án)"
        )

    evidence, clauses = parts[0], parts[1:]
    # Đoạn căn cứ không được mang chữ cái: hợp đồng ở `part7_system.md` đặt luật
    # này vì các phương án bị xáo lại sau khi lời giải được viết, nên một chữ cái
    # nằm ngoài đoạn của chính nó sẽ trỏ sang phương án khác.
    for label in labels:
        if f"({label})" in evidence:
            return f"đoạn căn cứ nhắc tới ({label}); đoạn đầu không được nêu chữ cái nào"

    for label, clause in zip(labels, clauses, strict=True):
        if not clause.startswith(f"({label})"):
            got = clause[:24]
            return f"đoạn cho ({label}) phải mở đầu bằng '({label})', đang là {got!r}"
    return None


def explain(gateway: Gateway, question: Question, tier: Tier, scene: str | None = None) -> Outcome:
    """Một lượt viết giải thích, tối đa hai lần gọi.

    Vòng thử lại nằm ở đây chứ không trong gateway, nên **mỗi lượt gọi HTTP là
    một hàng trong sổ cái** và câu hỏi "510 câu tốn bao nhiêu" cộng được. Cùng lý
    lẽ đã ghi ở đầu `enrich_skills`.
    """
    prompt = load("backfill_explanation")
    labels = [o.label for o in sorted(question.options, key=lambda o: o.label)]
    described = describe(question, scene)
    correction = ""

    for attempt in (1, 2):
        try:
            result = _with_backoff(
                lambda: gateway.run(
                    LLMRequest(
                        system=prompt.text,
                        user=described + correction,
                        max_tokens=MAX_TOKENS,
                    ),
                    feature=FEATURE,
                    tier=tier,
                    prompt_version=prompt.version,
                )
            )
        except LLMQuotaExhausted:
            raise
        except LLMError as exc:
            return Outcome(None, f"gọi hỏng: {exc}", attempt)

        text = result.text.strip()
        problem = check_shape(text, labels)
        if problem is None:
            return Outcome(text, "", attempt)
        correction = f"\n\nLần trước bạn trả lời sai dạng: {problem}. Viết lại đúng một dòng."
    return Outcome(None, f"sai dạng sau 2 lần: {problem}", 2)


def pending(
    session: Session, test_slug: str | None, part: int | None, limit: int | None
) -> list[Question]:
    """Hàng đợi là một TRUY VẤN: câu nào chưa có giải thích.

    Chuỗi rỗng tính là chưa có. Cột `explanation` nullable, nhưng một đường ghi
    nào đó đặt `''` thì hàng ấy sẽ không bao giờ được nhặt lên nếu chỉ hỏi
    `IS NULL` — và nó cũng không hiện gì cho học viên, vì giao diện kiểm
    `question.explanation &&`.
    """
    stmt = (
        select(Question)
        .options(selectinload(Question.options), joinedload(Question.question_set))
        .where((Question.explanation.is_(None)) | (Question.explanation == ""))
    )
    if test_slug is not None:
        stmt = (
            stmt.join(PracticeTestQuestion, PracticeTestQuestion.question_id == Question.id)
            .join(PracticeTest, PracticeTest.id == PracticeTestQuestion.test_id)
            .where(PracticeTest.slug == test_slug)
            # Theo đúng thứ tự học viên gặp, nên một lần chạy `--limit` cắt ngang
            # để lại phần đã xong ở đầu đề chứ không rải rác khắp nơi.
            .order_by(PracticeTestQuestion.number)
        )
    else:
        stmt = stmt.order_by(Question.part, Question.id)
    if part is not None:
        stmt = stmt.where(Question.part == part)

    rows = list(session.scalars(stmt).unique())
    return rows[:limit] if limit is not None else rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Viết giải thích cho câu hỏi chưa có")
    parser.add_argument("--test", default=None, help="slug của đề, ví dụ tp-form-06")
    parser.add_argument("--part", type=int, default=None, choices=range(1, 8))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="gọi model nhưng KHÔNG ghi")
    parser.add_argument("--tier", choices=["t1", "t2"], default="t2")
    parser.add_argument(
        "--model",
        default=None,
        help="provider/model ghi đè cả hai tầng, vd `bai/glm-5.3-flash` — chính model đã "
        "sinh tp-test-09 với độ phủ giải thích 100%%",
    )
    args = parser.parse_args(argv)

    # Dùng lại bộ dựng gateway của đường sinh đề chứ không viết bản thứ hai: nó
    # đã nối sẵn `resolve_feature`, và quên nối thứ đó thì màn `/admin/ai/providers`
    # lưu được, hiện ra được, và không ảnh hưởng gì tới thứ thật sự chạy.
    from app.content.exam_cli.paths import _gateway

    session = SessionLocal()
    try:
        try:
            gateway = _gateway(args.model)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        tier = Tier(args.tier)
        questions = pending(session, args.test, args.part, args.limit)
        where = f" trong {args.test}" if args.test else ""
        print(f"{len(questions)} câu{where} chưa có giải thích.\n")

        # Số thứ tự trong đề, cần để tra bản mô tả ảnh của Part 1. Chỉ có khi
        # biết đề nào — một câu hỏi nằm được trong nhiều đề, nên `--test` là
        # điều kiện để Part 1 làm được.
        numbers: dict[uuid.UUID, int] = {}
        if args.test is not None:
            numbers = {
                qid: number
                for qid, number in session.execute(
                    select(PracticeTestQuestion.question_id, PracticeTestQuestion.number)
                    .join(PracticeTest, PracticeTest.id == PracticeTestQuestion.test_id)
                    .where(PracticeTest.slug == args.test)
                ).all()
            }

        done = failures = skipped = 0
        try:
            for question in questions:
                scene = None
                if question.part == 1:
                    number = numbers.get(question.id)
                    if args.test is not None and number is not None:
                        scene = scene_for(args.test, number)
                    if scene is None:
                        # Không có bản mô tả thì không có dẫn chứng, và viết
                        # tiếp nghĩa là bịa. Bỏ qua câu đó và nói ra.
                        skipped += 1
                        print(f"  part 1  –  bỏ qua: không thấy mô tả cảnh trong {PHOTO_DIR}/")
                        continue
                outcome = explain(gateway, question, tier, scene)
                if outcome.text is None:
                    failures += 1
                    print(f"  part {question.part}  ✗  {outcome.reason}")
                    continue
                done += 1
                mark = " (thử lại)" if outcome.attempts > 1 else ""
                print(f"  part {question.part}  ✓{mark}  {outcome.text[:96]}…")
                if not args.dry_run:
                    question.explanation = outcome.text
                    # Ghi từng câu một. Gom lại cuối run thì một lần ngắt giữa
                    # chừng — hết ngân sách, mất mạng, Ctrl-C — vứt sạch mọi
                    # lượt gọi đã trả tiền.
                    session.commit()
        except LLMQuotaExhausted as exc:
            print(f"\nHết ngân sách token, dừng: {exc}", file=sys.stderr)

        note = f", bỏ qua {skipped}" if skipped else ""
        print(f"\nxong {done}, hỏng {failures}{note}.")
        if args.dry_run:
            print("(--dry-run: không ghi gì)")
        return 1 if failures and not done else 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
