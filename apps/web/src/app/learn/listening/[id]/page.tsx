"use client";

import {
  API_ROUTES,
  type ListeningAttemptResult,
  type ListeningContentPublic,
} from "@toeic-pilot/shared";
import { CircleCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { DictationExercise } from "@/components/dictation-exercise";
import { GuestNotice } from "@/components/guest-notice";
import { ListeningPlayerView } from "@/components/listening-player";
import { Alert, EmptyState, Page, PageHeader, SkeletonList, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { formatTime } from "@/lib/listening-player";
import { useRequireSession } from "@/lib/session";

/** Một từ che thành `*` dài bằng đúng từ đó — cùng chuẩn `maskUnreached` của
 * dictation (nhìn độ dài đoán từ là một phần cuộc chơi, không phải lộ đáp án).
 * Chưa đúng thì không có diff để mask, nên mask thẳng từ transcript thô. */
function MaskedText({ text }: { text: string }) {
  return (
    <>
      {text.split(/\s+/).map((word, index) => (
        <span key={index} className="font-data text-ink-faint">
          {"*".repeat(word.length)}{" "}
        </span>
      ))}
    </>
  );
}

/** Ngưỡng dính biên cho follow tự động: vào sâu quá chừng này mới tính là sang
 * câu (tick 500ms luôn bắt được, còn dừng lố qua mốc vài chục ms thì ở yên).
 * Nhỏ hơn nữa là câu ngắn bị nhảy cóc (tick bước qua luôn cả câu). */
const BOUNDARY_EPS = 0.3;

/** Mili-giây hiện tại. Bọc ngoài component như `timeAgo` ở admin/users: rule
 * purity cấm gọi `Date.now()` trong render (kể cả trong hàm lồng), còn helper
 * ngoài này chỉ được gọi từ handler bấm/nộp — đúng chỗ thời gian sinh ra. */
function nowMs(): number {
  return Date.now();
}

/** Một bài Listening Lab: phát lại từng segment YouTube rồi chép chính tả. */
export default function ListeningLessonPage() {
  const { token } = useRequireSession();
  const contentId = String(useParams().id);
  const [content, setContent] = useState<ListeningContentPublic | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());
  // Đếm lượt phát-lại-cùng-câu (bấm lại dòng đang chọn, nút Tiếp tục ở câu
  // cuối): start/end không đổi nên player chỉ nghe được qua tín hiệu này.
  const [replaySeq, setReplaySeq] = useState(0);
  // Đếm lượt follow tự động đổi câu (video chạy/tua sang câu khác): player
  // phân biệt với bấm tay để KHÔNG seek/play theo (giữ nguyên trạng thái).
  const [followSeq, setFollowSeq] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const rowRefs = useRef(new Map<number, HTMLButtonElement>());
  // Hai ref cho follow tự động (handleTime dưới): mốc tick trước để phân biệt
  // tua-nhảy vs trôi-tới, và cửa sổ settle sau mỗi lần bấm đi. Đứng đây cùng
  // các ref khác — dưới early-return là sai luật hooks.
  const lastHandledRef = useRef(-1);
  const settleUntilRef = useRef(0);
  // Mốc tính thời gian làm từng câu — chỉ ghi trong handler chuyển câu và đọc
  // trong handler nộp bài. Không khởi tạo ở render (`Date.now()` là hàm impure)
  // và không đặt trong effect (setState đồng bộ trong effect cho thứ tính được
  // từ sự kiện bấm). Lần nộp đầu chưa chuyển câu lần nào thì mốc là lúc bấm
  // Kiểm tra — `?? Date.now()` ngay trong handler là hợp lệ.
  const segStartedAt = useRef<number | null>(null);

  const load = useCallback(
    (t: string) =>
      apiFetch<ListeningContentPublic>(API_ROUTES.listeningContent(contentId), { token: t })
        .then((data) => {
          setContent(data);
          // Seeding tiến độ từ server để F5 không mất câu đã đúng — lượt nộp
          // trong phiên thì submitSegment cập nhật tiếp vào set này.
          setDoneIds(new Set(data.completed_segment_ids));
        })
        .catch(() => setError("Không tải được bài này. Nó có thể đã bị xoá.")),
    [contentId],
  );

  useEffect(() => {
    if (token) void load(token);
  }, [token, load]);

  /* Cuộn list tới câu đang làm. Trước early-return bên dưới: hook sau `return`
   * có điều kiện là lỗi luật lẫn lỗi React. */
  useEffect(() => {
    rowRefs.current.get(activeIndex)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIndex]);

  if (!token || (!content && !error)) {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={5} />
      </Page>
    );
  }

  const segments = content?.segments ?? [];
  const active = segments[activeIndex] ?? null;
  const next = activeIndex + 1 < segments.length ? segments[activeIndex + 1] : undefined;

  function goTo(index: number) {
    segStartedAt.current = nowMs();
    // Mở cửa sổ settle: seek sắp bay, tick stale đọc giờ cũ trong lúc đó mà
    // tính là follow là lôi bài tập đi lung tung (xem handleTime).
    settleUntilRef.current = nowMs() + 1200;
    if (index === activeIndex) {
      // Bấm lại đúng dòng đang chọn: start/end không đổi nên effect tự-phát
      // trong player không thấy gì — tín hiệu đếm riêng cho ca này.
      setReplaySeq((n) => n + 1);
      return;
    }
    setActiveIndex(index);
  }

  /* Follow tự động (video chạy/tua sang câu khác): đổi bài tập theo NHƯNG
   * không seek không phát — bump followSeq để player biết mà bỏ qua autoplay
   * (xem followSignal). Bấm tay (goTo trên) thì vẫn autoplay như cũ. */
  function followTo(index: number) {
    segStartedAt.current = nowMs();
    setActiveIndex(index);
    setFollowSeq((n) => n + 1);
  }

  /* Nút "Tiếp tục" bấm ngay cuối câu đang làm: cả ba (video, list, bài tập)
   * cùng tiến sang câu kế — autoplay effect trong player (start/end đổi) phát
   * luôn câu mới. Câu cuối thì phát lại câu đó. Cùng đường với follow-advance
   * dưới: mọi ca đổi câu đều qua goTo/followTo, không có đường tắt. */
  function advance() {
    if (activeIndex + 1 < segments.length) goTo(activeIndex + 1);
    else setReplaySeq((n) => n + 1);
  }

  /* Video tới đâu thì CẢ BÀI theo tới đó (list highlight + bài tập + cuộn):
   * một state duy nhất, không có chuyện list một nơi bài tập một nẻo. Tìm câu
   * chứa mốc giờ; ngoài khoảng (đầu video, hết video) thì đứng yên.
   *
   * Dính biên: TRÔI tới ngay mốc bắt đầu câu sau (vừa pause cuối câu trước)
   * thì ở yên câu trước — không thì vừa dừng đã tự nhảy sang câu mới dù user
   * chưa thao tác gì. Nhưng TUA tới (nhảy giờ) thì đi ngay kể cả trúng biên:
   * đó là chủ ý của user, không phải trôi tự nhiên. Hai ca phân biệt bằng độ
   * nhảy so với tick trước.
   *
   * Đánh đổi có chủ ý: chữ đang gõ dở mất theo khi video tự chạy qua câu —
   * nhưng video chỉ qua câu khi user bấm phát/xem (hành động đi tiếp), còn bài
   * đã nộp thì server giữ, không mất gì thật. */
  function handleTime(playedSeconds: number) {
    // Trong cửa sổ settle sau bấm đi: seek đang bay, tick đọc giờ CŨ — tính là
    // follow là lôi bài tập đi lung tung.
    if (nowMs() < settleUntilRef.current) return;
    const previous = lastHandledRef.current;
    lastHandledRef.current = playedSeconds;
    const index = segments.findIndex(
      (segment) => playedSeconds >= segment.start && playedSeconds < segment.end,
    );
    if (index === -1 || index === activeIndex) return;
    const jumped = Math.abs(playedSeconds - previous) > 1.5;
    if (!jumped && playedSeconds - segments[index]!.start < BOUNDARY_EPS) return;
    followTo(index);
  }

  /** Ghi lượt làm về attempts của segment — cũng là chỗ duy nhất đánh dấu câu
   * đã đúng (server phán, không phải trình duyệt), và tính thời gian làm. */
  async function submitSegment(segmentId: string, text: string): Promise<unknown> {
    if (!token || !content) return null;
    const result = await apiFetch<ListeningAttemptResult>(
      API_ROUTES.listeningAttempts(content.id),
      {
        method: "POST",
        token,
        body: JSON.stringify({
          segment_id: segmentId,
          answer: text,
          time_spent_seconds: Math.max(
            0,
            Math.round((nowMs() - (segStartedAt.current ?? nowMs())) / 1000),
          ),
        }),
      },
    );
    if (result.is_correct) {
      setDoneIds((current) => new Set(current).add(segmentId));
    }
    return result;
  }

  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={[{ href: "/learn/listening", label: "Listening Lab" }]} />
      {error && <Alert>{error}</Alert>}

      {content && (
        <>
          <PageHeader
            eyebrow={`${content.source_type === "tiktok" ? "TikTok" : "YouTube"} · ${doneIds.size}/${segments.length} câu đã đúng`}
            title={content.title}
            description="Nghe lại từng câu rồi gõ những gì bạn nghe được."
          />
          {/* Ghi nguồn: lời thoại thuộc về video gốc — học ở đây, xem gốc ở đây. */}
          <p className="mb-4 text-small text-ink-muted">
            Nguồn video gốc:{" "}
            <a
              href={content.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-action-ink underline"
            >
              {content.source_type === "tiktok" ? "TikTok" : "YouTube"} ↗
            </a>
          </p>

          <GuestNotice className="mb-4" />

          {segments.length === 0 && (
            <EmptyState
              title="Bài này chưa có câu nào"
              description="Transcript lúc tạo không còn segment nào hợp lệ."
            />
          )}

          {segments.length > 0 && active && (
            /* Video trái, transcript phải (mobile xếp chồng, video trước) —
               list có chiều cao riêng để follow có chỗ cuộn tới. */
            <div className="mb-4 grid items-start gap-4 lg:grid-cols-5">
              <div className="lg:col-span-3">
                {content.external_id ? (
                  /* KHÔNG `key` theo câu: remount là dựng lại iframe (video
                      chớp + load lại, cảm giác như reload trang). Một player
                      sống suốt bài, đổi câu chỉ seek — effect tự-phát-lại
                      trong `ListeningPlayerView` lo phần còn lại. */
                  <ListeningPlayerView
                    videoId={content.external_id}
                    start={active.start}
                    end={active.end}
                    stops={segments.map((segment) => segment.end)}
                    startLabel={
                      activeIndex === 0
                        ? "Bắt đầu"
                        : activeIndex + 1 < segments.length
                          ? "Tiếp tục"
                          : "Nghe lại"
                    }
                    onAdvance={advance}
                    replaySignal={replaySeq}
                    followSignal={followSeq}
                    onTimeUpdate={handleTime}
                  />
                ) : (
                  <Alert tone="warn">Bài này thiếu ID video nên không phát được.</Alert>
                )}
              </div>

              <section aria-label="Transcript" className="rounded border border-rule lg:col-span-2">
                <h2 className="border-b border-rule px-4 py-2 text-label font-semibold uppercase text-ink-muted">
                  Transcript · {segments.length} câu
                </h2>
                {/* List cuộn độc lập để follow (effect trên) có chỗ mà cuộn tới —
                    tràn trang thì `nearest` thành vô nghĩa. */}
                <ol className="max-h-72 space-y-1 overflow-y-auto p-2 lg:max-h-[430px]">
                  {segments.map((segment, index) => {
                    const done = doneIds.has(segment.id);
                    // MỘT trạng thái hiện tại duy nhất: chính là câu đang làm
                    // (= câu video đang phát tới, vì bài tập bám playback).
                    const current = index === activeIndex;
                    return (
                      <li key={segment.id}>
                        <button
                          ref={(node) => {
                            if (node) rowRefs.current.set(index, node);
                            else rowRefs.current.delete(index);
                          }}
                          type="button"
                          onClick={() => goTo(index)}
                          aria-current={current ? "true" : undefined}
                          title={`Câu ${index + 1} · ${done ? "đã đúng" : "chưa đúng"}`}
                          className={cx(
                            "flex w-full items-baseline gap-2 rounded border px-3 py-2 text-left text-body transition-colors",
                            current
                              ? "border-action bg-action-tint text-action-ink"
                              : done
                                ? "border-ok"
                                : "border-transparent hover:bg-recess",
                          )}
                        >
                          <span className="shrink-0 font-data text-small text-ink-faint">
                            #{index + 1}
                          </span>
                          <span className="shrink-0 font-data text-small text-ink-faint">
                            {formatTime(segment.start)}
                          </span>
                          <span className="min-w-0 flex-1">
                            {done ? segment.text : <MaskedText text={segment.text} />}
                          </span>
                          {done && (
                            <CircleCheck
                              size={15}
                              strokeWidth={2.5}
                              aria-hidden
                              className="shrink-0"
                            />
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ol>
              </section>
            </div>
          )}

          {active && (
            <DictationExercise
              key={active.id}
              item={{
                id: active.id,
                transcript: active.text,
                word_count: active.text.split(/\s+/).length,
              }}
              submitAnswer={(text) => submitSegment(active.id, text)}
              onNext={next ? () => goTo(activeIndex + 1) : undefined}
              nextLabel="Câu tiếp theo"
              advanceOnEnter={false}
            />
          )}
        </>
      )}
    </Page>
  );
}
