"""Ghép nhiều lượt nói thành một clip, mỗi lượt một giọng.

Đây là thứ gỡ `MEDIA-PIPELINE` §10.2 — *"không sinh được clip nhiều giọng ⇒
Part 2 và Part 3 bất khả thi"*. Ghi chú đó nói đúng thứ còn thiếu: **bước ghép
audio**, và rằng repo cố ý không có `ffmpeg`.

"Cố ý không có ffmpeg" vẫn đúng ở chỗ nó cần đúng: **ảnh production không có
ffmpeg và không cần**. Module này nằm trong `app/content/`, sau extra `content`,
cùng chỗ với edge-tts — nên ffmpeg là điều kiện tiên quyết của MÁY SOẠN NỘI
DUNG, đúng loại với "phải có mạng để gọi edge-tts". Không byte nào của nó đi vào
đường chạy lúc có request.

Cách ghép: nối ở mức khung (`-c copy`), **không** giải mã rồi mã hoá lại. Mã lại
một lần thì tai người không nghe ra, nhưng nó thêm một thế hệ mất mát vào thứ
sẽ còn được xử lý tiếp, và quan trọng hơn: nối `-c copy` chỉ đúng khi mọi đoạn
cùng tham số, nên ta **đo tham số của lượt đầu rồi sinh khoảng lặng khớp theo**
thay vì hy vọng chúng trùng nhau.
"""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Sai số cho phép khi đối chiếu độ dài file ra với tổng độ dài mong đợi.
#
# Không đặt chặt được: biên khung mp3 khoảng 24 ms ở 24 kHz, và mỗi lần nối lại
# làm tròn lên biên khung, nên sai số tích luỹ theo số đoạn. Mục đích của phép
# kiểm này KHÔNG phải đo chính xác — nó để bắt hỏng nặng, kiểu file ra chỉ chứa
# lượt đầu tiên, thứ mà `-c copy` có thể tạo ra mà không báo lỗi.
_TOLERANCE_BASE_MS = 200
_TOLERANCE_PER_SEGMENT_MS = 80


class FFmpegMissing(RuntimeError):
    """ffmpeg/ffprobe không có trên máy này."""


class JoinFailed(RuntimeError):
    """ffmpeg chạy nhưng cho ra thứ không dùng được."""


@dataclass(frozen=True)
class AudioParams:
    sample_rate: int
    channels: int
    bit_rate: int
    duration_ms: int


def require_ffmpeg() -> None:
    """Kiểm tra sớm, với thông báo nói được cách sửa.

    Gọi ở đầu lượt chạy chứ không để lỗi bật ra ở đoạn hội thoại thứ tư mươi:
    một lượt sinh nội dung dài mà chết giữa chừng vì thiếu công cụ là lãng phí
    cả phần đã gọi lên edge-tts.
    """
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise FFmpegMissing(
            f"cần {' và '.join(missing)} để ghép clip nhiều giọng (Part 2/3). "
            f"macOS: brew install ffmpeg · Debian/Ubuntu: apt install ffmpeg. "
            f"Chỉ máy soạn nội dung mới cần; ảnh production thì không."
        )


def probe(path: Path) -> AudioParams:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate,channels,bit_rate:format=duration,bit_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(result)
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}

    duration = fmt.get("duration")
    if duration is None:
        raise JoinFailed(f"ffprobe không đọc được độ dài của {path.name}")

    # `bit_rate` của stream vắng mặt ở một số file; format-level luôn có.
    bit_rate = stream.get("bit_rate") or fmt.get("bit_rate") or "48000"
    return AudioParams(
        sample_rate=int(stream.get("sample_rate") or 24_000),
        channels=int(stream.get("channels") or 1),
        bit_rate=int(bit_rate),
        duration_ms=int(round(float(duration) * 1000)),
    )


