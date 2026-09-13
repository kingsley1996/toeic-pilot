"""So một đề mới với họ đề cũ: trùng lặp + thể tích + band từ.

Chạy trước publish. Trùng KHÍT một câu (cùng stem + lựa chọn) là đề bị lộ —
chặn (exit 1). Gần-đúng (trigram ≥0.8) chỉ liệt kê để người duyệt quyết, vì
câu TOEIC cùng khuôn ("Where is...") giống nhau một nửa là bình thường.
Thể tích + band từ là bảng tham khảo, không chặn.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from app.content.exam import check as checker
from app.content.exam_cli.paths import DEFAULT_ROOT

NEAR_DUP = 0.8


def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _trigrams(text: str) -> set[str]:
    text = _norm(text)
    if len(text) < 3:
        return {text} if text else set()
    return {text[i : i + 3] for i in range(len(text) - 2)}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _read_workdir(root: Path) -> tuple[list[tuple[str, str, set[str]]], list[str]]:
    """Mọi câu hỏi (key, full_text, trigram) + mọi ngữ liệu của một đề.

    Thể tích chỉ đếm chữ NGƯỜI HỌC thấy (đề bài, lựa chọn, thoại/văn bản) —
    dòng `Explanation:` tiếng Việt lẫn vào là vỡ phép đo tần suất từ tiếng Anh.
    """
    questions: list[tuple[str, str, set[str]]] = []
    materials: list[str] = []
    for path in sorted((root / "paste").glob("*.txt")):
        stem = ""
        options: list[str] = []
        material: list[str] = []
        in_question = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "[QUESTION]":
                if stem or options:
                    full = stem + " " + " ".join(options)
                    questions.append((path.stem, full, _trigrams(full)))
                stem, options, in_question = "", [], True
            elif stripped in ("[SCRIPT]", "[PASSAGE]"):
                if stem or options:
                    full = stem + " " + " ".join(options)
                    questions.append((path.stem, full, _trigrams(full)))
                stem, options, in_question = "", [], False
            elif re.match(r"^\([A-D]\)", stripped) and in_question:
                options.append(re.sub(r"^\([A-D]\)\s*", "", stripped))
            elif stripped.startswith(("Answer:", "Explanation:", "Source:", "voice:")):
                continue
            elif stripped:
                if in_question:
                    stem += (" " + stripped) if stem else stripped
                else:
                    material.append(stripped)
        if stem or options:
            full = stem + " " + " ".join(options)
            questions.append((path.stem, full, _trigrams(full)))
        materials.extend(material)
    return questions, materials


def cmd_compare(args: argparse.Namespace) -> int:
    new_root = DEFAULT_ROOT / args.slug
    if not (new_root / "paste").is_dir():
        print(f"không có thư mục paste của {args.slug}", file=sys.stderr)
        return 2
    if args.against:
        others = [slug.strip() for slug in args.against.split(",") if slug.strip()]
    else:
        others = sorted(
            p.name for p in DEFAULT_ROOT.iterdir() if p.is_dir() and p.name != args.slug
        )
    new_questions, _ = _read_workdir(new_root)
    exact: set[str] = set()
    near: set[str] = set()
    for other in others:
        old_root = DEFAULT_ROOT / other
        if not (old_root / "paste").is_dir():
            continue
        old_questions, _ = _read_workdir(old_root)
        old_map = {_norm(full): key for key, full, _ in old_questions}
        top = 0.0
        top_pair = ""
        for key, full, tri in new_questions:
            if _norm(full) in old_map:
                exact.add(f"{key} == {other}/{old_map[_norm(full)]}")
                continue
            for okey, ofull, otri in old_questions:
                score = _jaccard(tri, otri)
                if score > top:
                    top, top_pair = score, f"{key} ~ {other}/{okey}"
                if score >= NEAR_DUP:
                    near.add(f"{key} ~ {other}/{okey} ({score:.2f})")
        print(f"so với {other}: {len(old_questions)} câu, max-sim {top:.2f} ({top_pair})")
    # Thể tích + band từ của đề mới đặt cạnh họ đề (tham khảo, không chặn).
    frequent = checker._frequent_words()
    for slug in [args.slug, *others]:
        root = DEFAULT_ROOT / slug
        if not (root / "paste").is_dir():
            continue
        questions, materials = _read_workdir(root)
        texts = [full for _, full, _ in questions] + materials
        words = checker._content_words(" ".join(texts))
        if not words:
            continue
        out10k = sum(1 for w in words if w not in frequent) / len(words)
        avglen = sum(len(w) for w in words) / len(words)
        print(f"  {slug}: {len(words)} từ nội dung, dài TB {avglen:.1f}, ngoài-10k {out10k:.1%}")
    if near:
        print(f"gần-đúng (≥{NEAR_DUP}, cần người nhìn):")
        for line in sorted(near)[:20]:
            print(f"  ~ {line}")
    if exact:
        print("TRÙNG KHÍT (chặn publish):")
        for line in sorted(exact)[:20]:
            print(f"  ✗ {line}")
        return 1
    print("không trùng khít câu nào.")
    return 0
