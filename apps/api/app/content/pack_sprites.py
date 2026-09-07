"""Đóng một tấm ảnh sinh ra thành tấm ghép ô 16×16 dùng được cho Petland.

    uv run python -m app.content.pack_sprites --input raw.png --sheet dinos
    uv run python -m app.content.pack_sprites --input raw.png --sheet dinos --commit

Đầu vào là ảnh có nền phẳng (thường là magenta) với các sinh vật rải rác — đúng
thứ một model sinh ảnh trả về. Đầu ra là tấm ghép lưới 10 cột, ô 16×16, màu đã ép
về đúng bảng của `creatures.png`.

**Nền nhận bằng LIÊN THÔNG TỪ MÉP, không bằng ngưỡng màu.** Ngưỡng màu là cách
hiển nhiên và nó sai ở đúng chỗ đắt nhất: một con vật thân tím có màu gần magenta,
nên ngưỡng đủ rộng để xoá viền nhoè cũng đủ rộng để **ăn mất cả con vật**. Đo được
trên bộ khủng long đầu tiên: siết ngưỡng thì mất hẳn con tím và một phần con cổ
dài; nới ra thì rìa đầy đốm tím. Không ngưỡng nào đúng cả hai.

Liên thông không có đánh đổi ấy: nền là phần chạm mép ảnh và nối liền tới đó, còn
pixel tím nằm trong lòng sprite thì không bao giờ với tới được.

Bảng màu đích và luật hình dạng đo từ chính `creatures.png`; xem
`planning/docs/PETLAND-SPRITE-PROMPTS.md` §1–§2.
"""

import argparse
from collections import Counter, deque
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

SHEET_COLS = 10
TILE = 16
# Màu viền của `creatures.png`, và nó chiếm 50,5% toàn tấm — viền không phải
# đường bao, nó là gần một nửa bức vẽ.
OUTLINE = (0x3F, 0x26, 0x31)
# Trong lòng ô, sprite chiếm bao nhiêu là bình thường. Đo trên 180 ô gốc: trung
# vị 202/256. Dưới ngưỡng dưới là con vật bị thu quá nhỏ hoặc bị xén mất.
MIN_FILL, MAX_FILL = 90, 250
# Bao nhiêu pixel liên thông thì đáng coi là một sinh vật, không phải hạt nhiễu.
MIN_BLOB = 400
# Sai lệch mỗi kênh còn coi là "cùng màu nền". Rộng tay được, vì phép liên thông
# mới là thứ quyết định, không phải con số này.
BG_TOLERANCE = 70


def _palette(source: Path) -> list[tuple[int, int, int]]:
    image = Image.open(source).convert("RGBA")
    pixels = image.load()
    seen: set[tuple[int, int, int]] = set()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a > 0:
                seen.add((r, g, b))
    return sorted(seen)


def _background(image: Image.Image) -> set[tuple[int, int]]:
    """Pixel nền = chạm mép ảnh và nối tới đó qua toàn màu nền."""
    width, height = image.size
    pixels = image.load()
    corner = pixels[0, 0][:3]

    def near(spot: tuple[int, int, int]) -> bool:
        return all(abs(spot[i] - corner[i]) <= BG_TOLERANCE for i in range(3))

    seen: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    edge = [(x, y) for x in range(width) for y in (0, height - 1)]
    edge += [(x, y) for y in range(height) for x in (0, width - 1)]
    for spot in edge:
        if spot not in seen and near(pixels[spot][:3]):
            seen.add(spot)
            queue.append(spot)
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen:
                if near(pixels[nx, ny][:3]):
                    seen.add((nx, ny))
                    queue.append((nx, ny))
    return seen