def join_turns(parts: list[bytes], gap_ms: int) -> bytes:
    """Nối các clip lượt nói, chèn `gap_ms` im lặng giữa chúng.

    Trả về mp3 hoàn chỉnh. Ném `JoinFailed` nếu file ra không dài như mong đợi —
    xem ghi chú ở `_TOLERANCE_*` về lý do phép kiểm này tồn tại.
    """
    if not parts:
        raise JoinFailed("không có lượt nói nào để ghép")
    if len(parts) == 1 and gap_ms <= 0:
        return parts[0]

    require_ffmpeg()

    with tempfile.TemporaryDirectory(prefix="toeic-join-") as tmp:
        workdir = Path(tmp)
        turn_paths: list[Path] = []
        for index, payload in enumerate(parts):
            path = workdir / f"turn-{index:03d}.mp3"
            path.write_bytes(payload)
            turn_paths.append(path)

        measured = [probe(path) for path in turn_paths]
        params = measured[0]
        expected_ms = sum(item.duration_ms for item in measured)

        # Mọi đoạn phải cùng tần số lấy mẫu và số kênh, nếu không `-c copy` cho
        # ra một file mà ffmpeg KHÔNG báo lỗi và ffprobe vẫn đọc ra độ dài gần
        # đúng — nhưng phần sau phát sai tốc độ. Đã thử thật: nối 24 kHz mono
        # với 44.1 kHz stereo lọt qua cả phép kiểm độ dài bên dưới. Nên tham số
        # phải được kiểm THẲNG, không suy ra từ triệu chứng.
        uniform = all(
            (item.sample_rate, item.channels) == (params.sample_rate, params.channels)
            for item in measured
        )

        segments: list[Path] = []
        if gap_ms > 0:
            silence = _make_silence(workdir, params, gap_ms)
            expected_ms += gap_ms * (len(turn_paths) - 1)
            for index, path in enumerate(turn_paths):
                if index:
                    segments.append(silence)
                segments.append(path)
        else:
            segments = list(turn_paths)

        listing = workdir / "segments.txt"
        # Trích dẫn theo cú pháp của concat demuxer. Tên file ở đây do ta đặt và
        # chỉ gồm chữ với số, nhưng vẫn viết đúng cú pháp để không tạo ra một
        # cái bẫy cho người sau đổi cách đặt tên.
        listing.write_text("".join(f"file '{path.name}'\n" for path in segments), encoding="utf-8")

        out = workdir / "joined.mp3"
        codec = (
            ["-c", "copy"]
            if uniform
            # Không đồng nhất thì mã lại về tham số của lượt đầu. Trường hợp
            # thật của nó là trộn bản thu người thật vào giữa các lượt TTS —
            # chính là đường vòng ADR-006 §5 nhắc tới — và ở đó một thế hệ mất
            # mát là cái giá đúng để trả, so với việc từ chối ghép.
            else [
                "-c:a",
                "libmp3lame",
                "-b:a",
                str(params.bit_rate),
                "-ar",
                str(params.sample_rate),
                "-ac",
                str(params.channels),
            ]
        )
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                *codec,
                str(out),
            ],
            cwd=workdir,
        )

        if not out.is_file() or out.stat().st_size == 0:
            raise JoinFailed("ffmpeg không tạo ra file nào")

        actual_ms = probe(out).duration_ms
        tolerance = _TOLERANCE_BASE_MS + _TOLERANCE_PER_SEGMENT_MS * len(segments)
        if abs(actual_ms - expected_ms) > tolerance:
            raise JoinFailed(
                f"clip ghép xong dài {actual_ms} ms, mong đợi ~{expected_ms} ms "
                f"(sai số cho phép {tolerance} ms). Thường là dấu hiệu các đoạn "
                f"không cùng tham số nên `-c copy` cho ra file hỏng."
            )
        return out.read_bytes()


def _make_silence(workdir: Path, params: AudioParams, gap_ms: int) -> Path:
    """Khoảng lặng mã hoá theo ĐÚNG tham số của lượt nói đầu tiên.

    Đây là chỗ khiến `-c copy` an toàn. Dùng một file im lặng dựng sẵn ở tần số
    khác là cách nhanh nhất để có một clip nối xong nghe méo hoặc chạy sai tốc
    độ, mà ffmpeg không hề báo lỗi.
    """
    silence = workdir / "gap.mp3"
    layout = "mono" if params.channels == 1 else "stereo"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={params.sample_rate}:cl={layout}",
            "-t",
            f"{gap_ms / 1000:.3f}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            f"{params.bit_rate}",
            str(silence),
        ]
    )
    return silence


def _run(command: list[str], cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True)
    except FileNotFoundError as error:
        raise FFmpegMissing(f"không tìm thấy {command[0]}") from error
    except subprocess.CalledProcessError as error:
        raise JoinFailed(f"{command[0]} lỗi: {error.stderr.strip()[:400]}") from error
    return completed.stdout
