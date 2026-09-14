# ruff: noqa: E702, E501, E741
#!/usr/bin/env python3
"""Trích một test RC từ 'GIẢI RC 2024.pdf' sang format paste của dự án.

    uv run --with pymupdf python scripts/extract_ets2024_rc.py --test 2

Sách chỉ có Reading (câu 101-200 = Part 5·30, Part 6·16, Part 7·54). Đọc bằng
PyMuPDF — pypdf vỡ layout hai cột thành rác 'wha/usiness' TRÔNG NHƯ văn bản
hợp lệ khi đem đo. Output: content/generated/tp-2024-{NN}/paste/.

Sau khi chạy, BẮT BUỘC xem khối STATS in ra và mở 2-3 tệp ngẫu nhiên — script
này đã biết trước những chỗ nó sẽ hụt (dòng `CHECK` dưới đây).
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import pymupdf

VN = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)


def test_pages(doc, n):
    """(start, end) trang của TEST n — đếm 1-based theo thứ tự marker 'TEST n' trong tệp."""
    hits = [
        i
        for i in range(len(doc))
        if re.search(rf"^\s*TEST\s*0?{n}\s*$", doc[i].get_text("text"), re.M)
    ]
    if not hits:
        raise SystemExit(f"không thấy marker TEST {n} — truyền --start/--end thủ công")
    start = hits[0] + 1  # trang marker là bìa trắng, nội dung bắt đầu sau nó
    nxt = [h for h in hits if h > start]
    return start, (nxt[0] if nxt else min(start + 41, len(doc)))


def parse_test(text):
    """→ list (part, slot, [(kind, payload)]). part 5: slot = số câu; 6/7: slot = index cụm."""
    clean = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or re.search(r"HOTLINE|TEST \d+ \(READING\)|^TEST \d+$|^\d{1,3}$", s):
            continue
        s = re.sub(r"^(\d{3})(?=[A-Za-z])(?!00\d)", r"\1 ", s)  # superscript '147As' dính liền
        clean.append(s)

    part = set_idx = 0
    items, mat, cur = [], [], None
    lambda: (
        mat
        and items.append(
            (part, set_idx if part != 5 else cur_num_holder[0], "material", "\n".join(mat[:]))
            or mat.clear()
        )
    )  # noqa: E731

    cur_num_holder = [0]

    def close_q():
        nonlocal cur
        if cur:
            items.append((part, cur["num"] if part == 5 else set_idx, "question", cur))
            cur = None

    def flush_mat():
        nonlocal mat
        if mat:
            items.append((part, set_idx, "material", "\n".join(mat)))
            mat = []

    for s in clean:
        if s in ("PART 5", "PART 6", "PART 7"):
            close_q()
            flush_mat()
            part = int(s[-1])
            set_idx = 0
            continue
        if part == 0:
            continue
        m = re.match(r"^(\d{2,3})\.\s*(.*)", s)
        if m and not VN.search(s[:24]) and 101 <= int(m.group(1)) <= 200:
            num = int(m.group(1))
            if part == 5:
                set_idx = num
            close_q()
            flush_mat()
            cur = {"num": num, "stem": [m.group(2).strip()], "opts": defaultdict(list), "opt": None}
            continue
        if s.startswith("Questions ") and part in (6, 7):
            close_q()
            flush_mat()
            set_idx += 1
            continue
        if cur is not None and re.match(r"^\([A-D]\)", s):
            for om in re.finditer(r"\(([A-D])\)\s*([^()]+?)(?=\s*\([A-D]\)\s*|$)", s):
                cur["opt"] = om.group(1)
                cur["opts"][om.group(1)].append(om.group(2).strip())
            continue
        if cur is not None:
            if VN.search(s) or s.startswith("Ø"):
                close_q()
            elif s:
                (cur["opts"][cur["opt"]] if cur["opt"] else cur["stem"]).append(s)
            continue
        if s and not VN.search(s):
            mat.append(s)
    close_q()
    flush_mat()
    return items


def reflow(par):
    """Một ngữ liệu → một đoạn liền mạch: liền dòng, strip số cài, bỏ dòng lặp tức thì."""
    out = []
    for l in par.splitlines():
        l = re.sub(r"^-+\s*", "", l.strip())
        l = re.sub(r"^1\d{2}\s+", "", l)
        if not l or re.fullmatch(r"-{4,}", l):
            continue
        if out and out[-1] == l:
            continue
        out.append(l)
    return " ".join(out)


def render(items, out_dir: Path):
    groups = defaultdict(list)
    for p, slot, kind, payload in items:
        groups[(p, slot)].append((kind, payload))
    counts = defaultdict(int)
    order6 = order7 = 0
    for (p, slot), blk in sorted(groups.items()):
        qs = [x for k, x in blk if k == "question"]
        if not qs:
            continue
        mats = [reflow(x) for k, x in blk if k == "material"]
        if p == 5:
            q = qs[0]
            stem = " ".join(q["stem"]).strip()
            if "-------" not in stem:
                stem = "------- " + stem  # blank nằm dòng riêng bị máy hút mất
            body = (
                f"[QUESTION]\n{stem}\n"
                + "".join(f"({L}) {' '.join(w)}\n" for L, w in sorted(q["opts"].items()))
                + "Source: reference\n"
            )
            name = f"p5-{slot - 100:02d}"
        else:
            if p == 6:
                order6 += 1
                name = f"p6-{order6:02d}"
            else:
                order7 += 1
                name = f"p7-{order7:02d}"
            body = "".join(f"[PASSAGE]\n{m}\n\n" for m in mats)
            for q in qs:
                body += f"[QUESTION]\n{' '.join(q['stem']).strip()}\n"
                body += "".join(f"({L}) {' '.join(w)}\n" for L, w in sorted(q["opts"].items()))
                body += "Source: reference\n"
        (out_dir / f"{name}.txt").write_text(body)
        counts[p] += sum(len(g["opts"]) and 1 or 1 for g in qs)
    return counts


def postpass(out_dir: Path):
    """Hai lỗi đã biết của máy đọc PDF: marker blank bị tách khi đứt trang, và dòng Việt dính lại."""
    for f in out_dir.glob("*.txt"):
        t = f.read_text()
        t = re.sub(r"-\s*--(1\d{2})-{2,}", r"---\1---", t)  # '- --131---' (đứt trang)
        t = re.sub(r"(?<!-)(1\d{2})---(?=[\s.,])", r"---\1---", t)  # '145---' thiếu gạch đầu
        t = re.sub(
            r"[^|\n]*[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵĐđ][^|\n]*",
            "",
            t,
            flags=re.I,
        )
        t = re.sub(r"\n{3,}", "\n\n", t)
        f.write_text(t)


def stats(out_dir: Path):
    q5 = sum(f.read_text().count("[QUESTION]") for f in out_dir.glob("p5-*.txt"))
    q6 = sum(f.read_text().count("[QUESTION]") for f in out_dir.glob("p6-*.txt"))
    q7 = sum(f.read_text().count("[QUESTION]") for f in out_dir.glob("p7-*.txt"))
    blanks = [
        str(n)
        for n in range(131, 147)
        if not re.search(
            rf"(-{{2,}}{n}-{{2,}}|---{n}---)",
            "".join(f.read_text() for f in out_dir.glob("p6-*.txt")),
        )
    ]
    print(f"STATS  p5={q5}/30 · p6={q6}/16 · p7={q7}/54 · tổng={q5 + q6 + q7}/100")
    if blanks:
        print("CHECK  blank Part 6 thiếu (đứt trang, vá tay bằng regex ---NNN---):", blanks)
    junk = [
        f.name for f in out_dir.glob("*.txt") if VN.search(f.read_text()) or "Ø" in f.read_text()
    ]
    if junk:
        print("CHECK  còn tiếng Việt/giải thích trong:", junk)
    thin = [
        f.name
        for f in out_dir.glob("*.txt")
        if 0 < len(f.read_text().split("[QUESTION]")[0].split()) < 40
        and f.name.startswith(("p6", "p7"))
    ]
    if thin:
        print("CHECK  ngữ liệu bất thường ngắn (<40 từ):", thin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(Path.home() / "Downloads/GIẢI RC 2024.pdf"))
    ap.add_argument("--test", type=int, required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    args = ap.parse_args()
    out = (
        Path(args.out)
        if args.out
        else Path(__file__).resolve().parents[1] / "content/generated" / f"tp-2024-{args.test:02d}"
    )  # noqa: E501
    (out / "paste").mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(args.pdf)
    start, end = (args.start - 1, args.end) if args.start else test_pages(doc, args.test)
    print(f"TEST {args.test}: trang {start + 1}..{end}")
    text = "\n".join(doc[i].get_text("text") for i in range(start, end))
    render(parse_test(text), out / "paste")
    postpass(out / "paste")
    stats(out / "paste")
    dash = []
    for i in range(start, end):
        d = [w for w in doc[i].get_text("words") if w[4].strip() in {"---", "——", "—"}]
        if len(d) >= 4 and len({round(w[1]) for w in d}) >= 3:
            dash.append(i + 1)
    if dash:
        print("CHECK  trang có bảng đồ hoạ (dựng graphics/ bằng words+cluster y, xem guide):", dash)


if __name__ == "__main__":
    main()
