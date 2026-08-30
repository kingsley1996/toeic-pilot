"""Trợ lý AI của trang web — knowledge base + công cụ tra dữ liệu cá nhân.

Nguồn ngữ cảnh, theo thứ tự ghép vào prompt:

1. **SITE_GUIDE** — khối tĩnh ngắn, luôn có mặt: bản đồ các khu của trang. Đủ
   cho câu "Trang này có gì".
2. **Knowledge base** (`knowledge_chunk`, đồng bộ từ `content/kb/*.md`) — tra
   bằng `search_knowledge`, chỉ khi câu hỏi khớp. Đây là nguồn làm câu trả lời
   CHÍNH XÁC: mỗi chunk là một mục tài liệu được review như mã, và model được
   bảo trích dẫn `[ref]` khi dựa vào nó. Một corpus do người viết là chỗ RAG
   đáng tin ngay từ mức nhỏ (xem `services/knowledge.py` về trần của phép tra
   lexical và đường nâng cấp vector).
3. **CÔNG CỤ** — dữ liệu cá nhân KHÔNG còn được tính sẵn trong ngữ cảnh nữa.
   Câu hỏi không liên quan tới bản thân thì không tiêu token vào một đống số;
   câu hỏi có liên quan thì model gọi tool lấy SỐ THẬT lúc đó. Bốn công cụ chỉ
   nhận `user` từ request — không có tham số user_id nào, nên không tồn tại
   đường đọc dữ liệu của người khác.

Vòng tool giới hạn 3 lượt gọi model cho mỗi câu hỏi: model muốn gọi công cụ thì
thực thi và gọi lại, hết 3 lượt vẫn chưa trả lời được thì hỏng TOÀN LƯỢT — một
câu trả lời dựa trên công cụ chưa chạy xong là câu trả lời bịa, tệ hơn là lỗi.

Không dùng `Retriever`/`Anchor` của coach: điểm neo của coach là một lượt làm
bài, của trợ lý là "không có" — và mỗi bên có một nguồn ngữ cảnh khác nhau.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.chat import CoachConversation, CoachMessage
from app.models.knowledge import KnowledgeChunk
from app.models.practice import Attempt
from app.models.progression import UserBadge
from app.models.ruby import RubyEvent
from app.models.user import User
from app.services import progression, ruby
from app.services.chat import MAX_QUESTION_CHARS, history, save_turn
from app.services.knowledge import search_knowledge
from app.services.llm.base import LLMRequest, LLMResult, ToolCall, Usage
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.router import Tier
from app.services.profile import ensure_profile
from app.services.profile_stats import gather_stats

logger = logging.getLogger(__name__)

__all__ = [
    "FEATURE",
    "MAX_ASSISTANT_TOKENS",
    "MAX_QUESTION_CHARS",
    "TOOL_SCHEMAS",
    "Answered",
    "ask",
]

FEATURE = "assistant_chat"

# Trần đầu ra của MỖI lượt gọi trong vòng tool. GLM-5.3-Flash LUÔN suy nghĩ
# (không tắt được) và phần thinking tính vào trần này: đo thật, trần 900 bị cắt
# giữa câu (finish_reason=length), một câu trả lời đầy đủ chỉ cần ~600-1500.
# Trần cao không tốn thêm — tiền tính theo token thật sự sinh ra.
MAX_ASSISTANT_TOKENS = 3000

# Bản đồ các khu — phần tĩnh, luôn có mặt. Ngắn trên chủ ý: phần chi tiết là
# việc của knowledge base, không phải của khối này.
SITE_GUIDE = """\
TOEIC Pilot là nền tảng luyện thi TOEIC. Các khu: `/dashboard` (việc hôm nay,
streak, XP, level), `/learn/vocabulary` (học từ theo chủ đề), `/learn/review`
và `/learn/typing` (ôn tập SM-2 theo từ đến hạn), `/learn/dictation` (nghe
chép theo cây chủ đề), `/learn/tests` (luyện đề, nộp bài mới có điểm),
`/learn/attempts` (lịch sử lượt làm), `/profile` (hồ sơ, thống kê, huy hiệu,
ví ruby), góc thú cưng Petland. Quy tắc chung: nội dung học viên thấy đều đã
xuất bản; XP và ruby là sổ cái ghi theo sự kiện."""


@dataclass(slots=True)
class Answered:
    conversation: CoachConversation
    question: CoachMessage
    answer: CoachMessage


# --- Công cụ ---------------------------------------------------------------


def _tool_summary(db: Session, user: User, args: dict[str, Any]) -> str:
    """Tổng quan tiến độ — số thật suy ra từ đúng nguồn giao diện đang dùng."""
    profile = ensure_profile(db, user)
    stats = gather_stats(db, user.id, profile.timezone)
    progress = progression.level_of(db, user.id)
    attempts = db.scalar(
        select(func.count(Attempt.id)).where(
            Attempt.user_id == user.id, Attempt.submitted_at.is_not(None)
        )
    )
    return json.dumps(
        {
            "level": progress.level,
            "xp_tong": progress.xp_total,
            "xp_con_lai_len_cap": progress.xp_for_next,
            "streak_hien_tai": stats.current_streak,
            "streak_dai_nhat": stats.longest_streak,
            "tu_da_thuoc": stats.vocabulary_mastered,
            "tu_tong": stats.vocabulary_total,
            "tu_den_han_on": stats.vocabulary_due,
            "dictation_cau_hoan_thanh": stats.dictation_completed,
            "dictation_luot_lam": stats.dictation_attempts,
            "luot_thi_da_nop": attempts or 0,
        },
        ensure_ascii=False,
    )


def _tool_recent_attempts(db: Session, user: User, args: dict[str, Any]) -> str:
    limit = max(1, min(int(args.get("limit", 3)), 10))
    rows = db.scalars(
        select(Attempt)
        .where(Attempt.user_id == user.id, Attempt.submitted_at.is_not(None))
        .order_by(Attempt.submitted_at.desc())
        .limit(limit)
    )
    return json.dumps(
        [
            {
                "ngay_nop": f"{a.submitted_at:%d/%m/%Y}",
                "listening": a.listening_scaled,
                "reading": a.reading_scaled,
                "total": a.total_scaled,
                "so_cau_phan": len(a.items) if a.items else None,
            }
            for a in rows
        ],
        ensure_ascii=False,
    )


def _tool_ruby(db: Session, user: User, args: dict[str, Any]) -> str:
    balance = ruby.balance(db, user.id)
    events = db.scalars(
        select(RubyEvent)
        .where(RubyEvent.user_id == user.id)
        .order_by(RubyEvent.created_at.desc())
        .limit(5)
    ).all()
    return json.dumps(
        {
            "so_du": balance,
            "su_kien_gan_day": [{"so_luong": e.amount, "nguon": e.source_type} for e in events],
        },
        ensure_ascii=False,
    )


def _tool_badges(db: Session, user: User, args: dict[str, Any]) -> str:
    rows = db.scalars(select(UserBadge).where(UserBadge.user_id == user.id)).all()
    return json.dumps(
        {"so_huy_hieu_da_dat": len(rows), "danh_sach": sorted(r.code for r in rows)},
        ensure_ascii=False,
    )


# Danh sách công cụ là HÌNH (schema cho model) + BẢN ĐỒ thực thi — tách hai
# thứ để schema đọc được từ prompt còn thực thi kiểm được độc lập.
TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "trang_thai_hoc_tap",
            "description": "Tổng quan tiến độ của người học: level, XP, streak, "
            "từ vựng đã thuộc/đến hạn, nghe chép, số lượt thi đã nộp.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "luot_thi_gan_day",
            "description": "Danh sách các lượt thi ĐÃ NỘP gần nhất với điểm "
            "Listening/Reading/Total. Chỉ dùng khi người hỏi về kết quả thi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Số lượt muốn xem (1-10)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vi_ruby",
            "description": "Số dư ruby và các sự kiện nhận/tiêu gần đây của người học.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "huy_hieu",
            "description": "Danh sách huy hiệu người học đã đạt được.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

_TOOL_IMPLS = {
    "trang_thai_hoc_tap": _tool_summary,
    "luot_thi_gan_day": _tool_recent_attempts,
    "vi_ruby": _tool_ruby,
    "huy_hieu": _tool_badges,
}

MAX_TOOL_ROUNDS = 3


def _execute(db: Session, user: User, call: ToolCall) -> str:
    impl = _TOOL_IMPLS.get(call.name)
    if impl is None:
        return json.dumps({"error": f"không có công cụ {call.name!r}"}, ensure_ascii=False)
    try:
        args = json.loads(call.arguments) if call.arguments.strip() else {}
    except json.JSONDecodeError:
        # JSON hỏng là DỮ LIỆU trả về cho model, không phải exception: nó tự
        # sửa được ở lượt gọi kế, còn ném lỗi là chết cả lượt hỏi vô cớ.
        return json.dumps(
            {"error": "tham số không phải JSON hợp lệ, hãy gửi lại"}, ensure_ascii=False
        )
    try:
        return impl(db, user, args if isinstance(args, dict) else {})
    except Exception as exc:  # noqa: BLE001
        # Cùng luật với JSON hỏng: một đối số sai KIỂU (vd `limit: "abc"`) là
        # dữ liệu cho model tự sửa, không phải một lỗi 500 đâm chết cả lượt.
        logger.exception("assistant_tool_failed", extra={"tool": call.name})
        return json.dumps({"error": str(exc)[:500]}, ensure_ascii=False)


def _knowledge_section(db: Session, query: str) -> str:
    chunks: list[tuple[float, KnowledgeChunk]] = search_knowledge(db, query)
    if not chunks:
        return "(không có mục tài liệu nào khớp câu hỏi)"
    blocks = [f"[{chunk.ref}] {chunk.title}\n{chunk.content}" for _, chunk in chunks]
    return "\n\n".join(blocks)


def ask(
    session: Session,
    gateway: Gateway,
    *,
    user: User,
    question: str,
    request_id: str | None = None,
) -> Answered:
    text = question.strip()
    if not text:
        raise ValueError("câu hỏi rỗng")
    text = text[:MAX_QUESTION_CHARS]

    conversation = _find(session, user)

    prompt = load("assistant_chat")
    context = f"{SITE_GUIDE}\n\nTÀI LIỆU TRANG:\n{_knowledge_section(session, text)}"
    system = prompt.render(context=context)

    # Lịch sử đi vào các tin nhắn user/assistant, KHÔNG bao giờ vào `system` —
    # cùng ranh giới an toàn đã ghi ở `chat.ask`, chỉ đổi hình: giao thức tool
    # đòi hội thoại dạng danh sách, và luật vẫn giữ được vì phần system do ta
    # viết toàn phần trước khi gửi.
    past = (
        [{"role": m.role, "content": m.content} for m in history(session, conversation.id)]
        if conversation
        else []
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        *past,
        {"role": "user", "content": text},
    ]

    result = LLMResult(text="", usage=Usage(), model="", provider="")
    for _ in range(MAX_TOOL_ROUNDS):
        result = gateway.run(
            LLMRequest(
                system=system,
                user=text,
                max_tokens=MAX_ASSISTANT_TOKENS,
                messages=messages,
                tools=TOOL_SCHEMAS,
            ),
            feature=FEATURE,
            tier=Tier.STRONG,
            user_id=user.id,
            prompt_version=prompt.version,
            request_id=request_id,
        )
        if not result.tool_calls:
            break

        messages.append(
            {
                "role": "assistant",
                "content": result.text or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                    for call in result.tool_calls
                ],
            }
        )
        for call in result.tool_calls:
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": _execute(session, user, call)}
            )
    else:
        # Hết 3 lượt vẫn muốn gọi công cụ: hỏng to thay vì trả một câu dựa trên
        # công cụ chưa chạy — một câu như thế là câu bịa có lớp vỏ hoàn chỉnh.
        raise ValueError("trợ lý lặp gọi công cụ quá 3 lượt mà chưa trả lời")

    # Tạo cuộc SAU lượt gọi model, không phải trước: model hỏng thì không để
    # lại một cuộc rỗng, và cửa sổ đua hẹp lại còn đúng lúc ghi.
    conversation = conversation or _open(session, user)
    asked, answered = save_turn(session, conversation.id, text, result.text.strip())
    return Answered(conversation, asked, answered)


def _find(session: Session, user: User) -> CoachConversation | None:
    return session.scalars(
        select(CoachConversation).where(
            CoachConversation.user_id == user.id,
            CoachConversation.attempt_id.is_(None),
        )
    ).first()


def _open(session: Session, user: User) -> CoachConversation:
    """Mở cuộc trợ lý, chịu được hai request đồng thời.

    Chỉ mục duy nhất từng phần (migration 050) là thứ quyết định; khối này chỉ
    biến lần thua cuộc đua thành một lượt đọc lại thay vì một lỗi 500.
    """
    conversation = CoachConversation(user_id=user.id, attempt_id=None)
    session.add(conversation)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _find(session, user)
        if existing is None:  # pragma: no cover — chỉ xảy ra nếu chỉ mục biến mất
            raise
        return existing
    return conversation
