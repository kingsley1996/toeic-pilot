"""Ép nền của một ảnh vừa sinh về đúng #FF00FF trước khi tách nền.

**Vì sao cần.** Bước tách nền của `generate2dsprite` khoá theo màu magenta thuần.
Model thì không nghe lời tuyệt đối: sáu khung sinh ra ở lượt thứ hai có nền hồng
đậm (~#E8207F) thay vì #FF00FF, và hậu quả không phải là một cảnh báo — nó là
một tấm PNG "trong suốt" mà tâm vẫn đặc 100%, tức là cái khung sẽ che kín avatar.
Đo được, nhưng chỉ khi có người nghĩ tới việc đo.

**Cách làm: lấy màu nền từ chính bốn góc ảnh.** Không hardcode màu hồng nào cả —
góc ảnh là chỗ DUY NHẤT chắc chắn là nền (prompt đã bắt chừa lề và không chạm
mép), nên nó tự nói cho ta biết model vừa vẽ nền màu gì. Một danh sách "các sắc
hồng đã gặp" sẽ hỏng ở lần model chọn sắc thứ bảy.

Ngưỡng mặc định 90 (khoảng cách Euclid trong RGB) đủ rộng để nuốt cả dải chuyển
sắc của nền lẫn viền răng cưa, và vẫn đủ hẹp để không chạm tới đỏ thẫm của bậc
grandmaster (B thấp) hay xanh băng của diamond.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

MAGENTA = (255, 0, 255)
CORNER = 24
TOLERANCE = 90.0


def normalise(path: Path, out: Path, tolerance: float = TOLERANCE) -> float:
    image = Image.open(path).convert("RGB")
    pixels = np.array(image).astype(float)

    corners = np.concatenate(
        [
            pixels[:CORNER, :CORNER].reshape(-1, 3),
            pixels[:CORNER, -CORNER:].reshape(-1, 3),
            pixels[-CORNER:, :CORNER].reshape(-1, 3),
            pixels[-CORNER:, -CORNER:].reshape(-1, 3),
        ]
    )
    background = np.median(corners, axis=0)

    distance = np.linalg.norm(pixels - background, axis=-1)
    mask = distance < tolerance
    pixels[mask] = MAGENTA

    Image.fromarray(pixels.astype(np.uint8)).save(out)
    return float(mask.mean())


if __name__ == "__main__":
    source = Path(sys.argv[1])
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_suffix(".magenta.png")
    share = normalise(source, target)
    print(f"{target}  ({share * 100:.1f}% pixel đã quy về magenta)")
