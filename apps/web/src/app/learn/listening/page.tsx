"use client";

import {
  API_ROUTES,
  type ListeningCaptionsPublic,
  type ListeningContentCreated,
  type ListeningContentSummary,
} from "@toeic-pilot/shared";
import { ArrowLeft, ArrowRight, Plus, Video } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { GuestNotice } from "@/components/guest-notice";
import {
  Alert,
  Button,
  EmptyState,
  FieldError,
  Input,
  Meter,
  Page,
  PageHeader,
  Panel,
  PanelLink,
  Select,
  SkeletonList,
  Textarea,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { resolveYouTubeUrl } from "@/lib/listening-source";
import { useRequireSession } from "@/lib/session";

const SOURCE_MESSAGE: Record<string, string> = {
  INVALID_URL: "Link chưa đúng — kiểm tra lại URL video YouTube.",
  UNSUPPORTED_SOURCE: "Mới chỉ nhận link YouTube, TikTok hẹn bản sau.",
  SOURCE_TYPE_MISMATCH: "Link và nguồn đã chọn không khớp. Thử lại từ đầu.",
  EMPTY_TITLE: "Đặt tên cho bài học để dễ tìm lại.",
  CAPTIONS_UNAVAILABLE: "Video này không có phụ đề công khai. Dán SRT/VTT bên dưới.",
  CAPTIONS_FETCH_FAILED: "Không lấy được phụ đề lúc này. Thử lại hoặc dán tay.",
  VIDEO_UNAVAILABLE: "YouTube không cho xem video này. Thử link khác.",
};

const SAMPLE_SRT = `1
00:00:00,000 --> 00:00:03,500
Hello everyone, welcome back.

2
00:00:03,500 --> 00:00:08,000
Today we're going to discuss the new schedule.
`;

type Step = { name: "url" } | { name: "detail"; videoId: string; url: string };

/* TẠM ẨN luồng tự tạo (paste URL + bài đã tạo) để hub chỉ còn thư viện biên
 * soạn — code giữ nguyên, bật lại bằng hằng này. `?create=1` là lối thoát cho
 * dev/e2e khi cờ đang tắt. */
const SHOW_CREATE = false;

/** Thumbnail card thư viện. YouTube có ảnh public theo ID; nguồn khác (sau
 * này) thì ô giữ chỗ — không đoán URL ảnh. */
function thumbnailFor(content: ListeningContentSummary): string | null {
  if (content.source_type === "youtube" && content.external_id) {
    return `https://i.ytimg.com/vi/${content.external_id}/hqdefault.jpg`;
  }
  return null;
}

/** Badge nền tảng góc thumbnail — chữ + glyph tự vẽ vì lucide bản này bỏ icon
 * brand. Sau này thêm TikTok thì thêm nhánh ở đây, một chỗ duy nhất. */
function PlatformBadge({ source }: { source: string }) {
  if (source !== "youtube") return null;
  return (
    <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded bg-black/70 px-1.5 py-0.5 text-label font-semibold text-white">
      <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden>
        <rect x="2" y="5" width="20" height="14" rx="4" fill="#FF0000" />
        <path d="M10 9.5v5l4.5-2.5z" fill="#fff" />
      </svg>
      YouTube
    </span>
  );
}

/** Tên video qua oEmbed (không cần API key). Hỏng thì user gõ tay — không bao
 * giờ chặn tạo bài vì không lấy được tiêu đề. Timeout riêng vì đây là fetch
 * thô ngoài apiFetch (không có timeout 30s của nó). */
async function fetchOEmbedTitle(canonicalUrl: string): Promise<string | null> {
  try {
    const res = await fetch(
      `https://www.youtube.com/oembed?url=${encodeURIComponent(canonicalUrl)}&format=json`,
      { signal: AbortSignal.timeout(8000) },
    );
    if (!res.ok) return null;
    const data = (await res.json()) as { title?: unknown };
    return typeof data.title === "string" && data.title.trim() ? data.title.trim() : null;
  } catch {
    return null;
  }
}

export default function ListeningLabPage() {
  // `useSearchParams` đòi Suspense bao ngoài (Next không dựng trang dùng nó mà
  // thiếu) — bọc ở đây để file page vẫn là một khối duy nhất.
  return (
    <Suspense
      fallback={
        <Page className="max-w-3xl">
          <SkeletonList rows={3} />
        </Page>
      }
    >
      <ListeningLabContent />
    </Suspense>
  );
}

function ListeningLabContent() {
  const { token } = useRequireSession();
  // Hook đứng riêng, KHÔNG gộp vào `SHOW_CREATE || ...` — short-circuit là gọi
  // có điều kiện, sai luật hooks.
  const params = useSearchParams();
  const showCreate = SHOW_CREATE || params.get("create") === "1";
  const router = useRouter();
  const [step, setStep] = useState<Step>({ name: "url" });
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  // Tiêu đề đang thuộc về video nào — đổi video thì ô tên reset theo (pattern
  // "điều chỉnh state trong render", không phải effect).
  const [titleFor, setTitleFor] = useState<string | null>(null);
  if (step.name === "detail" && titleFor !== step.videoId) {
    setTitleFor(step.videoId);
    setTitle("");
  }
  const [format, setFormat] = useState<"srt" | "vtt">("srt");
  const [transcript, setTranscript] = useState("");
  const [captionStatus, setCaptionStatus] = useState<"idle" | "loading" | "ok" | "fail">("idle");
  const [captionNote, setCaptionNote] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string[] | null>(null);
  const [created, setCreated] = useState<ListeningContentCreated | null>(null);
  const [busy, setBusy] = useState(false);
  const [mine, setMine] = useState<ListeningContentSummary[] | null>(null);
  const [library, setLibrary] = useState<ListeningContentSummary[] | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<ListeningContentSummary[]>(API_ROUTES.listeningContents, { token })
      .then(setMine)
      .catch(() => setMine([]));
    apiFetch<ListeningContentSummary[]>(API_ROUTES.listeningLibrary, { token })
      .then(setLibrary)
      .catch(() => setLibrary([]));
  }, [token]);

  // Có video mới thì thử lấy tên qua oEmbed. Chỉ điền khi ô vẫn trống — dùng
  // setTitle dạng hàm để không phải đọc `title` (đọc là phải khai deps, khai
  // là effect chạy lại mỗi chữ gõ, và chữ vừa gõ xong bị ghi đè ngay).
  useEffect(() => {
    if (step.name !== "detail") return;
    let alive = true;
    fetchOEmbedTitle(step.url).then((fetched) => {
      if (!alive || !fetched) return;
      setTitle((current) => (current.trim() ? current : fetched));
    });
    return () => {
      alive = false;
    };
  }, [step]);

  // Lấy phụ đề từ backend (backend gọi YouTube, trình duyệt không). Gọi từ
  // handler bấm nút — không phải effect — nên không có setState-trong-effect,
  // và mỗi lần bấm là một lần lấy có chủ ý, không phải tác dụng phụ của render.
  function fetchCaptions(url: string, authToken: string) {
    setCaptionStatus("loading");
    setCaptionNote(null);
    void apiFetch<ListeningCaptionsPublic>(API_ROUTES.listeningCaptions, {
      method: "POST",
      token: authToken,
      body: JSON.stringify({ url }),
    })
      .then((data) => {
        setFormat("vtt");
        setTranscript((current) => (current.trim() ? current : data.raw));
        if (data.title?.trim()) {
          setTitle((current) => (current.trim() ? current : data.title!.trim()));
        }
        setCaptionStatus("ok");
        setCaptionNote(
          data.kind === "asr"
            ? `Đã lấy phụ đề tự động (${data.language}, ${data.segment_count} câu). Nên đọc lại trước khi học.`
            : `Đã lấy phụ đề (${data.language}, ${data.segment_count} câu).`,
        );
      })
      .catch((err) => {
        setCaptionStatus("fail");
        if (err instanceof ApiError) {
          const detail = err.detail as { code?: unknown } | undefined;
          const code = typeof detail?.code === "string" ? detail.code : null;
          setCaptionNote(SOURCE_MESSAGE[code ?? ""] ?? err.message);
        } else {
          setCaptionNote(SOURCE_MESSAGE.CAPTIONS_FETCH_FAILED);
        }
      });
  }

  if (!token) {
    return (
      <Page className="max-w-3xl">
        <PageHeader eyebrow="Listening Lab" title="Học từ video thật" />
        <SkeletonList rows={3} />
      </Page>
    );
  }

  function goDetail() {
    const resolved = resolveYouTubeUrl(url);
    if (!resolved.ok) {
      setUrlError(SOURCE_MESSAGE[resolved.code] ?? "Link chưa đúng.");
      return;
    }
    setUrlError(null);
    setSubmitError(null);
    setCreated(null);
    setTranscript("");
    setCaptionStatus("idle");
    setCaptionNote(null);
    setStep({ name: "detail", videoId: resolved.source.videoId, url: resolved.source.url });
    if (token) fetchCaptions(resolved.source.url, token);
  }

  async function create() {
    if (step.name !== "detail" || busy || !token) return;
    setBusy(true);
    setSubmitError(null);
    try {
      const body = await apiFetch<ListeningContentCreated>(API_ROUTES.listeningContents, {
        method: "POST",
        token,
        body: JSON.stringify({
          source: { type: "youtube", url: step.url },
          title: title.trim(),
          transcript: { format, raw: transcript },
        }),
      });
      if (body.warnings.length > 0) {
        // Overlap timestamp vẫn học được nên không chặn — nhưng phải nói ra,
        // chứ im lặng đẩy sang bài học là giấu thông tin.
        setCreated(body);
      } else {
        router.push(`/learn/listening/${body.id}`);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { code?: unknown; errors?: unknown } | undefined;
        const code = typeof detail?.code === "string" ? detail.code : null;
        if (code === "INVALID_TRANSCRIPT" && Array.isArray(detail?.errors)) {
          setSubmitError((detail.errors as unknown[]).map(String));
        } else {
          setSubmitError([SOURCE_MESSAGE[code ?? ""] ?? err.message]);
        }
      } else {
        setSubmitError(["Không tạo được bài. Thử lại sau."]);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Listening Lab"
        title="Học từ video thật"
        description={
          showCreate
            ? "Dán link YouTube — hệ thống lấy phụ đề có timestamp nếu video có sẵn, rồi chép chính tả từng câu."
            : "Chọn một bài trong thư viện rồi chép chính tả từng câu."
        }
      />

      <GuestNotice className="mb-4" />

      {showCreate && (
        <>
          {/* Ba tab theo SPEC §4.1 — hai tab chưa tới lượt thì disabled công khai,
              không phải ẩn: user biết lộ trình mà không bấm vào chỗ vỡ. */}
          <div className="mb-4 flex gap-2" role="group" aria-label="Nguồn bài học">
            <Button size="sm" aria-pressed>
              YouTube
            </Button>
            <Button size="sm" variant="secondary" disabled title="Bản sau mới có">
              TikTok · sắp có
            </Button>
            <Button size="sm" variant="secondary" disabled title="Bản sau mới có">
              Tải lên · sắp có
            </Button>
          </div>

          {step.name === "url" ? (
            <Panel className="space-y-3 p-5">
              <label className="block">
                <span className="mb-1.5 block text-label font-semibold uppercase text-ink-muted">
                  Link video YouTube
                </span>
                <Input
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") goDetail();
                  }}
                  placeholder="https://www.youtube.com/watch?v=…"
                  inputMode="url"
                  aria-invalid={urlError !== null}
                />
              </label>
              {urlError && <FieldError>{urlError}</FieldError>}
              <Button onClick={goDetail}>
                Tiếp tục
                <ArrowRight size={16} strokeWidth={2} aria-hidden />
              </Button>
            </Panel>
          ) : (
            <div className="space-y-4">
              <Button variant="secondary" size="sm" onClick={() => setStep({ name: "url" })}>
                <ArrowLeft size={14} strokeWidth={2} aria-hidden />
                Đổi link khác
              </Button>

              <Panel className="flex gap-4 p-5">
                {/* Ảnh thumbnail ngoài không qua next/image được nếu chưa mở
                remotePatterns cho YouTube; ảnh trang trí, có link text cạnh bên. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`https://i.ytimg.com/vi/${step.videoId}/hqdefault.jpg`}
                  alt=""
                  width={160}
                  height={90}
                  className="h-[90px] w-40 shrink-0 rounded border border-rule object-cover"
                />
                <div className="min-w-0">
                  <p className="font-semibold">YouTube</p>
                  <a
                    href={step.url}
                    target="_blank"
                    rel="noreferrer"
                    className="break-all text-small text-action-ink underline"
                  >
                    {step.url}
                  </a>
                </div>
              </Panel>

              <Panel className="space-y-3 p-5">
                <label className="block">
                  <span className="mb-1.5 block text-label font-semibold uppercase text-ink-muted">
                    Tên bài học
                  </span>
                  <Input
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="VD: Business Meeting — New Schedule"
                    maxLength={512}
                  />
                </label>

                <div>
                  <span className="mb-1.5 block text-label font-semibold uppercase text-ink-muted">
                    Phụ đề có timestamp
                  </span>
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Select
                      value={format}
                      onChange={(event) => setFormat(event.target.value as "srt" | "vtt")}
                      aria-label="Định dạng phụ đề"
                    >
                      <option value="srt">SRT</option>
                      <option value="vtt">VTT</option>
                    </Select>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={captionStatus === "loading" || !token}
                      onClick={() => {
                        if (step.name !== "detail" || !token) return;
                        fetchCaptions(step.url, token);
                      }}
                    >
                      Lấy phụ đề YouTube
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setFormat("srt");
                        setTranscript(SAMPLE_SRT);
                      }}
                    >
                      <Plus size={14} strokeWidth={2} aria-hidden />
                      Chép mẫu thử
                    </Button>
                  </div>
                  {captionStatus === "loading" && (
                    <p className="mb-2 text-small text-ink-muted">Đang lấy phụ đề từ YouTube…</p>
                  )}
                  {captionNote && captionStatus === "ok" && (
                    <p className="mb-2 text-small text-ink-muted">{captionNote}</p>
                  )}
                  {captionNote && captionStatus === "fail" && (
                    <FieldError>{captionNote}</FieldError>
                  )}
                  <Textarea
                    value={transcript}
                    onChange={(event) => setTranscript(event.target.value)}
                    rows={8}
                    placeholder={"1\n00:00:00,000 --> 00:00:03,500\nHello everyone…"}
                    className="font-data"
                  />
                  <p className="mt-1.5 text-small text-ink-faint">
                    Ưu tiên phụ đề có trên YouTube. Không có thì dán SRT/VTT (cần giờ bắt đầu và giờ
                    kết thúc từng câu).
                  </p>
                </div>

                {submitError && (
                  <Alert tone="alert">
                    <ul className="list-disc space-y-0.5 pl-5">
                      {submitError.map((line, index) => (
                        <li key={index}>{line}</li>
                      ))}
                    </ul>
                  </Alert>
                )}

                {created ? (
                  <Alert tone="warn">
                    <p className="font-semibold">Đã tạo bài, nhưng phụ đề có chỗ chồng giờ:</p>
                    <ul className="mt-1 list-disc pl-5">
                      {created.warnings.map((line, index) => (
                        <li key={index}>{line}</li>
                      ))}
                    </ul>
                    <Link
                      href={`/learn/listening/${created.id}`}
                      className="mt-2 inline-block font-semibold text-action-ink underline"
                    >
                      Vào học luôn
                    </Link>
                  </Alert>
                ) : (
                  <Button
                    onClick={() => void create()}
                    disabled={busy || !transcript.trim() || captionStatus === "loading"}
                  >
                    {busy ? "Đang tạo…" : "Tạo bài học"}
                  </Button>
                )}
              </Panel>
            </div>
          )}
        </>
      )}

      <h2 className="mb-2 mt-8 text-subtitle">Thư viện bài có sẵn</h2>
      {library === null ? (
        <SkeletonList rows={2} />
      ) : library.length === 0 ? (
        <EmptyState
          title="Thư viện đang biên soạn"
          description="Đội ngũ đang chọn video và lời thoại. Quay lại sau nhé."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {library.map((content) => {
            const thumb = thumbnailFor(content);
            return (
              <PanelLink
                key={content.id}
                href={`/learn/listening/${content.id}`}
                className="group flex flex-col overflow-hidden p-0"
              >
                <span className="relative block">
                  {thumb ? (
                    /* Ảnh public của YouTube theo ID, không qua next/image được
                       nếu chưa mở remotePatterns (cùng lý do thumbnail ở bước
                       dán link). */
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={thumb}
                      alt=""
                      aria-hidden
                      width={480}
                      height={360}
                      loading="lazy"
                      className="aspect-video w-full border-b border-rule object-cover"
                    />
                  ) : (
                    <span
                      aria-hidden
                      className="grid aspect-video w-full place-items-center border-b border-rule bg-recess text-ink-faint"
                    >
                      <Video size={28} strokeWidth={1.5} />
                    </span>
                  )}
                  <PlatformBadge source={content.source_type} />
                </span>
                <span className="flex flex-1 flex-col p-3">
                  <span className="line-clamp-2 min-h-10 font-semibold leading-snug">
                    {content.title}
                  </span>
                  <span className="mt-2">
                    <Meter value={content.completed_count} max={content.segment_count} />
                  </span>
                  <span className="mt-1.5 font-data text-small text-ink-faint">
                    {content.completed_count}/{content.segment_count} câu đã đúng
                  </span>
                </span>
              </PanelLink>
            );
          })}
        </div>
      )}

      {showCreate && (
        <>
          <h2 className="mb-2 mt-8 text-subtitle">Bài đã tạo</h2>
          {mine === null ? (
            <SkeletonList rows={2} />
          ) : mine.length === 0 ? (
            <EmptyState
              title="Chưa có bài nào"
              description="Bài bạn tạo từ link YouTube sẽ nằm ở đây, kèm tiến độ từng bài."
            />
          ) : (
            <div className="space-y-2">
              {mine.map((content) => (
                <PanelLink
                  key={content.id}
                  href={`/learn/listening/${content.id}`}
                  className="flex items-center gap-3"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{content.title}</span>
                    <span className="mt-0.5 block text-small text-ink-muted">
                      {content.completed_count}/{content.segment_count} câu đã đúng
                    </span>
                  </span>
                </PanelLink>
              ))}
            </div>
          )}
        </>
      )}
    </Page>
  );
}
