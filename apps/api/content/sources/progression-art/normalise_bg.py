"""Ép nền của một ảnh vừa sinh về đúng #FF00FF trước khi tách nền.

**Vì sao cần.** Bước tách nền của `generate2dsprite` khoá theo màu magenta thuần.
Model thì không nghe lời tuyệt đối: sáu khung sinh ra ở lượt bronze→challenger có
nền hồng đậm (~#E8207F) thay vì #FF00FF, và hậu quả không phải một cảnh báo — nó
là một tấm PNG "trong suốt" mà tâm vẫn đặc 100%, tức cái khung che kín avatar.

**Vì sao lan từ MÉP chứ không lọc theo màu.** Bản đầu quy mọi pixel nằm trong
bán kính màu quanh nền thành magenta, và nó ăn thủng nhân vật: thân nâu của linh
vật (170, 92, 72) chỉ cách nền hồng (205, 37, 135) **90,7** — vừa đúng ngưỡng 90
— nên 12% pixel thân bị coi là nền và khoét thành lỗ đen lỗ chỗ. Số đo, không
phải phỏng đoán.

Nền THẬT thì luôn nối liền với mép ảnh, còn màu áo của nhân vật thì không. Lan
từ bốn góc vào chỉ chạm tới những gì thông với bên ngoài, nên một vùng bên trong
nhân vật có màu gần giống nền vẫn an toàn dù bán kính màu có rộng đến đâu.

Ngưỡng mặc định 100 rộng hơn bản cũ ĐƯỢC, chính vì phép lan đã chặn thiệt hại:
nó nuốt trọn dải chuyển sắc của nền và viền răng cưa mà không với tới bên trong.
"""

import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

MAGENTA = (255, 0, 255)
CORNER = 24
TOLERANCE = 100.0


def normalise(path: Path, out: Path, tolerance: float = TOLERANCE) -> float:
    image = Image.open(path).convert("RGB")
    pixels = np.array(image).astype(float)
    height, width, _ = pixels.shape

    corners = np.concatenate(
        [
            pixels[:CORNER, :CORNER].reshape(-1, 3),
            pixels[:CORNER, -CORNER:].reshape(-1, 3),
            pixels[-CORNER:, :CORNER].reshape(-1, 3),
            pixels[-CORNER:, -CORNER:].reshape(-1, 3),
        ]
    )
    background = np.median(corners, axis=0)

    # Ứng viên: đủ gần màu nền. Chưa phải kết luận — mới là điều kiện cần.
    near = np.linalg.norm(pixels - background, axis=-1) < tolerance

    # Lan theo hàng, từ mọi pixel ứng viên nằm trên mép ảnh. Quét theo HÀNG chứ
    # không theo từng pixel: một BFS pixel-một trên ảnh 1024×1024 chạy bằng
    # Python mất hàng chục giây, còn mỗi lần bật một đoạn liền nhau thì số vòng
    # lặp tụt xuống theo số đoạn, không theo số pixel.
    reached = np.zeros_like(near, dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    def push_span(row: int, col: int) -> None:
        """Bật cả đoạn liền nhau chứa (row, col) và xếp hàng các hàng kề."""
        if not near[row, col] or reached[row, col]:
            return
        left = col
        while left > 0 and near[row, left - 1] and not reached[row, left - 1]:
            left -= 1
        right = col
        while right < width - 1 and near[row, right + 1] and not reached[row, right + 1]:
            right += 1
        reached[row, left : right + 1] = True
        for neighbour in (row - 1, row + 1):
            if 0 <= neighbour < height:
                queue.append((neighbour, left))
                queue.append((neighbour, right))
                queue.append((neighbour, (left + right) // 2))

    for col in range(width):
        push_span(0, col)
        push_span(height - 1, col)
    for row in range(height):
        push_span(row, 0)
        push_span(row, width - 1)

    while queue:
        row, col = queue.popleft()
        # Đi hết đoạn liền nhau quanh điểm này ở hàng kề: một hàng có thể chứa
        # nhiều đoạn nền rời nhau (hai bên nhân vật), nên phải quét chứ không
        # chỉ thử đúng một cột.
        start = col
        while start > 0 and near[row, start - 1]:
            start -= 1
        end = col
        while end < width - 1 and near[row, end + 1]:
            end += 1
        for probe in range(start, end + 1):
            if near[row, probe] and not reached[row, probe]:
                push_span(row, probe)

    pixels[reached] = MAGENTA
    Image.fromarray(pixels.astype(np.uint8)).save(out)
    return float(reached.mean())


if __name__ == "__main__":
    source = Path(sys.argv[1])
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_suffix(".magenta.png")
    share = normalise(source, target)
    print(f"{target}  ({share * 100:.1f}% pixel đã quy về magenta)")