def _blobs(
    image: Image.Image, background: set[tuple[int, int]]
) -> list[tuple[tuple[int, int, int, int], set[tuple[int, int]]]]:
    """Từng sinh vật: khung bao VÀ tập pixel của chính nó.

    Trả kèm tập pixel chứ không chỉ khung, vì khung bao của hai con đứng sát nhau
    CHỒNG LÊN NHAU — cắt theo khung thì con này mang theo cánh của con kia. Đo
    được trên bộ khủng long đầu tiên: ba trong mười sáu con dính mảnh của hàng
    xóm, và nó trông y hệt một lỗi vẽ chứ không như một lỗi cắt."""
    width, height = image.size
    seen = set(background)
    boxes: list[tuple[tuple[int, int, int, int], set[tuple[int, int]]]] = []
    for y0 in range(height):
        for x0 in range(width):
            if (x0, y0) in seen:
                continue
            queue = deque([(x0, y0)])
            seen.add((x0, y0))
            body = {(x0, y0)}
            left = right = x0
            top = bottom = y0
            while queue:
                x, y = queue.popleft()
                left, right = min(left, x), max(right, x)
                top, bottom = min(top, y), max(bottom, y)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        body.add((nx, ny))
                        queue.append((nx, ny))
            if len(body) >= MIN_BLOB:
                boxes.append(((left, top, right, bottom), body))
    # Đọc theo hàng như người nhìn, không theo thứ tự quét.
    boxes.sort(key=lambda pair: (pair[0][1] // 120, pair[0][0]))
    return boxes


def _shrink(cell: Image.Image, palette: list[tuple[int, int, int]]) -> Image.Image:
    """Thu về 16×16 rồi ép bảng màu. LẤY MẪU GẦN NHẤT, không nội suy — nội suy làm
    nhoè viền, mà viền là gần nửa số pixel của phong cách này."""
    small = cell.resize((TILE, TILE), Image.NEAREST)
    pixels = small.load()
    out = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
    target = out.load()
    for y in range(TILE):
        for x in range(TILE):
            r, g, b, a = pixels[x, y]
            if a <= 128:
                continue
            best = min(palette, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
            target[x, y] = (*best, 255)

    def neighbours(x: int, y: int) -> int:
        return sum(
            1
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if (dx or dy)
            and 0 <= x + dx < TILE
            and 0 <= y + dy < TILE
            and target[x + dx, y + dy][3] > 0
        )

    # Pixel lẻ loi là tàn dư của phép thu, không phải nét vẽ.
    lone = [
        (x, y)
        for y in range(TILE)
        for x in range(TILE)
        if target[x, y][3] > 0 and neighbours(x, y) < 3
    ]
    for x, y in lone:
        target[x, y] = (0, 0, 0, 0)

    # Vành ngoài cùng LUÔN là màu viền. Đây là luật của phong cách, không phải
    # thủ thuật: mọi ô của `creatures.png` đều có viền kín bao quanh.
    #
    # Nó cũng dọn đúng khuyết tật còn lại sau phép tách nền. Pixel ở ranh giới
    # là nửa nền nửa viền; phần ngả về nền bị xoá, phần ngả về viền ở lại rồi ép
    # bảng màu thành TÍM (`#9B4CA3` là màu gần magenta nhất trong bảng). Kết quả
    # là một vành đốm tím quanh con vật, trông như nét vẽ cố ý.
    rim = [
        (x, y)
        for y in range(TILE)
        for x in range(TILE)
        if target[x, y][3] > 0
        and any(
            not (0 <= x + dx < TILE and 0 <= y + dy < TILE) or target[x + dx, y + dy][3] == 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
    ]
    for x, y in rim:
        target[x, y] = (*OUTLINE, 255)
    return out


def pack(
    raws: Sequence[Path], source_sheet: Path
) -> tuple[list[Image.Image], list[dict[str, object]]]:
    """Nhiều ảnh thô vào MỘT tấm.

    Một mẻ sinh ảnh thường ra vài chục con trên vài tấm, và chúng thuộc cùng một
    chủ đề. Ghép chúng ở đây thay vì tạo mỗi ảnh một tấm: mỗi tấm là một dòng ở
    `CREATURE_SHEET_TILES`, một dòng ở `CREATURE_SHEETS`, một lượt sinh lại hợp
    đồng — chi phí của tấm nằm ở chỗ đó, không ở dung lượng tệp.
    """
    palette = _palette(source_sheet)
    tiles: list[Image.Image] = []
    report: list[dict[str, object]] = []
    for raw in raws:
        found, rows = _pack_one(raw, palette, len(tiles))
        tiles.extend(found)
        report.extend(rows)
    return tiles, report


def _pack_one(
    raw: Path, palette: list[tuple[int, int, int]], offset: int
) -> tuple[list[Image.Image], list[dict[str, object]]]:
    image = Image.open(raw).convert("RGBA")
    background = _background(image)
    boxes = _blobs(image, background)

    src = image.load()
    tiles: list[Image.Image] = []
    report: list[dict[str, object]] = []
    for index, ((left, top, right, bottom), body) in enumerate(boxes, start=offset):
        # Chỉ pixel của CHÍNH con này, không phải mọi thứ nằm trong khung của nó.
        cut = Image.new("RGBA", (right - left + 1, bottom - top + 1), (0, 0, 0, 0))
        into = cut.load()
        for x, y in body:
            into[x - left, y - top] = src[x, y]
        tile = _shrink(cut, palette)
        pixels = tile.load()
        drawn = [(x, y) for y in range(TILE) for x in range(TILE) if pixels[x, y][3] > 0]
        colours = Counter(pixels[x, y][:3] for x, y in drawn)
        touches = any(x in (0, TILE - 1) or y in (0, TILE - 1) for x, y in drawn)
        tiles.append(tile)
        report.append(
            {
                "index": index,
                "from": raw.name,
                "source": f"{right - left + 1}x{bottom - top + 1}",
                "fill": len(drawn),
                "colours": len(colours),
                "touches_edge": touches,
                "ok": MIN_FILL <= len(drawn) <= MAX_FILL and len(colours) >= 3,
            }
        )
    return tiles, report


def write_sheet(tiles: list[Image.Image], out: Path) -> None:
    rows = (len(tiles) + SHEET_COLS - 1) // SHEET_COLS
    sheet = Image.new("RGBA", (SHEET_COLS * TILE, rows * TILE), (0, 0, 0, 0))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % SHEET_COLS) * TILE, (i // SHEET_COLS) * TILE))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        action="append",
        help="ảnh thô, nền phẳng. Lặp lại cờ này để gộp nhiều ảnh vào một tấm.",
    )
    parser.add_argument("--sheet", required=True, help="tên tấm, ví dụ `dinos`")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("../web/public/pet/creatures.png"),
        help="tấm lấy BẢNG MÀU đích",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("../web/public/pet"))
    parser.add_argument(
        "--drop",
        type=int,
        nargs="*",
        default=[],
        metavar="Ô",
        help="chỉ số ô BỎ đi, đọc từ bảng báo cáo của lần chạy trước",
    )
    parser.add_argument("--commit", action="store_true", help="ghi tấm ghép; mặc định chỉ báo cáo")
    args = parser.parse_args()

    tiles, report = pack(args.input, args.source)
    # Bỏ ô SAU khi đã đánh số, không phải trước: chỉ số trong lệnh là chỉ số ở
    # bảng báo cáo mà người vừa nhìn, nên chạy lại với `--drop` phải giữ nguyên
    # cách đọc ấy. Đánh số lại trước khi bỏ thì mỗi lần bỏ một ô là mọi ô sau nó
    # đổi số, và lệnh thứ hai bỏ nhầm con.
    dropped = set(args.drop)
    if dropped:
        tiles = [tile for i, tile in enumerate(tiles) if i not in dropped]
        report = [row for row in report if row["index"] not in dropped]
    names = ", ".join(one.name for one in args.input)
    print(f"{names}: {len(tiles)} sinh vật\n")
    print("   ô     nguồn   lấp/256  màu  chạm mép")
    for row in report:
        mark = "" if row["ok"] else "   ← xem lại"
        print(
            f"  {row['index']:>2}  {row['source']:>9}  {row['fill']:>7}  {row['colours']:>3}"
            f"  {'có' if row['touches_edge'] else 'không':>8}{mark}"
        )
    bad = [r["index"] for r in report if not r["ok"]]
    if dropped:
        print(f"\n  đã bỏ {len(dropped)} ô: {sorted(dropped)}")
    print(f"  máy thấy dùng được: {len(report) - len(bad)}/{len(report)}")
    if bad:
        print(f"  cần xem lại: {bad}")
    print("  Số này là GỢI Ý. Nhìn ở đúng cỡ 16px trước khi tin.")

    if args.commit:
        out = args.out_dir / f"{args.sheet}.png"
        write_sheet(tiles, out)
        print(f"\n  đã ghi {out}")
    else:
        print("\n  (chưa ghi gì — thêm --commit)")


if __name__ == "__main__":
    main()
