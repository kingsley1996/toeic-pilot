"""Nhập hàng loạt audio và ảnh có sẵn trên đĩa vào một đề đã dán.

Audio được kiểm tra bằng ffprobe theo nội dung thực tế thay vì tin extension.
Dataset có thể chứa file tên `.mp3` nhưng bytes thực tế là WAV/PCM; importer
sẽ lưu MIME type và extension của storage key theo container thực tế.

    uv run python -m app.content.import_media audio --test <slug> --dir <thư mục> \\
        --accent en-US [--match number|order] [--dry-run]
    uv run python -m app.content.import_media image --test <slug> --dir <thư mục> \\
        --source-url ... --license ... --attribution ... [--dry-run]

Vì sao là lệnh offline chứ không phải luồng vé của ADR-006 §2.3: **hai bài toán
khác nhau.** Vé/xác minh tồn tại cho byte đi từ một máy ta không kiểm soát —
trình duyệt của biên tập viên. Ở đây file đã nằm trên đĩa máy soạn nội dung,
cùng loại với audio do `generate` sinh ra, nên nó là bài toán đồng bộ. Bắt đường
đơn giản trả giá cho đường phức tạp là cách làm cả hai đều tệ (xem `push_media`,
cùng lập luận).

**Chữ trước, media sau.** Lệnh này chỉ *gắn* vào câu và cụm đã tồn tại; nó không
tạo câu hỏi nào. Chưa dán nội dung thì không có ô nào để gắn, và nó sẽ nói ra
điều đó thay vì âm thầm không làm gì.

Khớp file với ô là phần duy nhất không suy ra được từ schema, nên nó **không
đoán bừa**: `--dry-run` in ra bảng khớp đầy đủ, và khi chạy thật, file thừa hay
ô trống đều làm lệnh dừng chứ không bỏ qua. Bỏ qua im lặng ở đây nghĩa là một đề
thiếu đúng một bản thu, phát hiện được khi có người ngồi làm tới câu đó.
"""

import argparse
import re
import sys
import json
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.media import (
    AUDIO_ACCENTS,
    script_fingerprint,
    storage_key_for,
    upload_source_hash,
)
from app.core.storage import (
    CloudinaryDriver,
    LocalDiskDriver,
    MediaKind,
    S3Driver,
    StorageError,
    get_driver,
    guess_mime,
)
from app.models import (
    AudioAsset,
    ImageAsset,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionSet,
)

AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Slot:
    """Một ô media đang chờ, và con số dùng để khớp file vào nó.

    `number` là số câu chính thức: với Part 1/2 là số của chính câu đó, với Part
    3/4 là số câu **đầu tiên** của cụm — vì cả cụm dùng chung một bản thu, và
    người đặt tên file gần như luôn lấy số mở đầu (`32.mp3`, `32-34.mp3`).
    """

    number: int
    part: int
    label: str
    owner: Question | QuestionSet
    filled: bool


def audio_slots(session: Session, test: PracticeTest) -> list[Slot]:
    """Mọi ô bản thu của đề, theo thứ tự số câu.

    Hai tầng, không phải một (ADR-001 §A4.3): Part 1 và 2 mỗi câu một clip, Part
    3 và 4 một bài nói dùng chung cho cả cụm. Gộp lại thành một danh sách ở đây
    để phần khớp file không phải biết sự khác nhau đó.
    """
    rows = session.execute(
        select(PracticeTestQuestion, Question)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .where(PracticeTestQuestion.test_id == test.id, Question.part.in_((1, 2, 3, 4)))
        .order_by(PracticeTestQuestion.number)
    ).all()

    slots: list[Slot] = []
    seen_sets: set[uuid.UUID] = set()
    for link, question in rows:
        if question.part in (1, 2):
            slots.append(
                Slot(
                    number=link.number,
                    part=question.part,
                    label=f"câu {link.number}",
                    owner=question,
                    filled=question.audio_asset_id is not None,
                )
            )
            continue

        stimulus = question.question_set
        if stimulus is None or stimulus.id in seen_sets:
            continue
        seen_sets.add(stimulus.id)
        slots.append(
            Slot(
                number=link.number,
                part=question.part,
                label=f"cụm từ câu {link.number} · {stimulus.title or 'không tên'}",
                owner=stimulus,
                filled=stimulus.audio_asset_id is not None,
            )
        )
    return slots


