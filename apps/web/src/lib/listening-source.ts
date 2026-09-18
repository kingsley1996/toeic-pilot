/**
 * Nhận diện URL YouTube paste ở phía trình duyệt — CHỈ để phản hồi tức thì
 * (preview embed, báo lỗi ngay khi gõ). Backend validate lại mọi thứ ở
 * `POST /listening/contents`, nên đây là bản mirror có chủ ý của
 * `apps/api/app/services/listening_source.py`: sửa một bên thì sửa cả hai.
 */

export const SOURCE_ERROR_INVALID = "INVALID_URL";
export const SOURCE_ERROR_UNSUPPORTED = "UNSUPPORTED_SOURCE";

export type SourceErrorCode = typeof SOURCE_ERROR_INVALID | typeof SOURCE_ERROR_UNSUPPORTED;

export type ResolvedYouTubeSource = {
  videoId: string;
  /** URL chuẩn để embed/preview — cùng dạng backend lưu vào `source_url`. */
  url: string;
};

const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "music.youtube.com",
  "youtu.be",
  "www.youtu.be",
]);

const TIKTOK_HOSTS = new Set(["tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"]);

const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;

/** Trích video ID theo hình dạng path. Không khớp hình quen thì null — không
 * cắt bừa một đoạn path làm ID rồi để player kẹt. */
function pickId(parts: string[], query: URLSearchParams): string | null {
  if (
    parts.length === 2 &&
    (parts[0] === "embed" || parts[0] === "shorts" || parts[0] === "live")
  ) {
    return parts[1] ?? null;
  }
  if (parts[0] === "watch") {
    return query.get("v");
  }
  // Như backend: host đã là YouTube thì đoạn path đơn lẻ là ứng viên ID
  // (youtu.be/<id>); đúng/sai do regex 11 ký tự phán sau.
  return parts.length === 1 ? (parts[0] ?? null) : null;
}

export function resolveYouTubeUrl(
  raw: string,
): { ok: true; source: ResolvedYouTubeSource } | { ok: false; code: SourceErrorCode } {
  const text = raw.trim();
  if (!text) return { ok: false, code: SOURCE_ERROR_INVALID };

  let parsed: URL;
  try {
    parsed = new URL(text.includes("://") ? text : `https://${text}`);
  } catch {
    return { ok: false, code: SOURCE_ERROR_INVALID };
  }
  const host = parsed.hostname.toLowerCase();
  if (!host.includes(".")) return { ok: false, code: SOURCE_ERROR_INVALID };
  // TikTok nhận diện đúng rồi từ chối lịch sự (user cần biết link họ đúng mà
  // tính năng chưa có); domain lạ cũng UNSUPPORTED — khác link hỏng (INVALID).
  if (TIKTOK_HOSTS.has(host) || !YOUTUBE_HOSTS.has(host)) {
    return { ok: false, code: SOURCE_ERROR_UNSUPPORTED };
  }

  const videoId = pickId(parsed.pathname.split("/").filter(Boolean), parsed.searchParams);
  if (!videoId || !VIDEO_ID.test(videoId)) return { ok: false, code: SOURCE_ERROR_INVALID };

  return {
    ok: true,
    source: { videoId, url: `https://www.youtube.com/watch?v=${videoId}` },
  };
}
