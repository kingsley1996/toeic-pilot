"""Tìm media không còn ai trỏ tới, và khoá lưu trữ không còn hàng nào mô tả.

    uv run python -m app.content.reconcile_media [--delete-rows]

Rác media sinh ra ở hai chỗ, và cả hai đều **im lặng**:

  * **Xác nhận hỏng.** Luồng bốn bước của ADR-006 tải byte lên nhà cung cấp
    TRƯỚC rồi mới ghi hàng. Bước xác nhận bị từ chối — thiếu giấy phép, thiếu
    chữ thay ảnh — thì byte ở lại đó, không hàng nào biết tới nó.
  * **Gỡ ảnh / thay bản thu.** Cả hai chỉ tháo liên kết. Hàng asset và object ở
    lại, cố ý: asset là content-addressed nên hai câu dùng chung một bức là
    chuyện bình thường, và xoá theo nút gỡ sẽ có ngày làm mất ảnh của câu khác.

Lệnh này **chỉ báo cáo**. Xoá object trên nhà cung cấp là không hoàn tác được và
phải do người quyết định từng lần, nên nó không có cờ nào làm việc đó; `--delete-rows`
chỉ dọn hàng trong database, thứ dựng lại được từ manifest.

Đây là lệnh offline sau extra `content`, cùng loại với `push_media`: nó đọc cấu
hình kho lưu trữ, và không byte nào của nó nằm trên đường phục vụ request.
"""

import argparse
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    AudioAsset,
    DictationItem,
    ImageAsset,
    Question,
    QuestionSet,
    VocabularyAudio,
)


@dataclass
class Report:
    dangling_audio: list[AudioAsset] = field(default_factory=list)
    dangling_image: list[ImageAsset] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.dangling_audio) + len(self.dangling_image)


def referenced_audio_ids(session: Session) -> set[str]:
    """Mọi `audio_asset.id` đang được ai đó trỏ tới.

    Bốn nguồn, và bỏ sót một nguồn là báo nhầm một bản thu đang dùng thành rác —
    nên danh sách này phải khớp với mọi khoá ngoại trỏ vào `audio_asset`. Hôm
    nay là: từ vựng, dictation, câu hỏi (Part 1, 2), cụm (Part 3, 4).
    """
    columns = (
        VocabularyAudio.audio_asset_id,
        DictationItem.audio_asset_id,
        Question.audio_asset_id,
        QuestionSet.audio_asset_id,
    )
    found: set[str] = set()
    for column in columns:
        found |= {str(value) for value in session.scalars(select(column)) if value}
    return found


def referenced_image_ids(session: Session) -> set[str]:
    """Mọi `image_asset.id` đang được ai đó trỏ tới.

    Ảnh câu hỏi (Part 1) cộng **ba** ô ngữ liệu của cụm. Quên ô 2 và 3 là báo
    nhầm ảnh của bài đọc nhiều đoạn thành rác.
    """
    columns = (
        Question.image_asset_id,
        QuestionSet.passage_image_id,
        QuestionSet.passage_2_image_id,
        QuestionSet.passage_3_image_id,
    )
    found: set[str] = set()
    for column in columns:
        found |= {str(value) for value in session.scalars(select(column)) if value}
    return found


def collect(session: Session) -> Report:
    report = Report()
    used_audio = referenced_audio_ids(session)
    used_image = referenced_image_ids(session)
    # Ảnh đại diện KHÔNG đi qua `image_asset` — `user_profile.avatar_storage_key`
    # giữ thẳng khoá lưu trữ. Nên nó không bao giờ xuất hiện ở đây, và cũng
    # không được coi là rác chỉ vì không có hàng asset nào mô tả nó.
    for clip in session.scalars(select(AudioAsset).order_by(AudioAsset.created_at)):
        if str(clip.id) not in used_audio:
            report.dangling_audio.append(clip)
    for picture in session.scalars(select(ImageAsset).order_by(ImageAsset.created_at)):
        if str(picture.id) not in used_image:
            report.dangling_image.append(picture)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tìm media không còn ai trỏ tới.")
    parser.add_argument(
        "--delete-rows",
        action="store_true",
        help="xoá hàng asset mồ côi (KHÔNG đụng tới object trên nhà cung cấp)",
    )
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        report = collect(session)

        for clip in report.dangling_audio:
            print(f"audio  {clip.storage_key}  {clip.duration_ms or 0}ms  {clip.source}")
        for picture in report.dangling_image:
            print(
                f"image  {picture.storage_key}  {picture.width}x{picture.height}  {picture.source}"
            )

        if not report.total:
            print("Không có media mồ côi.")
            return 0

        print(
            f"\n{len(report.dangling_audio)} bản thu và {len(report.dangling_image)} ảnh "
            f"không còn ai trỏ tới."
        )
        if not args.delete_rows:
            print(
                "Chạy lại với --delete-rows để xoá HÀNG trong database. "
                "Object trên nhà cung cấp thì lệnh này không đụng tới: xoá ở đó không "
                "hoàn tác được, và khoá là content-addressed nên một object có thể "
                "được một hàng khác dựng lại từ manifest."
            )
            return 0

        for clip in report.dangling_audio:
            session.delete(clip)
        for picture in report.dangling_image:
            session.delete(picture)
        session.commit()
        print(f"Đã xoá {report.total} hàng. Object vẫn còn trên nhà cung cấp.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