def image_slots(session: Session, test: PracticeTest, part: int) -> list[Slot]:
    """Ô ảnh. Hai hình dạng, vì ảnh treo ở hai tầng khác nhau.

    **Part 1** — ảnh trên CÂU. Mỗi câu một bức, và câu nào cũng phải có.

    **Part 3 và 4** — hình trên CỤM, và chỉ vài cụm cuối mỗi part mới có. Bảng
    giá, lịch trình hay sơ đồ mặt bằng in một lần cạnh cả ba câu, và một câu
    trong cụm nói "Look at the graphic". Đúng tầng với đoạn văn Part 7, nên nó
    dùng `passage_image_id` chứ không sinh cột mới.

    Part 2 không có ảnh nào — đề in con số 0 chữ ở đó.
    """
    if part == 2:
        return []

    rows = session.execute(
        select(PracticeTestQuestion, Question)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .where(PracticeTestQuestion.test_id == test.id, Question.part == part)
        .order_by(PracticeTestQuestion.number)
    ).all()

    if part == 1:
        return [
            Slot(
                number=link.number,
                part=1,
                label=f"câu {link.number}",
                owner=question,
                filled=question.image_asset_id is not None,
            )
            for link, question in rows
        ]

    slots: list[Slot] = []
    seen: set[uuid.UUID] = set()
    for link, question in rows:
        stimulus = question.question_set
        if stimulus is None or stimulus.id in seen:
            continue
        seen.add(stimulus.id)
        slots.append(
            Slot(
                number=link.number,
                part=part,
                label=f"cụm từ câu {link.number} · {stimulus.title or 'không tên'}",
                owner=stimulus,
                filled=stimulus.passage_image_id is not None,
            )
        )
    return slots


# Nhãn "part N" trong tên file, ở mọi kiểu viết hay gặp: `part3`, `Part_3`,
# `p3`, `phan3`. Phải gỡ TRƯỚC khi tìm số câu — xem `leading_number`.
_PART_LABEL = re.compile(r"(?:^|[^a-z])(?:part|phan|p)[\s_-]*\d+", re.IGNORECASE)


def leading_number(path: Path) -> int | None:
    """Số câu suy ra từ tên file, hoặc None.

    Hai luật, và cả hai đều đến từ một lần hỏng im lặng:

    **Gỡ nhãn part trước.** `part3_32.mp3` mà đọc thẳng sẽ cho `3`. Tệ hơn là
    `3` KHÔNG phải một số vô nghĩa — Part 1 chạy từ câu 1 đến 6, nên nó khớp
    thành công vào câu 3 và gắn một đoạn hội thoại Part 3 vào một câu ảnh Part 1.
    Khớp sai mà vẫn "thành công" là đúng thứ bảng `--dry-run` sinh ra để chặn,
    nhưng chặn được thì tốt hơn là trông cậy vào mắt người.

    **Rồi lấy số ĐẦU, không phải số cuối.** `32-34.mp3` là cụm mở đầu ở câu 32;
    số cuối cho 34, và 34 không mở đầu cụm nào nên mọi file đặt tên theo khoảng
    sẽ trượt hết.
    """
    stem = _PART_LABEL.sub(" ", path.stem)
    match = re.search(r"\d+", stem)
    return int(match.group()) if match else None


