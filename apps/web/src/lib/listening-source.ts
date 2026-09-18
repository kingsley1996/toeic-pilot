/**
 * Nhận diện URL paste ở phía trình duyệt — CHỈ để phản hồi tức thì (preview,
 * báo lỗi ngay khi gõ). Backend validate lại mọi thứ ở `POST
 * /listening/contents`, nên đây là bản mirror có chủ ý của
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

export type ResolvedTikTokSource = {
  /** ID số khi trích được ngay; null với link rút gọn (backend theo redirect
   * rồi mới biết ID — client không đoán). */
  videoId: string | null;
  /** Host chuẩn hoá về www, giữ nguyên path, bỏ query. */
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
const TIKTOK_SHORT_HOSTS = new Set(["vm.tiktok.com", "vt.tiktok.com"]);

const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
// TikTok video ID là số (thực tế 19 chữ số) — cùng độ nới với backend.
const TIKTOK_ID = /^\d{8,24}$/;

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

/** Trích TikTok video ID theo hình dạng path — mirror `_pick_tiktok` backend. */
function pickTikTokId(parts: string[]): string | null {
  let candidate: string | undefined;
  if (parts.length === 3 && parts[1] === "video" && parts[0]) {
    candidate = parts[2];
  } else if (parts.length === 2 && parts[0] === "video") {
    candidate = parts[1];
  } else if (parts.length === 2 && parts[0] === "embed") {
    candidate = parts[1];
  } else if (parts.length === 3 && parts[0] === "embed" && parts[1] === "v2") {
    candidate = parts[2];
  } else {
    return null;
  }
  return candidate && TIKTOK_ID.test(candidate) ? candidate : null;
}

export function resolveTikTokUrl(
  raw: string,
): { ok: true; source: ResolvedTikTokSource } | { ok: false; code: SourceErrorCode } {
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
  if (!TIKTOK_HOSTS.has(host)) return { ok: false, code: SOURCE_ERROR_UNSUPPORTED };

  const parts = parsed.pathname.split("/").filter(Boolean);
  if (TIKTOK_SHORT_HOSTS.has(host)) {
    // Link rút gọn: client không theo redirect được tin cậy — nhận hình dạng
    // rồi để backend resolve ID sau (backend mới là trọng tài, client không
    // được chặt hơn ở đây). Trống path thì link hỏng.
    if (parts.length === 0 || !parts[0]) return { ok: false, code: SOURCE_ERROR_INVALID };
    return { ok: true, source: { videoId: null, url: `https://${host}/${parts.join("/")}` } };
  }
  const videoId = pickTikTokId(parts);
  if (!videoId) return { ok: false, code: SOURCE_ERROR_INVALID };
  return { ok: true, source: { videoId, url: `https://www.tiktok.com/${parts.join("/")}` } };
}
