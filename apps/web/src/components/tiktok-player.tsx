"use client";

/**
 * Khung xem video TikTok (học + sửa bài).
 *
 * Khác player YouTube (`listening-player`): TikTok embed KHÔNG có Player API
 * nên không seek từng câu, không báo giờ phát — chỉ xem toàn video. Bài
 * TikTok vì thế không có nghe-lại-từng-câu và follow timeline, đó là giới hạn
 * của TikTok chứ không phải thiếu sót UI. Iframe thuần, không cần script
 * nhúng của họ.
 *
 * TikTok dựng tường bot ngay trên endpoint embed ("overload-protect
 * triggered") với mạng bị gắn cờ — iframe lúc đó là khung chết mà trình duyệt
 * không cho mình đọc lỗi (cross-origin). Vì thế LUÔN có link mở ngoài bên
 * dưới: học không bao giờ kẹt vì khung nhúng.
 */
export function TiktokPlayerView({
  videoId,
  sourceUrl,
}: {
  videoId: string;
  /** Link xem gốc — lối thoát khi embed bị tường. */
  sourceUrl?: string;
}) {
  return (
    <div className="mx-auto w-full max-w-[300px]">
      {/* Video dọc 9:16 — khung 16:9 như YouTube là dải đen hai bên. */}
      <div className="aspect-[9/16] w-full overflow-hidden rounded border border-rule bg-recess">
        <iframe
          src={`https://www.tiktok.com/embed/v2/${videoId}`}
          title="Video TikTok"
          loading="lazy"
          allow="fullscreen; encrypted-media; picture-in-picture"
          allowFullScreen
          className="h-full w-full"
        />
      </div>
      {sourceUrl && (
        <p className="mt-1.5 text-center text-small text-ink-muted">
          Không xem được trong khung?{" "}
          <a
            href={sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="font-semibold text-action-ink underline"
          >
            Mở trên TikTok
          </a>
        </p>
      )}
    </div>
  );
}
