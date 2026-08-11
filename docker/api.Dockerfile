# Ảnh API — hai tầng, chạy bằng người dùng thường (P2-6).
#
# **Không cài `gcc` và `libpq-dev`.** Bản cũ cài cả hai để biên dịch psycopg,
# nhưng dependency là `psycopg[binary]`: wheel đã đóng gói sẵn libpq, nên không
# có gì để biên dịch. Hai gói đó chưa bao giờ cần — chúng chỉ làm ảnh nặng thêm
# và mang một trình biên dịch C vào môi trường phục vụ request.
#
# Hai tầng để thứ dựng ra môi trường ảo không đi kèm vào ảnh cuối. Với dependency
# thuần wheel thì lợi ích nhỏ hơn trường hợp phải biên dịch, nhưng ranh giới vẫn
# đáng có: ngày nào thêm một gói cần biên dịch, chỗ để cài trình biên dịch đã
# nằm sẵn ở tầng builder và không ai phải nghĩ lại.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app/apps/api

COPY apps/api/pyproject.toml apps/api/uv.lock ./
# `--no-dev` và `--frozen`: ảnh production không mang pytest, và không bao giờ
# tự giải lại phụ thuộc — lockfile là nguồn sự thật, y như luật đã áp cho pnpm.
RUN uv sync --frozen --no-dev


FROM python:3.12-slim AS runtime

# `uv` vẫn có mặt ở tầng chạy, có chủ ý: cùng ảnh này phục vụ cả compose dev,
# nơi CMD bị ghi đè thành `uv run uvicorn --reload`. Bỏ nó đi sẽ tiết kiệm vài
# chục megabyte và làm hỏng luồng phát triển — không đáng.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Người dùng thường, không phải root. Một lỗ thực thi mã trong tiến trình phục
# vụ HTTP mà chạy bằng root thì kẻ tấn công có luôn cả container.
RUN useradd --create-home --uid 10001 toeic

WORKDIR /app/apps/api

# Môi trường ảo dựng ở tầng builder, chép nguyên sang. Đường dẫn phải TRÙNG với
# tầng builder: venv của Python ghi đường dẫn tuyệt đối vào script của nó, nên
# chép sang chỗ khác sẽ ra một venv trỏ vào hư không.
COPY --from=builder --chown=toeic:toeic /app/apps/api/.venv /app/apps/api/.venv
COPY --chown=toeic:toeic apps/api ./

COPY docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh
RUN chmod +x /usr/local/bin/api-entrypoint.sh

# `WORKDIR` tạo /app/apps/api bằng root, và `COPY --chown` chỉ đổi chủ NHỮNG THỨ
# NÓ CHÉP VÀO — không đổi chủ chính thư mục cha. Nên uid 10001 đọc được mọi thứ
# bên trong mà không tạo được gì mới, và `app/main.py` tạo `media/` ngay lúc
# import ở chế độ development thì đổ `PermissionError` trước khi app kịp tồn tại.
#
# Lỗi này KHÔNG hiện ra ở máy đã từng chạy pipeline nội dung: `apps/api/media`
# có sẵn trong build context nên nó được chép vào (đúng chủ), và `mkdir` thành
# no-op. Chỉ một lần checkout sạch mới lộ — tức là chỉ ở CI. Nay `.dockerignore`
# loại thư mục đó ra, nên hai môi trường dựng từ cùng một đầu vào.
RUN mkdir -p /app/apps/api/media && chown toeic:toeic /app/apps/api /app/apps/api/media

ENV PYTHONPATH=/app/apps/api \
    # `uv run` cần chỗ ghi cache; không có HOME ghi được thì nó đổ ở người dùng
    # thường. Trỏ vào thư mục của chính user thay vì để nó tự tìm.
    UV_CACHE_DIR=/home/toeic/.cache/uv \
    # Venv đã dựng sẵn — cấm `uv run` tự đồng bộ lại lúc khởi động. Không có cờ
    # này, một container khởi động chậm có thể đi giải lại phụ thuộc qua mạng,
    # và đó là thứ cuối cùng ta muốn ở đường khởi động production.
    UV_FROZEN=1

USER toeic

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
