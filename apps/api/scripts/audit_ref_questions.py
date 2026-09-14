# ruff: noqa: E501, E741, E702, E731, E701, E401, I001
import sys
import re, json
from pathlib import Path
P = Path(sys.argv[1] if len(sys.argv) > 1 else "content/generated/tp-2024-01/paste")
OPT = re.compile(r"^\(([A-D])\)\s?(.*)$")
GARBAGE = re.compile(r"Paraphrasing|\bCH[a-zA-Z]{2,}|CHElo|J\*|6€|#X|\d\|\d|\| [a-z]|882\(|X2z")  # KHÔNG re.I
VN = r"[ạảãăằắẳẵặầấẩẫậẹẻẽềếểễệỉĩịọỏõồổỗộơờớởỡợủũụưừứửữỳỷỹĐđ]"  # bỏ é/è/ê/à/â/ô — 'résumé', 'à la carte' hợp lệ
rows, clean = [], {}
def tail(s, n=44): return "…" + s.strip()[-n:]

for fp in sorted(P.glob("p*-*.txt")):
    part, idx = fp.name[:2], fp.name[2:4]
    t = fp.read_text(); lines = t.splitlines()
    marks = [(i, re.match(r"^\[(SCRIPT|PASSAGE|QUESTION)\]$", l.strip()).group(1))
             for i, l in enumerate(lines)
             if re.match(r"^\[(SCRIPT|PASSAGE|QUESTION)\]$", l.strip())]
    nq_ok = {"p1": 1, "p2": 1, "p3": 3, "p4": 3, "p5": 1, "p6": 4}.get(part)
    qi = [i for i, tg in marks if tg == "QUESTION"]
    if nq_ok and len(qi) != nq_ok:
        rows.append((fp.name, "file", f"{len(qi)} [QUESTION], chuẩn {nq_ok}", ""))
    # script / passage level
    if part in ("p3", "p4"):
        s0 = 1 if lines and lines[0].strip() == "[SCRIPT]" else None
        s_end = qi[0] if qi else len(lines)
        script = [l for l in lines[1:s_end] if l.strip()] if s0 else []
        if not script:
            rows.append((fp.name, "file", "SCRIPT rỗng — set mất lời thoại", ""))
        else:
            for l in script:
                if re.search(r"[a-z,]$", l) and not re.search(r"[.?!\"]$", l):
                    rows.append((fp.name, "script", "dòng thoại cụt", tail(l)))
        nturn = len(script)
        if part == "p3" and 0 < nturn < 4:
            rows.append((fp.name, "file", f"chỉ {nturn} lượt thoại (<4)", ""))
    if part in ("p6", "p7"):
        p0 = next((i for i, tg in marks if tg == "PASSAGE"), None)
        pends = [qi[0]] if qi else [len(lines)]
        body = " ".join(l for l in lines[p0+1:pends[0]] if l.strip()) if p0 is not None else ""
        if p0 is not None:
            if part == "p6" and len(re.findall(r"------- \(\d\) -------", body)) != 4:
                rows.append((fp.name, "file", "blank (n) ≠ 4", tail(body, 30)))
            if len(body.split()) < 60:
                rows.append((fp.name, "file", f"passage {len(body.split())} từ", ""))
            if body and not re.search(r"[.?!\"'\)]$", body.strip()):
                rows.append((fp.name, "file", "passage kết thúc hở (nghi cụt cuối đoạn)", tail(body)))
    nc = 0
    for k, q in enumerate(qi, 1):
        end = qi[k] if k < len(qi) else len(lines)
        body = [l for l in lines[q+1:end] if l.strip()]
        opts = [OPT.match(l) for l in body if OPT.match(l)]
        stem = [l for l in body if not OPT.match(l) and not re.match(r"^(Answer:|Source:|Explanation:|voice:)", l)]
        m = re.search(r"^Answer:\s*(\S+)", "\n".join(body), re.M)
        ans = m.group(1) if m else None
        probs = []
        letters = "".join(o.group(1) for o in opts)
        need = "ABC" if part == "p2" else "ABCD"
        if letters != need:
            miss = "".join(c for c in need if c not in letters)
            probs.append(f"thiếu option {('['+miss+']') if miss else 'trắng cả 4'}" if letters else "mất cả 4 options")
        for o in opts:
            if not o.group(2).strip(): probs.append(f"option {o.group(1)} rỗng")
            if re.search(r",$", o.group(2).strip()): probs.append(f"option {o.group(1)} phẩy cuối (cụt)")
        if not stem:
            probs.append("stem trống") if part != "p1" else None
        else:
            st = stem[-1].strip()
            if part in ("p2", "p3", "p4", "p5", "p6", "p7") and not re.search(r'[?.!"“]$', st) and not st.startswith("Blank") and not st.endswith("to"):  # '…closest in meaning to' là chuẩn nhà
                probs.append("stem cụt cuối")
            if re.search(rf"{VN}", st) or re.search(rf"{VN}", " ".join(o.group(2) for o in opts)):
                probs.append("còn ký tự Việt")
            if part == "p5" and "-------" not in st:
                probs.append("mất marker blank")
        if ans and ans not in "ABCD":
            probs.append(f"Answer='{ans}'")
        if ans and ans in "ABCD" and len(letters) < 4 and ans not in letters:
            probs.append(f"Answer {ans} trỏ option đã mất")
        # garbage trong stem/script block
        j = " ".join(stem + [o.group(2) for o in opts])
        g = GARBAGE.search(j)
        if g: probs.append(f"rác: {g.group(0)!r}")
        if probs:
            rows.append((fp.name, f"Q{k}", "; ".join(probs), " | ".join(x.strip()[:40] for x in stem[-1:]) if stem else ""))
        else:
            nc += 1
    clean[fp.name] = (nc, len(qi))
tot_ok = sum(v[0] for v in clean.values())
print(f"TỔNG: {tot_ok} câu sạch / {sum(v[1] for v in clean.values())} khối câu\n")
cur = None
for f, q, p, ev in rows:
    if f != cur: print(f"\n### {f}"); cur = f
    print(f"| {q} | {p} | `{ev}` |")
json.dump({"clean": clean, "rows": rows}, open("/tmp/q_audit.json", "w"))
