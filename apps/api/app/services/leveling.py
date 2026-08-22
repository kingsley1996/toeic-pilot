"""Đường cong level — số học thuần, không chạm cơ sở dữ liệu.

Cùng loại với `srs.py`: không session, không truy vấn, test được bằng một bảng
giá trị. Đổi ở đây là đổi CÁCH tính; đổi các con số thì không cần đụng tới tệp
này nữa, vì chúng đã là dữ liệu (`level_tier`, `progression_setting`).

Bảng ngưỡng đi vào đây như một THAM SỐ, không phải một hằng số. Đó là chỗ khác
biệt duy nhất so với bản đầu, và nó là thứ khiến admin sửa được đường cong mà
không cần triển khai lại: `app/services/progression_config.py` đọc bảng ra, chỗ
này chỉ biết số học.
"""

from __future__ import annotations

from dataclasses import dataclass


def curve_thresholds(
    *,
    coefficient: float,
    exponent: float,
    break_at: int,
    linear_step: int,
    max_level: int,
) -> list[int]:
    """Sinh ngưỡng XP tích luỹ cho từng level, chỉ số = level (phần tử 0 bỏ trống).

    Hai đoạn chứ không một: một hàm luỹ thừa chạy mãi thì tới level 40 mỗi bậc
    đòi hàng chục nghìn XP và người học lâu năm không bao giờ thấy thanh nhích —
    mà đó đúng là nhóm người hệ thống này tồn tại để giữ lại.

    Đây là MÁY SINH, không phải phép tra cứu. Nó ghi ra `level_tier` một lần;
    sau đó các hàng mới là sự thật, và admin sửa từng bậc được.
    """
    thresholds = [0, 0]
    for level in range(2, max_level + 1):
        if level <= break_at:
            thresholds.append(int(coefficient * level**exponent))
        else:
            thresholds.append(thresholds[break_at] + (level - break_at) * linear_step)
    return thresholds


@dataclass(frozen=True)
class Progress:
    level: int
    xp_total: int
    """XP đã tích trong level hiện tại, tính từ ngưỡng của chính nó."""
    xp_into_level: int
    """XP cần thêm để lên level kế. 0 khi đã kịch trần."""
    xp_for_next: int


def level_from_xp(xp_total: int, thresholds: list[int]) -> Progress:
    """Level và tiến độ trong level, suy từ tổng XP và bảng ngưỡng.

    XP âm không tồn tại (`xp_event.amount` luôn dương), nhưng nhận vào thì kẹp về
    0 thay vì ném lỗi: một trang hồ sơ không mở được vì số liệu lạ là hỏng nặng
    hơn hẳn so với việc hiển thị level 1.

    Bảng ngưỡng rỗng hoặc hỏng cũng vậy — rơi về level 1 chứ không ném. Bảng này
    do người sửa được, nên nó SẼ có lúc ở trạng thái nửa vời.
    """
    xp = max(0, xp_total)
    max_level = max(1, len(thresholds) - 1)

    level = 1
    while level < max_level and xp >= thresholds[level + 1]:
        level += 1

    floor = thresholds[level] if level < len(thresholds) else 0
    if level >= max_level:
        return Progress(level=level, xp_total=xp, xp_into_level=xp - floor, xp_for_next=0)

    return Progress(
        level=level,
        xp_total=xp,
        xp_into_level=xp - floor,
        xp_for_next=thresholds[level + 1] - xp,
    )


def frame_for_level(level: int, tiers: list[tuple[int, str]]) -> str | None:
    """Mã khung của một level, hoặc None khi chưa tới bậc nào.

    `tiers` là (min_level, code) theo thứ tự bất kỳ — sắp giảm dần ngay tại đây
    chứ không tin vào thứ tự của phía gọi: bảng này do người nhập, và một hàng
    thêm sau với ngưỡng thấp hơn sẽ chen vào giữa.
    """
    for threshold, code in sorted(tiers, reverse=True):
        if level >= threshold:
            return code
    return None
