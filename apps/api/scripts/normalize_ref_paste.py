# ruff: noqa: E702, E501, E741, E731, F541
"""Chuẩn hoá paste tp-2024-NN về đúng format nhà — chỉ p3..p7, không đụng p1/p2.

    uv run python scripts/normalize_ref_paste.py content/generated/tp-2024-01/paste

Idempotent; chạy lại sau mỗi lần extract hoặc vá tay. Sửa tầng format:
marker nhân đôi, nhãn W-Am:/số câu ghim trong script, blank '---1xx---' →
'------- (n)', stem 'Blank (n)', option lai Việt-Anh (cắt phần Việt), dòng
option lạc trong passage (trả về câu đang thiếu, không thì xoá), '..'.

Không cứu được nội dung đã mất thật (dòng thoại cắt giữa trang, option hụt
OCR) — script chỉ in danh sách còn lại để vá theo planning/docs/EXTRACT-REF-2024.md.
"""

import re
import sys
from pathlib import Path

VN = r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵĐđ]"
LABEL = re.compile(r"^(?:[A-Za-z]{1,2}(?:-[A-Za-z]{2,3}){1,2}|Man|Woman|Narrator):\s*")
QNUM_MID = re.compile(r"(?<=[.!?] )\d{1,3} (?=[A-Z])")
OPT = re.compile(r"^\(([A-D])\)\s?(.*)$", re.M)
SPEAKTAG = re.compile(rf"^(?:[A-Za-z]{{1,2}}(?:-[A-Za-z]{{2,3}}){{1,2}}):\s*(.*)$")


def strip_script_noise(lines: list[str]) -> list[str]:
    out = []
    for l in lines:
        s = l.rstrip()
        if not s.strip():
            out.append(s)
            continue
        m = SPEAKTAG.match(s.strip())
        body = m.group(1) if m else s.strip()
        body = LABEL.sub("", body)
        body = QNUM_MID.sub("", body)
        body = re.sub(r"(?<![\d.\n])1\d\d(?=[A-Z][a-z])", "", body)  # '191Orange'
        body = re.sub(r"^(?:[,.] )?\d{1,3} (?=[A-Za-z])", "", body) if m else body
        if m and re.match(r"^\d{1,3}\s", m.group(1)):
            body = re.sub(r"^\d{1,3}\s+", "", body)
        # dòng bảng rơi vào hội thoại: ≤2 từ, không dấu câu — ví dụ 'Stormy Sea' trơ
        if m is None and len(body.split()) <= 2 and not re.search(r"[.?!]", body):
            continue
        out.append(body)
    return out


def split_inline_options(text: str) -> list[str]:
    """'...(A) x (B) y' một dòng → tách thành từng dòng option."""
    parts = re.split(r"(?=\([A-D]\) )", text)
    return [p.strip() for p in parts if p.strip()]


def fix_options_vn(line: str) -> str:
    """Option lai EN+VN: cắt từ token đầu chứa ký tự Việt."""
    head, _, rest = line.partition(" ")
    if not re.match(r"^\([A-D]\)$", head):
        return line
    keep = []
    for w in rest.split(" "):
        if re.search(VN, w):
            break
        keep.append(w)
    return (head + " " + " ".join(keep)).rstrip()


def questions_region(text: str) -> str:
    """Chạy sửa trên toàn bộ phần [QUESTION] blocks."""
    out = []
    for line in text.splitlines():
        m = OPT.match(line)
        if m and re.search(VN, line):
            line = fix_options_vn(line)
        elif re.search(VN, line):
            continue
        out.append(line)
    return "\n".join(out)


def clean_prose(t: str) -> str:
    t = QNUM_MID.sub("", t)  # '...Mina. 154 See you'
    t = re.sub(r"(?<![\d.])1\d\d(?=[A-Z][a-z])", "", t)  # '191Orange'
    return t


