"""Chặng nạp: đi qua ĐÚNG đường mà người dán đi.

`POST /parts/{part}/parse` → xem kết quả → `POST /parts`. Gọi HTTP với token của
một tài khoản `editor`, **không** gọi thẳng vào service.

Đắt hơn một lệnh `INSERT` và vẫn chọn, vì đường HTTP là đường đã có test và đã có
mọi luật ở `validators.py` đứng sau. Gọi thẳng service thì bỏ qua tầng schema, và
chỗ đầu tiên nó lộ ra sẽ là một câu Part 2 có bốn đáp án nằm im trong database —
hợp lệ với mọi thứ trừ chính bài thi.

**Từ chối nạp khi còn lỗi.** Cổng ở `check.py` đã chạy trước; nếu máy chủ vẫn báo
lỗi thì hai bên đang bất đồng, và nạp tiếp là ghi vào database thứ mà một trong
hai bên cho là sai.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from app.content.exam.blueprint import Blueprint
from app.content.exam.writer import paste_path


class LoadError(RuntimeError):
    pass


def raw_text(blueprint: Blueprint, workdir: Path, part: int, only: str | None = None) -> str:
    """Ghép các tệp dán của một part theo ĐÚNG thứ tự số câu.

    Thứ tự quan trọng: `commit_part` cấp số câu theo thứ tự cụm trong danh sách,
    lấp vào những số còn trống của part. Ghép lộn xộn thì câu 101 mang nội dung
    của ô p5-17, và không có gì báo — cả hai đều là câu Part 5 hợp lệ.
    """
    slots = [slot for plan in blueprint.parts if plan.part == part for slot in plan.slots]
    if only is not None:
        # Nạp ĐÚNG MỘT ô. `commit_part` lấp vào những số câu còn trống theo thứ
        # tự, nên gửi một cụm khi còn đúng một chỗ trống sẽ điền đúng chỗ đó.
        #
        # Có mặt vì lựa chọn thay thế là xoá cả part rồi nạp lại — và một part
        # đã có người làm bài thì việc đó phá lịch sử trả lời của họ để sửa một
        # câu. Không tương xứng.
        slots = [slot for slot in slots if slot.id == only]
    blocks: list[str] = []
    for slot in sorted(slots, key=lambda item: item.number):
        path = paste_path(workdir, slot)
        if not path.exists():
            raise LoadError(f"{slot.id}: chưa có tệp dán")
        blocks.append(path.read_text().strip())
    return "\n\n".join(blocks)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def ensure_test(base_url: str, token: str, blueprint: Blueprint) -> None:
    """Tạo đề nếu chưa có. Trùng slug thì bỏ qua — nạp lại là chuyện bình thường."""
    response = httpx.post(
        f"{base_url}/api/v1/admin/tests",
        headers=_headers(token),
        json={"slug": blueprint.slug, "title": blueprint.title, "kind": "full"},
        timeout=30.0,
    )
    if response.status_code in (200, 201):
        return
    if response.status_code == 409:
        return
    raise LoadError(f"không tạo được đề: {response.status_code} {response.text[:200]}")


def load_part(
    base_url: str,
    token: str,
    blueprint: Blueprint,
    workdir: Path,
    part: int,
    only: str | None = None,
) -> int:
    """Phân tích rồi ghi một part. Trả về số cụm đã ghi."""
    body = raw_text(blueprint, workdir, part, only)

    parsed = httpx.post(
        f"{base_url}/api/v1/admin/tests/{blueprint.slug}/parts/{part}/parse",
        headers=_headers(token),
        json={"raw_text": body},
        timeout=60.0,
    )
    if parsed.status_code != 200:
        raise LoadError(f"parse thất bại: {parsed.status_code} {parsed.text[:300]}")
    preview = parsed.json()
    if preview["error_count"]:
        raise LoadError(
            f"máy chủ báo {preview['error_count']} cụm có lỗi — chạy `check` và sửa trước khi nạp"
        )

    committed = httpx.post(
        f"{base_url}/api/v1/admin/tests/{blueprint.slug}/parts",
        headers=_headers(token),
        json={"part": part, "groups": preview["groups"]},
        timeout=120.0,
    )
    if committed.status_code not in (200, 201):
        raise LoadError(f"commit thất bại: {committed.status_code} {committed.text[:300]}")
    return len(preview["groups"])
