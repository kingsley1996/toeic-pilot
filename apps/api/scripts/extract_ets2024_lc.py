# ruff: noqa: E702, E501, E741, E731
"""Trích một test LISTENING từ 'SCRIPT LC.pdf' (sách scan Hàn, KHÔNG có text layer).

    uv run --with ocrmac --with pymupdf python scripts/extract_ets2024_lc.py --test 3

Hai giai đoạn, cache vào <out>/_ocr/pages.json để parse lại bao nhiêu lần cũng
không OCR lại (OCR là phần đắt — ~3s/trang):

  Phase 1: tìm trang của TEST n (mốc 'TEST n' trên trang answer key), Vision OCR
           từng trang → JSON {trang: [{t,x,y}]}.
  Phase 2: dựng paste/. Cấu trúc sách: key+P1 statements → PART 2 → PART 3 →
           PART 4, ~30 trang/test.

Vài điều đã trả giá mà parser này đã tính trước:
- tesseract CHẾT với trang lẫn Hàn-Anh; chỉ Apple Vision (ocrmac) đọc được.
- Thư mục CỘT KHÔNG CỐ ĐỊNH: có trang questions bên trái, có trang bên phải.
  Phân loại theo NỘI DUNG dòng, không theo x.
- Hội thoại P3: số câu cài trong lời thoại ('... picnic, Jingdao. 33 The food')
  và tag rỗng ('M-Au' dòng riêng) — phải giữ object join để nối đúng lượt.
- Dòng chú giải Hàn-translit ('§öl 4IC') lọt mọi bộ lọc tỉ lệ ASCII — whitelist
  ký tự mới chặn được.
Đếm kỳ vọng sau chạy: P1 24 statements · P2 25 · P3 39/13 set · P4 30/10 set.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KO = re.compile(r"[가-힣]")
VN = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
ALLOWED_NONASCII = set("\u2018\u2019\u201c\u201d\u2013\u2014€£")
QSTART = re.compile(
    r"^(What|Where|When|Why|How|Which|Who|According|In the|In her|In his|How much|How many)\b"
)
W = re.compile(r"[A-Za-z'’]+")


def ok(t):
    return (
        len(t) > 4
        and not KO.search(t)
        and not VN.search(t)
        and not (set(t) - set(map(chr, range(32, 127))) - ALLOWED_NONASCII)
    )


def ocr_pages(pdf, start, end, cache: Path, redo=False):
    if cache.exists() and not redo:
        return {int(k): v for k, v in json.loads(cache.read_text()).items()}
    import pymupdf
    from ocrmac import ocrmac

    doc = pymupdf.open(pdf)
    pages = {}
    for i in range(start, end):
        doc[i].get_pixmap(dpi=180).save("/tmp/_lc_ocr.png")
        res = ocrmac.OCR("/tmp/_lc_ocr.png", language_preference=["en-US"]).recognize()
        pages[i + 1] = [
            {"t": t, "y": round(1 - b[1] - b[3], 3), "x": round(b[0], 3)}
            for t, c, b in res
            if t.strip()
        ]
        print(f"  OCR trang {i + 1} ({len(pages[i + 1])} dòng)", file=sys.stderr, flush=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pages, ensure_ascii=False))
    return pages


def locate_test(pdf, n, window=40):
    """Trang key của TEST n: chứa 'TEST n' VÀ ≥40 dòng dạng `NN(X)`. Quét theo suy đoán 30 tr/test rồi hiệu chỉnh."""
    import pymupdf
    from ocrmac import ocrmac

    doc = pymupdf.open(pdf)
    approx = 1 + (n - 1) * 30
    for probe in sorted(range(1, len(doc)), key=lambda i: abs(i - approx)):
        if abs(probe - approx) > window:
            continue
        doc[probe].get_pixmap(dpi=150).save("/tmp/_lc_loc.png")
        res = ocrmac.OCR("/tmp/_lc_loc.png", language_preference=["en-US"]).recognize()
        txt = " ".join(t for t, _, _ in res)
        grid = len(re.findall(r"\d{1,3}\s*\([A-D]\)", txt))
        if re.search(rf"TEST\s*0?{n}\b", txt) and grid > 40:
            return probe
    raise SystemExit(f"không định vị được TEST {n} — xem tay bằng --start")


def parse(pages, start):
    """pages là dict trang tuyệt đối; quy về chỉ số tương đối so với trang key."""
    P = {i - start: v for i, v in pages.items()}
    nmax = max(P)

    # ranh giới phần: trang đầu chứa 'PART k'
    def first_page(marker):
        for pg in sorted(P):
            if any(re.match(rf"^PART\s*{marker}\b", l["t"].strip()) for l in P[pg]):
                return pg
        return None

    p2, p3, p4 = first_page(2), first_page(3), first_page(4)
    ends = {"p1": (1, 2), "p2": (p2, p3 - 1), "p3": (p3, p4 - 1), "p4": (p4, nmax)}
    key = {}
    for l in P[1]:
        m = re.match(r"^(\d{1,3})\s*\(?([A-D])\)?$", l["t"].strip().replace(" ", ""))
        if m and 1 <= int(m.group(1)) <= 100:
            key[int(m.group(1))] = m.group(2)

    def rows(rng, x0=0, x1=1):
        return [
            (pg, l["y"], l["x"], l["t"].strip())
            for pg in range(rng[0], rng[1] + 1)
            for l in sorted(P.get(pg, []), key=lambda r: (r["y"], r["x"]))
        ]

    # P1: statements (A)-(D) ở cột phải trang key + trang sau, câu trần thuật thuần
    stmts, seen = [], set()
    for pg, y, x, t in rows((1, 3), 0.44):
        m = re.match(r"^\(([A-D])\)\s+(.{6,})$", t)
        if not m:
            continue
        body = m.group(2)
        sent = re.match(r"^([A-Z][A-Za-z \u2019,.-]{8,})\.?$", body)
        txt = sent.group(1) + "." if sent else None
        if not txt:
            g = re.findall(r"\(([a-z][A-Za-z ,.\u2019-]{8,})\)", body)
            txt = g[-1].strip() if g else None
        if not txt or (m.group(1), txt.lower()) in seen:
            continue
        seen.add((m.group(1), txt.lower()))
        stmts.append((pg, y, m.group(1), txt))
    # P2: khối 'NN [tag] stem' + (A)(B)(C)
    Q2, cur = {}, None
    for pg, y, x, t in rows(ends["p2"]):
        m = re.match(r"^(\d{1,2})(?:\s+(.*))?$", t)
        if m and 7 <= int(m.group(1)) <= 31:
            cur = int(m.group(1))
            Q2[cur] = {"x": x, "stem": [], "opts": {}}
            rest = re.sub(r"^(?:[WM]-\w{2}\s*)?", "", m.group(2) or "")
            rest = re.sub(r"\s+[WM]-\w{2}$", "", rest).strip()
            if rest and ok(rest) and rest[0].isupper() and not rest.startswith("("):
                Q2[cur]["stem"].append(rest)
            continue
        if cur is None:
            continue
        mo = re.match(r"^\(([A-C])\)\s*(.{2,})$", t)
        if mo and abs(x - Q2[cur]["x"]) < 0.06:
            Q2[cur]["opts"].setdefault(mo.group(1), []).append(mo.group(2).strip())
            continue
        if (
            abs(x - Q2[cur]["x"]) < 0.06
            and not Q2[cur]["opts"]
            and ok(t)
            and len(t) > 12
            and t[0].isupper()
        ):
            Q2[cur]["stem"].append(t)

    def grab(rng, lo, hi):
        L = rows(rng)
        Q, cur = {}, None
        for pg, y, x, t in L:
            if re.fullmatch(r"\d{1,3}", t) and lo <= int(t) <= hi:
                cur = int(t)
                Q[cur] = {"x": x, "stem": [], "opts": {}}
                continue
            m = re.match(r'^(\d{1,3})\s+([A-Z“"].{6,})', t)
            if m and lo <= int(m.group(1)) <= hi:
                cur = int(m.group(1))
                Q[cur] = {"x": x, "stem": [m.group(2)], "opts": {}}
                continue
            if cur is None or abs(x - Q[cur]["x"]) > 0.06:
                continue
            mo = re.match(r"^\(([A-D])\)\s*(.{2,})$", t)
            if mo and len(Q[cur]["opts"]) < 4:
                Q[cur]["opts"].setdefault(mo.group(1), []).append(mo.group(2))
                continue
            if (
                not Q[cur]["opts"]
                and ok(t)
                and len(t) > 10
                and t[0].isupper()
                and len(Q[cur]["stem"]) < 2
            ):
                Q[cur]["stem"].append(t)
        turns, headers, cur = [], {}, None
        for pg, y, x, t in L:
            mh = re.match(r"^(\d{2,3})\s*[-–]\s*(\d{2,3})", t)
            if mh and lo <= int(mh.group(1)) <= hi:
                headers.setdefault(int(mh.group(1)), (pg, y))
                cur = None
                continue
            mt = re.match(r"^((?:W|M)-\w{2})[\s:]*\s*(.*)$", t)
            if mt and not KO.search(t) and not VN.search(t):
                txt = mt.group(2)
                if not txt and turns and turns[-1][4] == "md":
                    turns[-1][2][0] = mt.group(1)
                    cur = turns[-1][2]
                    continue
                t0 = [mt.group(1), txt]
                turns.append([pg, y, t0, x, "tag"])
                cur = t0
                continue
            md = re.match(r"^(\d{2,3})[|lI]?\s+([a-zA-Z].{5,})$", t)
            if (
                md
                and lo - 1 <= int(md.group(1)) <= hi
                and ok(md.group(2))
                and not md.group(2).endswith("?")
                and not QSTART.match(md.group(2))
            ):
                prev = turns[-1][2][0] if turns else "W-Am"
                spk = ("M" if prev.startswith("W") else "W") + "-" + prev.split("-")[1]
                t0 = [spk, md.group(2)]
                turns.append([pg, y, t0, x, "md"])
                cur = t0
                continue
            if (
                cur is not None
                and ok(t)
                and len(t) > 5
                and not t.startswith(("(", "Ø"))
                and not re.fullmatch(r"\d{1,3}", t)
            ):
                mid = cur[1][-1:].islower() or cur[1].endswith((",", "-"))
                if abs(x - turns[-1][3]) < 0.16 and (
                    mid or (not QSTART.search(t) and not t.endswith("?"))
                ):
                    cur[1] += " " + t
        starts = [lo + 3 * k for k in range((hi - lo) // 3 + 1)]
        cuts, idx = {}, 0
        for s in starts[1:]:
            pos = None
            if s in headers:
                hp = headers[s]
                pos = next((i for i, r in enumerate(turns) if (r[0], r[1]) >= hp), None)
            else:
                pos = next(
                    (
                        i
                        for i, r in enumerate(turns[idx:], idx)
                        if re.search(rf'(^|\s)\s{s}\s+[A-Z(“"]', r[2][1])
                    ),
                    None,
                )
            if pos is not None and pos > idx:
                cuts[s] = pos
                idx = pos
        sets = {starts[0]: turns[: cuts.get(starts[1], len(turns))]}
        for k in range(1, len(starts)):
            a = cuts.get(starts[k])
            nxt = cuts.get(starts[k + 1] if k + 1 < len(starts) else None)
            sets[starts[k]] = turns[a:nxt] if a is not None else []
        return Q, sets

    return key, stmts, Q2, ends, grab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(Path.home() / "Downloads/SCRIPT LC.pdf"))
    ap.add_argument("--test", type=int, required=True)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--pages", type=int, default=31)
    ap.add_argument("--redo-ocr", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = Path(args.out) if args.out else Path(__file__).resolve().parents[1] / "content/generated" / f"tp-2024-{args.test:02d}"
    start = (args.start - 1) if args.start else locate_test(args.pdf, args.test)
    print(f"TEST {args.test}: trang key = {start + 1}")
    pages = ocr_pages(
        args.pdf, start, start + args.pages, out / "_ocr" / "pages.json", args.redo_ocr
    )
    key, stmts, Q2, ends, grab = parse(pages, start)
    p3, p4 = grab(ends["p3"], 32, 70), grab(ends["p4"], 71, 100)
    # ---- xuất
    (out / "paste").mkdir(parents=True, exist_ok=True)
    emit2(out / "paste", key, stmts, Q2, {"p3": p3, "p4": p4})
    q = lambda pre: sum(
        f.read_text().count("[QUESTION]") for f in (out / "paste").glob(f"{pre}-*.txt")
    )
    print(
        f"STATS  key={len(key)}/100 · P1 statements={len(stmts)}/24 · p2={q('p2')}/25 · p3={q('p3')}/39 · p4={q('p4')}/30"
    )
    for pre, (Q, sets) in (("p3", p3), ("p4", p4)):
        empty = [s for s, v in sets.items() if not v]
        if empty:
            print(
                f"CHECK  {pre} set không lời thoại (header/số cài OCR hụt — xem guide §LC-ranh):",
                empty,
            )
    miss = sorted(set(range(7, 32)) - set(Q2))
    if miss:
        print("CHECK  P2 thiếu:", miss)
    if len(key) < 100 or len(stmts) < 24:
        print("CHECK  key/statements hụt — OCR lại trang key với --redo-ocr hoặc tăng --pages")


def emit2(pdir, key, stmts, Q2, G):
    # chỉ dọn phần của LC — nửa RC của cùng thư mục merge phải sống sót
    for pat in ("p1-*.txt", "p2-*.txt", "p3-*.txt", "p4-*.txt"):
        for f in pdir.glob(pat):
            f.unlink()
    for qn in range(6):
        grp = stmts[qn * 4 : (qn + 1) * 4]
        if len(grp) < 4:
            break
        body = "[QUESTION]\n" + "".join(
            f"({L}) {t}\n" for _, _, L, t in sorted(grp, key=lambda r: (r[0], r[1]))
        )
        (pdir / f"p1-0{qn + 1}.txt").write_text(
            body + f"Answer: {key.get(qn + 1, '?')}\nSource: reference\n"
        )
    seq = 0  # p2 trong nhà mang số thứ tự 01..25, không phải số đề 6..35
    for qn, q in sorted(Q2.items()):
        if len(q["opts"]) < 2:
            continue
        seq += 1
        body = f"[QUESTION]\n{' '.join(q['stem']).strip()}\n"
        body += "".join(f"({L}) {' '.join(w)}\n" for L, w in sorted(q["opts"].items()))
        (pdir / f"p2-{seq:02d}.txt").write_text(
            body + f"Answer: {key.get(qn, '?')}\nSource: reference\n"
        )
    for pre, (Q, sets) in G.items():
        for i, s in enumerate(sorted(sets), 1):
            body = "[SCRIPT]\n" + "".join(f"{r[2][0]}: {r[2][1]}\n" for r in sets[s]) + "\n"
            for j in range(3):
                q = Q.get(s + j)
                if not q:
                    continue
                body += f"[QUESTION]\n{' '.join(q['stem']).strip()}\n"
                body += "".join(f"({L}) {' '.join(w)}\n" for L, w in sorted(q["opts"].items()))
                body += f"Answer: {key.get(s + j, '?')}\nSource: reference\n"
            (pdir / f"{pre}-{i:02d}.txt").write_text(body)


if __name__ == "__main__":
    main()
