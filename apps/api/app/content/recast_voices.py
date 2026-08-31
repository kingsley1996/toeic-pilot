"""Đổi dàn giọng của một đề đã dán sang dàn narrator của đề thật.

Giọng nằm trong `question.audio_script` / `question_set.audio_script` — DỮ LIỆU,
không phải mã — nên đổi `TOEIC_NARRATORS` không chạm được vào đề đã có. Đây là
bước di trú cho chúng.

Hai ràng buộc, và cái thứ nhất là lý do việc này không thể là một lệnh UPDATE
với bảng ánh xạ cố định:

- **Giới tính của từng lượt phải giữ nguyên.** Part 3 và 4 hỏi thẳng "What does
  the *man* say?", nên lật giới tính một lượt là làm câu hỏi sai đáp án — và
  không phép kiểm nào trong hệ thống thấy điều đó.
- **Trong một ô, hai người nói không được trùng giọng**, nếu không người nghe
  không tách được ai đang nói.

Accent chọn theo kiểu tham lam: trong số các narrator cùng giới còn dùng được
cho ô đó, lấy accent đang ít lượt nhất — nên cả đề tự tiến về xấp xỉ 25% mỗi
accent thay vì phải rải lại từ đầu.

Sau khi chạy, lời thoại đã đổi nên `script_state` trả `STALE` cho đúng những ô
ấy: `backfill_audio --only questions` (KHÔNG cần `--force`) sẽ thu lại đúng
chúng và không đụng tới đề khác.
"""

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.exam_cli.paths import blueprint_path, workdir_for
from app.core.database import SessionLocal
from app.core.media import LOGICAL_VOICE_ACCENTS, TOEIC_NARRATORS, voice_gender
from app.models import PracticeTest, PracticeTestQuestion, Question, QuestionSet

NARRATORS_BY_GENDER: dict[str, list[str]] = {}
for _accent, _voice in TOEIC_NARRATORS.items():
    NARRATORS_BY_GENDER.setdefault(voice_gender(_voice), []).append(_voice)

_ScriptOwner = Question | QuestionSet


@dataclass
class Recast:
    label: str
    mapping: dict[str, str] = field(default_factory=dict)
    problem: str = ""

    @property
    def changed(self) -> bool:
        return any(before != after for before, after in self.mapping.items())


def plan_slot(label: str, voices: list[str], used: Counter[str]) -> Recast:
    """Ánh xạ giọng cũ -> giọng mới cho MỘT ô, giữ nguyên giới tính từng lượt."""
    recast = Recast(label=label)
    taken = {voice for voice in voices if voice in TOEIC_NARRATORS.values()}
    for voice in voices:
        if voice in taken and voice in TOEIC_NARRATORS.values():
            recast.mapping[voice] = voice
            continue
        gender = voice_gender(voice)
        free = [n for n in NARRATORS_BY_GENDER[gender] if n not in taken]
        if not free:
            recast.problem = (
                f"{gender}: ô có nhiều người cùng giới hơn số narrator "
                f"({len(NARRATORS_BY_GENDER[gender])}) — phải sửa tay"
            )
            return recast
        pick = min(free, key=lambda n: (used[n], n))
        recast.mapping[voice] = pick
        taken.add(pick)
    return recast


def _owners(session: Session, slug: str) -> list[tuple[_ScriptOwner, str]]:
    test = session.scalar(select(PracticeTest).where(PracticeTest.slug == slug))
    if test is None:
        raise SystemExit(f"không có đề nào tên {slug!r}")
    question_ids = session.scalars(
        select(PracticeTestQuestion.question_id).where(PracticeTestQuestion.test_id == test.id)
    ).all()

    questions = session.scalars(
        select(Question)
        .where(
            Question.id.in_(question_ids),
            Question.part.in_((1, 2)),
            Question.audio_script.is_not(None),
        )
        .order_by(Question.part, Question.created_at)
    ).all()
    set_ids = session.scalars(
        select(Question.set_id).where(Question.id.in_(question_ids), Question.set_id.is_not(None))
    ).all()
    sets = session.scalars(
        select(QuestionSet)
        .where(
            QuestionSet.id.in_(set(set_ids)),
            QuestionSet.part.in_((3, 4)),
            QuestionSet.audio_script.is_not(None),
        )
        .order_by(QuestionSet.part, QuestionSet.created_at)
    ).all()

    owners: list[tuple[_ScriptOwner, str]] = [
        (q, f"P{q.part} câu {str(q.id)[:8]}") for q in questions
    ]
    owners += [(s, f"P{s.part} cụm {s.title or str(s.id)[:8]}") for s in sets]
    return owners


