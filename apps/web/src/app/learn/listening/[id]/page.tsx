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

/** Rộng hơn bước tick (500ms) một chút: dừng lố qua mốc bắt đầu câu sau vài
 * chục ms vẫn tính là "đang ở mốc", highlight không chớp sang câu sau rồi về
 * trong lúc user chưa thao tác gì. */
const FOLLOW_EPS = 0.6;

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
  /* Câu video ĐANG phát tới — highlight + cuộn theo, ĐỘC LẬP với câu đang làm.
   * Cố ý không gộp: video chạy xuyên câu mà lôi cả bài tập theo thì chữ đang gõ
   * dở mất theo; bấm vào dòng nào thì bài tập mới nhảy theo (goTo dưới). */
  const [followId, setFollowId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rowRefs = useRef(new Map<string, HTMLButtonElement>());
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

  /* Cuộn list tới câu video đang phát. Trước early-return bên dưới: hook sau
   * `return` có điều kiện là lỗi luật lẫn lỗi React. */
  useEffect(() => {
    if (!followId) return;
    rowRefs.current.get(followId)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [followId]);

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
    if (index === activeIndex) {
      // Bấm lại đúng dòng đang chọn: start/end không đổi nên effect tự-phát
      // trong player không thấy gì — tín hiệu đếm riêng cho ca này.
      setReplaySeq((n) => n + 1);
      return;
    }
    setActiveIndex(index);
    // Highlight đi theo ngay, khỏi chờ tick (tick tới xác nhận lại giá trị
    // này nên không sợ lệch).
    const target = segments[index];
    if (target) setFollowId(target.id);
  }

  /* Nút "Tiếp tục" bấm ngay cuối câu đang làm: cả ba (video, list, bài tập)
   * cùng tiến sang câu kế — autoplay effect trong player (start/end đổi) phát
   * luôn câu mới. Câu cuối thì phát lại câu đó. Bài tập đổi theo vì user CHỦ
   * ĐỘNG tiến (khác với follow tự chạy khi xem — cái đó không được đụng tới
   * chữ đang gõ). */
  function advance() {
    if (activeIndex + 1 < segments.length) goTo(activeIndex + 1);
    else setReplaySeq((n) => n + 1);
  }

  /* Video tới đâu thì list theo tới đó: tìm câu chứa mốc giờ, highlight + cuộn
   * tới. Ngoài khoảng (đầu video, hết video) thì giữ highlight cũ — mất dấu còn
   * tệ hơn đứng yên. Dính biên: dừng NGAY mốc bắt đầu câu sau (vừa pause cuối
   * câu trước) thì ở yên câu trước — không thì highlight tự nhảy sang câu mới
   * dù user chưa thao tác gì. */
  function handleTime(playedSeconds: number) {
    const index = segments.findIndex(
      (segment) => playedSeconds >= segment.start && playedSeconds < segment.end,
    );
    if (index === -1) return;
    setFollowId((current) => {
      const id = segments[index]!.id;
      if (current === id) return current;
      if (
        index > 0 &&
        playedSeconds - segments[index]!.start < FOLLOW_EPS &&
        current === segments[index - 1]!.id
      ) {
        return current;
      }
      return id;
    });
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
            eyebrow={`YouTube · ${doneIds.size}/${segments.length} câu đã đúng`}
            title={content.title}
            description="Nghe lại từng câu rồi gõ những gì bạn nghe được."
          />

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
                    // MỘT highlight duy nhất: video đang phát tới đâu thì sáng
                    // tới đó; chưa phát gì thì sáng câu đang làm. Hai viền cam
                    // cùng lúc (bài tập một nơi, video một nơi) đọc thành lỗi.
                    const current = segment.id === (followId ?? segments[activeIndex]?.id);
                    return (
                      <li key={segment.id}>
                        <button
                          ref={(node) => {
                            if (node) rowRefs.current.set(segment.id, node);
                            else rowRefs.current.delete(segment.id);
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