def normalize(fp: Path) -> list[str]:
    notes = []
    t = fp.read_text()
    lines = t.splitlines()
    part = fp.name[:2]
    stray_opts: list[str] = []

    # 1. marker nhân đôi liền nhau
    deduped = [
        l
        for i, l in enumerate(lines)
        if not (l.strip().startswith("[") and i and lines[i - 1].strip() == l.strip())
    ]
    if len(deduped) != len(lines):
        notes.append("gộp marker đôi")
        lines = deduped

    marks = [
        (i, re.match(r"^\[(SCRIPT|PASSAGE|QUESTION)\]$", l.strip()).group(1))
        for i, l in enumerate(lines)
        if re.match(r"^\[(SCRIPT|PASSAGE|QUESTION)\]$", l.strip())
    ]
    new: list[str] = []
    pos = 0
    while pos < len(lines):
        if marks and pos == marks[0][0]:
            tag = marks[0][1]
            end = marks[1][0] if len(marks) > 1 else len(lines)
            body = lines[pos + 1 : end]
            marks = marks[1:]
            pos = end
            if tag == "SCRIPT":
                new.append("[SCRIPT]")
                new.extend(strip_script_noise(body))
            elif tag == "PASSAGE":
                keep = []
                before = len(stray_opts)
                for l in body:
                    if OPT.match(l.strip()) or re.search(r"\([A-D]\) .*\([A-D]\)", l):
                        stray_opts.extend(split_inline_options(l.strip()))
                    else:
                        keep.append(clean_prose(l))
                if len(stray_opts) > before:
                    notes.append(f"option lạc khỏi passage x{len(stray_opts) - before}")
                new.append("[PASSAGE]")
                new.extend(keep)
            else:
                new.append("[QUESTION]")
                cleaned = clean_prose(questions_region("\n".join(body)))
                new.extend(cleaned.splitlines())
        else:
            new.append(lines[pos])
            pos += 1
    t = "\n".join(new)

    # 3. p6: '---1xx---' → '------- (n) -------' + stem 'Blank (n)'
    if part == "p6":
        nums = re.findall(r"---(1\d\d)---", t)
        if nums:
            for n, _ in enumerate(nums, 1):
                t = re.sub(rf"---{nums[n - 1]}---", f"------- ({n}) -------", t, count=1)
            blocks = t.split("[QUESTION]")
            rebuilt = [blocks[0]]
            for n, b in enumerate(blocks[1:], 1):
                first = b.strip().splitlines()[0] if b.strip() else ""
                if not OPT.match(first.strip()) and not first.strip().startswith("Blank"):
                    b = (
                        b.replace(first, f"Blank ({n})\n{first}", 1)
                        if first
                        else f"\nBlank ({n})" + b
                    )
                elif OPT.match(first.strip()):
                    b = f"\nBlank ({n})" + b
                rebuilt.append(b)
            t = "[QUESTION]".join(rebuilt)
            notes.append(f"p6: {len(nums)} blank đổi marker + stem")

    # 4. '..'
    t2 = re.sub(r"(?<!\.)\.\.(?!\.)", ".", t)
    if t2 != t:
        notes.append("chuẩn hoá '..'")
        t = t2

    # 5. trả option lạc về câu đang thiếu đúng chữ (không thì loại hẳn)
    if stray_opts:
        pool = {OPT.match(o).group(1): OPT.match(o).group(2) for o in stray_opts if OPT.match(o)}
        chunks = t.split("[QUESTION]")
        for ci, ch in enumerate(chunks[1:], 1):
            have = {m.group(1) for m in OPT.finditer(ch)}
            add = [(L, pool[L]) for L in "ABCD" if L in pool and L not in have]
            if not add:
                continue
            ins = "\n".join(f"({L}) {tx}".rstrip() for L, tx in add)
            mm = list(OPT.finditer(ch))
            if mm:
                line_end = (
                    ch.index("\n", mm[-1].start()) if "\n" in ch[mm[-1].start() :] else len(ch)
                )
                chunks[ci] = ch[:line_end] + "\n" + ins + ch[line_end:]
            else:
                anchor = re.search(r"\n(?=(Answer:|Source:|Explanation:))", ch)
                at = anchor.start() + 1 if anchor else len(ch.rstrip("\n"))
                chunks[ci] = ch[:at] + ins + "\n" + ch[at:]
            for L, _ in add:
                pool.pop(L)
            notes.append(f"trả {len(add)} option lạc về Q{ci}")
        t = "[QUESTION]".join(chunks)

    # 6. marker rỗng (bị lột hết nội dung) — parser nhà tính đó là 1 khối trống
    fl = t.splitlines()
    drop = set()
    mk = [i for i, l in enumerate(fl) if re.match(r"^\[(SCRIPT|PASSAGE|QUESTION)\]$", l.strip())]
    for k, i in enumerate(mk):
        nxt = mk[k + 1] if k + 1 < len(mk) else len(fl)
        if fl[i].strip() == "[PASSAGE]" and not "".join(fl[i + 1 : nxt]).strip():
            # chỉ xoá [PASSAGE] rỗng. [QUESTION] rỗng = câu mất nội dung, giữ để STATS
            # còn đếm đúng; [SCRIPT] rỗng = set mất lời thoại, giữ làm tín hiệu.
            drop.add(i)
    if drop:
        notes.append(f"xoá {len(drop)} marker rỗng")
        t = "\n".join(l for i, l in enumerate(fl) if i not in drop)

    # 7. passage cụt (<15 từ) đứng ngay trước passage khác → mảnh vỡ cùng tài liệu, gộp
    fl = t.splitlines()
    pmk = [i for i, l in enumerate(fl) if l.strip() in ("[PASSAGE]", "[QUESTION]")]
    merge_at = set()
    for k, i in enumerate(pmk):
        if fl[i].strip() != "[PASSAGE]" or k + 1 >= len(pmk):
            continue
        j = pmk[k + 1]
        if fl[j].strip() == "[PASSAGE]" and len(" ".join(fl[i + 1 : j]).split()) < 15:
            merge_at.add(j)
    if merge_at:
        notes.append(f"gộp {len(merge_at)} passage cụt")
        t = "\n".join(l for i, l in enumerate(fl) if i not in merge_at)

    fp.write_text(t.rstrip("\n") + "\n")
    return notes


