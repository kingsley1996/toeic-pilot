# Ảnh riêng cho worker TTS — CỐ Ý không dùng chung với `api.Dockerfile`.
#
# Ảnh API dựng `--no-dev` không có extra `content`, và không có ffmpeg. Đó là
# ràng buộc chứ không phải thiếu sót: `app/main.py` không được import
# `app.content` (PHASE2-AUDIO §A4.1), và `tests/test_content_isolation.py` bắt
# vi phạm trong một subprocess dưới một giây.
#
# Gộp hai ảnh làm một sẽ phá đúng ranh giới đó — không phải hôm nay, mà vào ngày
# ai đó thấy `app.content` đã sẵn trong ảnh và import nó vào một request handler
# "cho tiện". Lúc ấy production có thêm edge-tts, ffmpeg, và một lệnh gọi mạng
# nằm trên đường phục vụ request.
#
# Cái giá là một ảnh nữa phải dựng. Cái được là ranh giới có hình dạng vật lý
# thay vì chỉ là một quy ước người ta phải nhớ.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app/apps/api

# ffmpeg là điều kiện tiên quyết của MÁY SOẠN NỘI DUNG, cùng loại với "phải có
# mạng để gọi edge-tts" — xem `app/content/audio_join.py`. Chỉ ảnh này cần.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --extra content

COPY apps/api ./

ENV PYTHONPATH=/app/apps/api

# Không migrate, không mở cổng. Worker không sở hữu schema và không phục vụ ai;
# `api-entrypoint.sh` chạy `alembic upgrade head` và đó phải là một chỗ duy nhất.
CMD ["uv", "run", "python", "-m", "app.content.tts_worker"]