def match_files(
    files: list[Path], slots: list[Slot], mode: str
) -> tuple[list[tuple[Path, Slot]], list[Path], list[Slot]]:
    """Ghép file với ô. Trả về (cặp đã khớp, file thừa, ô còn trống)."""
    if mode == "index":
        # Tra theo VỊ TRÍ: file mang số 11 lấy ô thứ 11 của part. Bản đầu ghép
        # theo cặp (`zip`), và cặp chỉ đúng khi mọi ô đều có file — sai ngay ở
        # hình Part 3/4, nơi **chỉ vài cụm cuối** có hình. Ghép cặp ở đó sẽ đẩy
        # hình của cụm 11 vào cụm 1, khớp thành công, và không có gì báo.
        pairs, extra = [], []
        taken: set[int] = set()
        for path in files:
            index = leading_number(path)
            if index is None or not 1 <= index <= len(slots) or index in taken:
                extra.append(path)
                continue
            taken.add(index)
            pairs.append((path, slots[index - 1]))
        return pairs, extra, [s for i, s in enumerate(slots, start=1) if i not in taken]

    if mode == "order":
        # `index`: số trong tên file là thứ tự TRONG PART, không phải số câu —
        # `part2/10_....mp3` là câu thứ 10 của Part 2, tức câu 16. Chế độ này
        # tồn tại vì `number` không chỉ trượt ở đây, nó khớp SAI: 10 cũng là một
        # câu Part 2 có thật, nên file thứ mười được gắn vào câu thứ tư.
        #
        # `order`: cùng phép ghép, dùng khi tên file không có số nào.
        #
        # Cả hai đều dựa vào thứ tự, nên `collect` phải sắp theo số. Và cả hai
        # chỉ đúng khi số ô bằng số file — chênh một là lệch từ đó trở đi, nên
        # phần thừa/thiếu bên dưới là thứ chặn, không phải cảnh báo.
        pairs = list(zip(files, slots, strict=False))
        return pairs, files[len(pairs) :], slots[len(pairs) :]

    by_number = {slot.number: slot for slot in slots}
    pairs, extra = [], []
    for path in files:
        number = leading_number(path)
        slot = by_number.pop(number, None) if number is not None else None
        if slot is None:
            extra.append(path)
        else:
            pairs.append((path, slot))
    return pairs, extra, list(by_number.values())


def collect(directory: Path, suffixes: set[str]) -> list[Path]:
    """File media trong thư mục, sắp theo **số** chứ không theo chuỗi.

    Sắp theo chuỗi cho ra `1, 10, 11, 12, 13, 2, 3…`, và chế độ `order` ghép
    file với ô theo đúng thứ tự này — nên một lần `sorted()` mặc định là mười ba
    đoạn hội thoại vào sai chỗ, tất cả vẫn "khớp thành công".
    """
    files = [
        path
        for path in directory.rglob("*")
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() in suffixes
    ]
    return sorted(
        files, key=lambda path: (leading_number(path) is None, leading_number(path) or 0, path.name)
    )


def store(kind: MediaKind, storage_key: str, path: Path, data: bytes) -> None:
    """Đưa byte tới nơi nó sẽ được phục vụ, theo đúng driver đang cấu hình.

    `LocalDiskDriver.write` và `upload_file` đều nằm NGOÀI protocol
    `StorageDriver`, để một request handler không với tới được đường ghi
    (ADR-006 §2.8c). Đây là lệnh offline nên nó được phép gọi thẳng.
    """
    driver = get_driver(kind)
    if isinstance(driver, LocalDiskDriver):
        driver.write(storage_key, data)
    elif isinstance(driver, CloudinaryDriver | S3Driver):
        driver.upload_file(storage_key, path)
    else:
        raise StorageError(f"driver cho {kind} không hỗ trợ ghi offline")