def recast(session: Session, slug: str, dry_run: bool) -> int:
    owners = _owners(session, slug)
    used: Counter[str] = Counter()
    plans: list[tuple[_ScriptOwner, Recast]] = []

    for owner, label in owners:
        script = owner.audio_script or []
        voices: list[str] = []
        for turn in script:
            if turn["voice"] not in voices:
                voices.append(turn["voice"])
        plan = plan_slot(label, voices, used)
        plans.append((owner, plan))
        if plan.problem:
            continue
        for turn in script:
            used[plan.mapping[turn["voice"]]] += 1

    print(f"{len(plans)} ô có lời thoại\n")
    for owner, plan in plans:
        if plan.problem:
            print(f"  ✗ {plan.label}: {plan.problem}")
            continue
        if not plan.changed:
            continue
        moves = ", ".join(
            f"{before} → {after}" for before, after in plan.mapping.items() if before != after
        )
        print(f"  {plan.label}: {moves}")

    print("\nAccent sau khi đổi:")
    total = sum(used.values())
    by_accent: Counter[str] = Counter()
    for voice, count in used.items():
        by_accent[LOGICAL_VOICE_ACCENTS[voice]] += count
    for accent, count in sorted(by_accent.items()):
        print(f"  {accent}  {count:>4} lượt  {count / total:.0%}")

    stuck = [plan for _, plan in plans if plan.problem]
    changed = [(owner, plan) for owner, plan in plans if plan.changed and not plan.problem]
    print(f"\n{len(changed)} ô sẽ đổi · {len(stuck)} ô phải sửa tay")

    if dry_run:
        print("dry-run: không ghi gì")
        return 1 if stuck else 0

    for owner, plan in changed:
        owner.audio_script = [
            {**turn, "voice": plan.mapping[turn["voice"]]} for turn in (owner.audio_script or [])
        ]
    session.commit()
    print("đã ghi. Chạy `backfill_audio --only questions` để thu lại (không cần --force).")
    return 1 if stuck else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", required=True, help="slug của đề, ví dụ tp-form-07")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--files-only",
        action="store_true",
        help="bỏ qua database, chỉ đưa tệp dán và blueprint về đúng dàn giọng đang lưu",
    )
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        if args.files_only:
            return sync_files(session, args.test, args.dry_run)
        code = recast(session, args.test, args.dry_run)
        print("\n--- tệp dán và blueprint ---")
        return max(code, sync_files(session, args.test, args.dry_run))


_VOICE_LINE = re.compile(r"^voice:\s*(\S+)\s*$")


def read_paste(path: Path) -> tuple[list[str], list[str]]:
    """(giọng theo thứ tự xuất hiện, các dòng ĐƯỢC ĐỌC) của một tệp dán.

    Một dòng `[...]` đóng vùng lời thoại. Không đóng thì phần câu hỏi và bốn lựa
    chọn sau `[QUESTION]` cũng bị tính là lời thoại, và tệp Part 3/4 nào cũng
    trượt khỏi bảng tra — đã đo, 23/54 tệp trượt trước khi có dòng đó.
    """
    voice: str | None = None
    order: list[str] = []
    texts: list[str] = []
    for line in path.read_text().splitlines():
        if line.startswith("["):
            voice = None
            continue
        found = _VOICE_LINE.match(line)
        if found:
            voice = found.group(1)
            if voice not in order:
                order.append(voice)
            continue
        stripped = line.strip()
        if voice and stripped and not re.match(r"^(Answer|Source|Explanation)\s*:", stripped, re.I):
            texts.append(stripped)
    return order, texts


def sync_files(session: Session, slug: str, dry_run: bool) -> int:
    """Đưa tệp dán và `blueprint.json` về đúng dàn giọng ĐANG NẰM TRONG DATABASE.

    Lấy database làm nguồn sự thật chứ không chạy lại bộ lập ánh xạ: chạy lại là
    hai lượt lập độc lập, và chúng có thể ra hai kết quả khác nhau — đúng thứ
    việc này sinh ra để dọn.

    Nối tệp với hàng bằng NỘI DUNG lời thoại, không bằng tên tệp: tên tệp là id ô
    của blueprint, mà `commit_part` cộng thêm câu chứ không ghi đè, nên không có
    gì bảo đảm ô `p3-01` là hàng nào trong database.
    """
    index: dict[tuple[str, ...], list[str]] = {}
    for owner, _ in _owners(session, slug):
        script = owner.audio_script or []
        key = tuple(turn["text"] for turn in script)
        index[key] = list(dict.fromkeys(turn["voice"] for turn in script))

    paste_dir = workdir_for(slug) / "paste"
    if not paste_dir.is_dir():
        raise SystemExit(f"không có thư mục {paste_dir}")

    per_slot: dict[str, list[str]] = {}
    unmatched: list[str] = []
    rewritten = 0

    for path in sorted(paste_dir.glob("p[1-4]-*.txt")):
        before, texts = read_paste(path)
        after = index.get(tuple(texts))
        if after is None or len(after) != len(before):
            unmatched.append(path.name)
            continue
        per_slot[path.stem] = after
        mapping = dict(zip(before, after, strict=True))
        if all(old == new for old, new in mapping.items()):
            continue
        lines = [
            f"voice: {mapping[_VOICE_LINE.match(line).group(1)]}"  # type: ignore[union-attr]
            if _VOICE_LINE.match(line)
            else line
            for line in path.read_text().splitlines()
        ]
        moves = ", ".join(f"{o} → {n}" for o, n in mapping.items() if o != n)
        print(f"  {path.name}: {moves}")
        rewritten += 1
        if not dry_run:
            path.write_text("\n".join(lines) + "\n")

    plan_path = blueprint_path(slug)
    slots_changed = 0
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
        for part in plan.get("parts", []):
            for slot in part.get("slots", []):
                after = per_slot.get(slot.get("id", ""))
                if after is None:
                    continue
                if slot.get("voices"):
                    if slot["voices"] != after:
                        slot["voices"] = after
                        slots_changed += 1
                elif slot.get("voice") and slot["voice"] != after[0]:
                    slot["voice"] = after[0]
                    slots_changed += 1
        if not dry_run and slots_changed:
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")

    print(f"\n{rewritten} tệp dán · {slots_changed} ô blueprint")
    if unmatched:
        print(f"KHÔNG nối được với database: {', '.join(unmatched)}")
    if dry_run:
        print("dry-run: không ghi gì")
    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.exit(main())