def residual_problems(fp: Path) -> list[str]:
    t = fp.read_text()
    probs = []
    qs = re.split(r"^\[QUESTION\]$", t, flags=re.M)
    for i, q in enumerate(qs[1:], 1):
        opts = OPT.findall(q)
        if len(opts) != 4:
            probs.append(f"Q{i}: {len(opts)}/4 options")
        if re.search(r"^\s*$\n^\(", q, re.M):
            pass
    if "[SCRIPT]\n\n[QUESTION]" in t:
        probs.append("SCRIPT rỗng")
    for l in t.splitlines():
        if re.match(r"^(Answer:|Source:|Explanation:)", l):
            continue
        if (
            re.search(r"[a-z,]$", l)
            and not re.search(r"[.?!:\"'–-]$", l)
            and not OPT.match(l)
            and not l.startswith("[")
        ):
            probs.append(f"cụt?: ...{l[-30:]}")
            break
    return probs


if __name__ == "__main__":
    root = Path(sys.argv[1])
    total = 0
    for fp in sorted(root.glob("p[34567]-*.txt")):
        notes = normalize(fp)
        rp = residual_problems(fp)
        tag = "; ".join(notes) if notes else "—"
        print(f"{fp.name}: sửa: {tag}" + (f" | CÒN: {', '.join(rp)}" if rp else ""))
        total += len(notes)
    print(f"\nxong. cần vá tay thêm: đếm dòng 'CÒN' phía trên.")