def probe_audio(data: bytes, suffix: str) -> tuple[int, str, str]:
    """Detect the actual audio container, duration and MIME type.

    The dataset may contain files whose extension does not match their actual
    container. For example, a file named ``10_xxx.mp3`` can contain RIFF/WAVE
    PCM audio. Therefore the importer must inspect the bytes with ffprobe
    instead of trusting the filename extension.

    Returns:
        (duration_ms, actual_extension, mime_type)
    """
    suffix = suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        raise ValueError(f"unsupported audio extension: {suffix}")

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=format_name,duration",
                    "-of",
                    "json",
                    tmp.name,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Không tìm thấy ffprobe. Hãy cài FFmpeg bằng `brew install ffmpeg`."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise ValueError(
            f"ffprobe không đọc được audio"
            + (f": {detail}" if detail else "")
        ) from exc

    try:
        payload = json.loads(result.stdout)
        format_info = payload["format"]
        format_name = str(format_info["format_name"]).lower()
        duration = float(format_info["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(
            "ffprobe không trả về format/duration hợp lệ"
        ) from exc

    if duration <= 0:
        raise ValueError(f"audio có duration không hợp lệ: {duration}")

    # ffprobe may report multiple compatible container names for M4A/MP4.
    if "mp3" in format_name:
        actual_ext = ".mp3"
        mime_type = "audio/mpeg"
    elif "wav" in format_name or "wave" in format_name:
        actual_ext = ".wav"
        mime_type = "audio/wav"
    elif any(
        name in format_name
        for name in ("m4a", "mp4", "mov", "3gp", "3g2")
    ):
        actual_ext = ".m4a"
        mime_type = "audio/mp4"
    else:
        raise ValueError(
            f"audio format không được hỗ trợ: {format_name!r}. "
            "Dataset chỉ hỗ trợ MP3, WAV và M4A."
        )

    return round(duration * 1000), actual_ext, mime_type


def probe_audio_file(path: Path) -> tuple[int, str, str]:
    """Read and validate one audio file from disk."""
    try:
        data = path.read_bytes()
        return probe_audio(data, path.suffix)
    except (OSError, ValueError, RuntimeError) as exc:
        raise ValueError(f"audio {path}: {exc}") from exc


def validate_audio_files(files: list[Path]) -> dict[Path, tuple[int, str, str]]:
    """Validate all audio files before any storage/DB mutation."""
    results: dict[Path, tuple[int, str, str]] = {}

    for path in files:
        results[path] = probe_audio_file(path)

    return results


def import_audio(
    session: Session,
    pairs: list[tuple[Path, Slot]],
    accent: str,
    probed: dict[Path, tuple[int, str, str]],
) -> int:
    done = 0

    for path, slot in pairs:
        data = path.read_bytes()

        try:
            duration_ms, actual_ext, mime_type = probed[path]
        except KeyError as exc:
            raise ValueError(
                f"thiếu kết quả validation cho audio {path}"
            ) from exc

        # Storage key and MIME are based on the ACTUAL container, not the
        # filename extension. This matters for dataset files such as:
        # `10_xxx.mp3` whose bytes are actually RIFF/WAVE.
        digest = upload_source_hash(str(uuid.uuid4()))
        key = storage_key_for(
            digest,
            ext=actual_ext.lstrip("."),
        )

        # Probe/validate has already completed for every file before import,
        # so only valid audio reaches storage.
        store("audio", key, path, data)

        asset = AudioAsset(
            storage_key=key,
            source_hash=digest,
            mime_type=mime_type,
            size_bytes=len(data),
            duration_ms=duration_ms,
            # `uploaded`, không phải `tts` — và đây không phải chi tiết ghi chép.
            # Nó là thứ khiến worker TTS KHÔNG BAO GIỜ ghi đè bản thu này
            # (`AudioState.EXTERNAL`).
            source="uploaded",
            engine="uploaded",
            engine_version="-",
            voice="uploaded",
            accent=accent,
        )
        session.add(asset)
        session.flush()

        owner = slot.owner
        owner.audio_asset_id = asset.id
        owner.audio_attached_at = datetime.now(UTC)

        script = owner.audio_script or []
        owner.audio_script_hash = script_fingerprint(
            [(turn["text"], turn["voice"]) for turn in script]
        )

        print(
            f"  {path.name:<28} -> Part {slot.part} {slot.label}"
            f"  [{actual_ext.lstrip('.')} · {duration_ms} ms]"
        )
        done += 1

    return done


def import_images(
    session: Session,
    pairs: list[tuple[Path, Slot]],
    *,
    source_url: str,
    license_name: str,
    attribution: str,
    alt_text: str | None,
) -> int:
    from PIL import Image

    done = 0
    for path, slot in pairs:
        data = path.read_bytes()
        with Image.open(path) as opened:
            width, height = opened.size

        digest = upload_source_hash(str(uuid.uuid4()))
        key = storage_key_for(digest, ext=path.suffix.lstrip("."), prefix="image")
        store("image", key, path, data)

        asset = ImageAsset(
            storage_key=key,
            source_hash=digest,
            mime_type=guess_mime(path.name),
            size_bytes=len(data),
            width=width,
            height=height,
            source="uploaded",
            # Ba cột NOT NULL, và không có mặc định ở bất kỳ tầng nào — cùng luật
            # với `question.source` (ADR-007 §2.5). Phần lớn ảnh mở là CC-BY,
            # dùng được nhưng *phải* ghi công.
            source_url=source_url,
            license=license_name,
            attribution=attribution,
            # Part 1 để trống có chủ ý: mô tả kỹ bức ảnh là lộ đáp án, vì nội
            # dung ảnh CHÍNH LÀ thứ câu hỏi đang kiểm.
            #
            # Part 3/4 thì ngược lại — hình là dữ liệu phải đọc mới trả lời
            # được, và mô tả nó KHÔNG lộ đáp án vì người học vẫn phải nghe. Bỏ
            # trống ở đó là một câu người dùng máy đọc màn hình không làm được.
            alt_text=alt_text,
        )
        session.add(asset)
        session.flush()

        # Part 1 gắn lên câu, Part 3/4 gắn lên cụm — hai cột khác nhau, và đó là
        # khác biệt thật về format chứ không phải chi tiết lưu trữ.
        if isinstance(slot.owner, Question):
            slot.owner.image_asset_id = asset.id
        else:
            slot.owner.passage_image_id = asset.id
        print(f"  {path.name:<28} -> Part {slot.part} {slot.label}")
        done += 1
    return done


def report(pairs, extra, empty, *, kind: str, skipped=()) -> None:  # type: ignore[no-untyped-def]
    print(
        f"\n{len(pairs)} khớp · {len(skipped)} bỏ qua (đã có) · "
        f"{len(extra)} file thừa · {len(empty)} ô còn trống\n"
    )
    for path, slot in pairs:
        print(f"  {path.name:<28} -> Part {slot.part} {slot.label}")
    for path, slot in skipped:
        print(f"  {path.name:<28} -> Part {slot.part} {slot.label}  [đã có, bỏ qua]")
    for path in extra:
        print(f"  {path.name:<28} -> KHÔNG khớp ô nào", file=sys.stderr)
    for slot in empty:
        print(f"  {'(trống)':<28} <- Part {slot.part} {slot.label} chưa có {kind}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nhập audio/ảnh có sẵn vào một đề đã dán.")
    parser.add_argument("kind", choices=("audio", "image"))
    parser.add_argument("--test", required=True, help="slug của đề")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument(
        "--match",
        choices=("number", "index", "order"),
        default="number",
        help=(
            "number: số trong tên file là số câu chính thức · "
            "index: là thứ tự trong part (cần --part) · "
            "order: không có số, xếp theo tên"
        ),
    )
    parser.add_argument("--part", type=int, choices=(1, 2, 3, 4), default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--accent", choices=sorted(AUDIO_ACCENTS), help="bắt buộc với audio")
    parser.add_argument("--source-url")
    parser.add_argument("--license")
    parser.add_argument("--attribution")
    parser.add_argument(
        "--alt-text",
        help="chữ thay ảnh — BẮT BUỘC với hình Part 3/4, để trống với ảnh Part 1",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="gắn đè lên ô đã có media (mặc định: bỏ qua ô đã có)",
    )
    args = parser.parse_args(argv)

    if not args.dir.is_dir():
        print(f"không có thư mục {args.dir}", file=sys.stderr)
        return 2
    if args.kind == "audio" and not args.accent:
        # Không mặc định: không ai ngoài người tải lên biết bản thu giọng gì, và
        # đoán hộ sẽ ghi một giá trị sai vào cột người học nhìn thấy.
        print("--accent là bắt buộc với audio", file=sys.stderr)
        return 2
    if args.kind == "image" and not (args.source_url and args.license and args.attribution):
        print("--source-url, --license và --attribution đều bắt buộc với ảnh", file=sys.stderr)
        return 2
    if args.kind == "image" and args.part in (3, 4) and not args.alt_text:
        # Hình Part 3/4 LÀ dữ liệu phải đọc mới trả lời được. Thiếu chữ thay ảnh
        # ở đó không phải bất tiện — đó là một câu người dùng máy đọc màn hình
        # không làm được. Khác Part 1, nơi để trống mới là đúng.
        print("--alt-text là bắt buộc với hình Part 3/4", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        test = session.scalar(select(PracticeTest).where(PracticeTest.slug == args.test))
        if test is None:
            print(f"không có đề {args.test!r}", file=sys.stderr)
            return 2

        if args.kind == "audio":
            slots = audio_slots(session, test)
        else:
            if args.part is None:
                print("--part là bắt buộc với ảnh (1, 3 hoặc 4)", file=sys.stderr)
                return 2
            slots = image_slots(session, test, args.part)
        if not slots:
            print(
                f"đề {args.test!r} chưa có câu Part 1-4 nào — dán nội dung trước, "
                f"media gắn vào câu đã tồn tại",
                file=sys.stderr,
            )
            return 2

        if args.part is not None:
            slots = [slot for slot in slots if slot.part == args.part]
        if args.match == "index" and args.part is None:
            # Không có --part thì "thứ tự trong part" không có nghĩa: danh sách ô
            # trải cả bốn part, và file thứ 10 của Part 2 sẽ rơi vào ô thứ 10
            # của cả đề.
            print("--match index cần --part", file=sys.stderr)
            return 2

        # Khớp trên danh sách ô ĐẦY ĐỦ, rồi mới bỏ ô đã có — không phải ngược lại.
        #
        # Lọc trước làm `--match index` sai ngay ở lần chạy thứ hai: chỉ số tra
        # theo vị trí, nên một ô đã đầy bị rút khỏi danh sách sẽ đẩy mọi ô sau nó
        # lên một bậc, và `2_x.mp3` rơi vào ô thứ ba. Khớp thành công, không báo
        # gì — và chạy lại sau một lần nhập dở là việc tài liệu bảo người ta làm.
        files = collect(args.dir, AUDIO_SUFFIXES if args.kind == "audio" else IMAGE_SUFFIXES)

        # Validate the actual audio container before matching/importing.
        # The dataset may use `.mp3` filenames for WAV/PCM bytes, so extension
        # alone cannot be trusted.
        probed: dict[Path, tuple[int, str, str]] = {}
        if args.kind == "audio":
            try:
                probed = validate_audio_files(files)
            except (ValueError, RuntimeError) as exc:
                print(f"\\nDừng validation audio: {exc}", file=sys.stderr)
                return 1

        pairs, extra, empty = match_files(files, slots, args.match)

        skipped = [] if args.overwrite else [pair for pair in pairs if pair[1].filled]
        if not args.overwrite:
            pairs = [pair for pair in pairs if not pair[1].filled]
        empty = [slot for slot in empty if not slot.filled]
        report(pairs, extra, empty, kind=args.kind, skipped=skipped)

        if args.dry_run:
            if args.kind == "audio":
                print("\nAudio validation:")
                for path in files:
                    duration_ms, actual_ext, mime_type = probed[path]
                    print(
                        f"  {path.name:<28} "
                        f"{actual_ext:<5} {duration_ms:>7} ms {mime_type}"
                    )
            print("\n(dry-run — chưa ghi gì)")
            return 0
        # Ô trống là BÌNH THƯỜNG với hình Part 3/4: chỉ vài cụm cuối mỗi part có
        # hình. Coi nó là lỗi ở đây sẽ khiến lệnh không bao giờ chạy được, và
        # người ta sẽ tắt phép kiểm cho cả những chỗ nó đang bảo vệ thật.
        partial = args.kind == "image" and args.part in (3, 4)
        if extra or (empty and not partial):
            # Dừng chứ không làm phần khớp được. Nhập một nửa để lại một đề
            # thiếu đúng vài bản thu, và chỗ thiếu chỉ lộ ra khi có người ngồi
            # làm tới đúng câu đó.
            print(
                "\nDừng: còn file thừa hoặc ô trống. Soát lại tên file, hoặc "
                "chạy --match order nếu thứ tự file khớp thứ tự câu.",
                file=sys.stderr,
            )
            return 1

        try:
            if args.kind == "audio":
                done = import_audio(session, pairs, args.accent, probed)
            else:
                done = import_images(
                    session,
                    pairs,
                    source_url=args.source_url,
                    license_name=args.license,
                    attribution=args.attribution,
                    alt_text=args.alt_text,
                )
            session.commit()
        except Exception as exc:
            session.rollback()
            print(f"\\nDừng import: {exc}", file=sys.stderr)
            return 1

    print(f"\nđã gắn {done} {args.kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
