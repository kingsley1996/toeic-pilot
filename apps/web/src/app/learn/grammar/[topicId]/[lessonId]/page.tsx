"use client";

import { API_ROUTES, type GrammarLessonDetail, type GrammarTopicDetail } from "@toeic-pilot/shared";
import { ArrowRight, BookOpen, Check, PenLine } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { GrammarQuestionCard } from "@/components/grammar-question-card";
import { GuestNotice } from "@/components/guest-notice";
import { MarkdownLite } from "@/components/markdown-lite";
import { Alert, Button, cx, Page, PageHeader, Panel, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { getSidebarState, setSidebarState } from "@/lib/sidebar";
import { useSession } from "@/lib/session";

/**
 * Tầng 3: một bài học — `theory` là trang lý thuyết, `practice` là màn drill.
 *
 * Bốn thứ chỉ trang này có:
 * - Sidebar chính TỰ thu thành dải icon khi vào bài: người học đang đọc tài
 *   liệu, không đang điều hướng app. State cũ được khôi phục khi rời trang —
 *   thu sidebar là của riêng chế độ đọc, không phải cài đặt của họ bị ghi đè.
 * - Cột bài học cùng topic, ĐÚNG style sidebar của trang (cùng border, cùng
 *   item, cùng sticky dưới header): hai cột cạnh nhau mà hai kiểu khác nhau là
 *   hai hệ thiết kế trên một màn hình.
 * - Breadcrumb sticky trên đầu nội dung và thanh tiến độ sticky dưới chân — cả
 *   hai chỉ trong phạm vi cột nội dung, không lấn qua hai sidebar.
 * - Practice có đủ nút Hoàn thành / Bỏ hoàn thành như mọi lesson — làm đúng hết
 *   câu chỉ là thông tin trên thanh, dấu do người học tự bấm.
 */

/**
 * Cache cấp module, sống qua cả lần dựng lại của trang khi đổi bài.
 *
 * Không phải tối ưu băng thông — mỗi bài vẫn được fetch lại như cũ, cache chỉ
 * để HIỆN NGAY nội dung đã biết trong lúc chờ. Không có nó, mỗi cú bấm chuyển
 * bài là một nhịp skeleton thay toàn màn hình, và đọc như trang hỏng chứ không
 * như đang tải.
 */
const lessonCache = new Map<string, GrammarLessonDetail>();
const topicCache = new Map<string, GrammarTopicDetail>();

/** `/learn/grammar/{topic}/{lesson}` — 5 đoạn. */
function isLessonPath(path: string): boolean {
  const parts = path.split("?")[0].split("/");
  return parts.length === 5 && parts[1] === "learn" && parts[2] === "grammar";
}

export default function GrammarLessonPage() {
  const { status, token } = useSession();
  const params = useParams();
  const topicId = String(params.topicId);
  const lessonId = String(params.lessonId);
  const [lesson, setLesson] = useState<GrammarLessonDetail | null>(
    () => lessonCache.get(lessonId) ?? null,
  );
  const [topic, setTopic] = useState<GrammarTopicDetail | null>(
    () => topicCache.get(topicId) ?? null,
  );
  const [error, setError] = useState<string | null>(null);
  // Câu vừa được làm đúng TRONG PHIÊN này, cộng vào số `completed` của server —
  // để thanh đáy nhích từng câu một thay vì đứng yên tới lúc tải lại trang.
  // Mang theo id của bài: đổi bài là bộ đếm tự về 0 mà không cần effect reset
  // (lint `set-state-in-effect` chặn kiểu đó, và nó cũng thừa).
  const [justCorrect, setJustCorrect] = useState<{ lessonId: string; ids: Set<string> }>({
    lessonId: "",
    ids: new Set(),
  });

  useEffect(() => {
    apiFetch<GrammarLessonDetail>(API_ROUTES.grammarLesson(lessonId), {
      token: token ?? undefined,
    })
      .then((data) => {
        lessonCache.set(lessonId, data);
        setLesson(data);
      })
      .catch(() => setError("Không tải được bài học này."));
    apiFetch<GrammarTopicDetail>(API_ROUTES.grammarTopic(topicId), {
      token: token ?? undefined,
    })
      .then((data) => {
        topicCache.set(topicId, data);
        setTopic(data);
      })
      .catch(() => {});
  }, [lessonId, topicId, token]);

  useEffect(() => {
    const previous = getSidebarState();
    setSidebarState("collapsed");
    return () => {
      // Đi sang bài KHÁC: đừng khôi phục — instance mới sẽ thu tiếp, và nhả
      // "expanded" giữa hai lần mount chính là cái nhấp nháy mà người học thấy.
      if (!isLessonPath(window.location.pathname)) setSidebarState(previous);
    };
  }, []);

  /*
   * Dấu hoàn thành phải sáng/tắt trên CỘT BÀI HỌC ngay khi bấm — người học
   * vừa thao tác xong thì nhìn thấy-liền-tay, và tick của bài hiện tại trong
   * cột là chỗ họ đo "mình tới đâu". Vì vậy cả hai hàm đều sửa `topic` (state
   * + cache) cùng lúc với `lesson`, không chờ fetch lại.
   */
  function flipInTopic(lessonId: string, completed: boolean) {
    setTopic((prev) => {
      if (!prev) return prev;
      const next = {
        ...prev,
        lessons: prev.lessons.map((sibling) =>
          sibling.id === lessonId ? { ...sibling, completed } : sibling,
        ),
        completed_lesson_count: Math.max(0, prev.completed_lesson_count + (completed ? 1 : -1)),
      };
      topicCache.set(prev.id, next);
      return next;
    });
  }

  function markComplete() {
    if (!token || !shown) return;
    // Một hàng theo PK (user, lesson) — bấm đúp vẫn là một lần hoàn thành, nên
    // client lạc quan bật cờ ngay khi gọi, không chờ đọc lại.
    void apiFetch(API_ROUTES.grammarLessonComplete(shown.id), { method: "POST", token }).catch(() =>
      setError("Không đánh dấu được — thử lại."),
    );
    const updated = { ...shown, completed: true };
    lessonCache.set(shown.id, updated);
    setLesson(updated);
    flipInTopic(shown.id, true);
  }

  function unmarkComplete() {
    if (!token || !shown) return;
    void apiFetch(API_ROUTES.grammarLessonComplete(shown.id), {
      method: "DELETE",
      token,
    }).catch(() => setError("Không bỏ được dấu — thử lại."));
    const updated = { ...shown, completed: false };
    lessonCache.set(shown.id, updated);
    setLesson(updated);
    flipInTopic(shown.id, false);
  }

  /*
   * Suy ra lúc render, không phải setState trong effect — lint
   * `set-state-in-effect` chặn cách sau, và nó cũng đúng hơn: bài đang tải
   * được hiển thị từ cache nếu từng xem, ngược lại giữ bài cũ cho tới khi bài
   * mới về. Đổi bài vì thế không bao giờ có một khung rỗng/skeleton giữa chừng;
   * thanh đáy tác động đúng vào bài ĐANG hiện trên màn hình.
   */
  const shown = lesson && lesson.id === lessonId ? lesson : (lessonCache.get(lessonId) ?? lesson);

  if (status === "loading" || (!shown && !error)) {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  const isPractice = shown?.kind === "practice";
  const fresh = justCorrect.lessonId === lessonId ? justCorrect.ids : new Set<string>();
  const answeredCorrect =
    shown?.questions.filter((q) => q.completed || fresh.has(q.id)).length ?? 0;
  // Hoàn thành là dấu tay của người học với CẢ HAI loại — làm đúng hết câu chỉ
  // là thông tin trên thanh, không tự bật dấu.
  const lessonDone = Boolean(shown?.completed);

  return (
    <div className="flex min-h-[calc(100dvh-4rem)] flex-col lg:flex-row">
      {/* Mobile: dải bài học NGANG cuộn được ngay trên nội dung — ẩn hẳn nó là
          cắt mất đường duy nhất chuyển bài trong chủ đề (app sidebar thành
          ngăn kéo, không chứa danh sách bài). Desktop: cột dọc sticky. */}
      <aside className="shrink-0 border-b border-rule bg-ground lg:sticky lg:top-16 lg:block lg:h-[calc(100dvh-4rem)] lg:w-60 lg:border-b-0 lg:border-r">
        <div className="flex h-full flex-col">
          <div className="min-h-0 flex-1 px-2 py-3 lg:overflow-y-auto">
            <p className="mb-2 px-2.5 text-label font-semibold uppercase text-ink-faint">
              {shown?.topic_title ?? "Bài học"}
            </p>
            <nav className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
              {topic?.lessons.map((sibling) => {
                const current = sibling.id === lessonId;
                const SiblingIcon = sibling.kind === "practice" ? PenLine : BookOpen;
                return (
                  <Link
                    key={sibling.id}
                    href={`/learn/grammar/${topicId}/${sibling.id}`}
                    aria-current={current ? "page" : undefined}
                    className={cx(
                      "relative inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded px-2.5 py-1.5 text-small font-semibold transition-colors",
                      current
                        ? "bg-action-tint text-action-ink"
                        : "text-ink-muted hover:bg-recess hover:text-ink",
                    )}
                  >
                    <SiblingIcon size={16} strokeWidth={1.75} aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{sibling.title}</span>
                    {sibling.completed && (
                      <Check size={13} strokeWidth={2} className="shrink-0 text-ok" aria-hidden />
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>
          {/* Đáy sidebar, NGOÀI khối cuộn — cùng khuôn `sidebarBottom` của app:
              danh sách bài cuộn được, khe này thì không, nên lối ra luôn nhìn
              thấy kể cả khi chủ đề dài hơn màn hình. Nhãn trung tính: đây là
              một liên kết điều hướng, không phải lời kêu gọi hành động. */}
          {shown?.next_topic && (
            <div className="border-t border-rule p-2">
              <Link
                href={`/learn/grammar/${shown.next_topic.topic_id}/${shown.next_topic.lesson_id}`}
                className="flex items-center justify-between gap-2 rounded px-2.5 py-2 text-small font-semibold text-ink-muted transition-colors hover:bg-recess hover:text-ink"
              >
                <span className="min-w-0 truncate">
                  Chủ đề tiếp theo: {shown.next_topic.topic_title}
                </span>
                <ArrowRight size={13} strokeWidth={2} className="shrink-0" aria-hidden />
              </Link>
            </div>
          )}
        </div>
      </aside>

      {/* Cột dọc để `mt-auto` của thanh đáy có tác dụng khi bài ngắn: cột cao
          ít nhất bằng màn hình, thanh nằm sát đáy; khi bài dài, `sticky` giữ nó
          nhìn thấy được trong lúc cuộn. */}
      <div className="flex min-h-[calc(100dvh-4rem)] min-w-0 flex-1 flex-col">
        <div className="sticky top-16 z-10 bg-ground/85 px-4 pt-3 backdrop-blur">
          <Breadcrumbs
            trail={[
              { href: "/learn/grammar", label: "Ngữ pháp" },
              { href: `/learn/grammar/${topicId}`, label: shown?.topic_title ?? "Chủ đề" },
            ]}
          />
        </div>

        {shown && (
          <Page className="max-w-3xl">
            {error && <Alert>{error}</Alert>}

            <PageHeader eyebrow={isPractice ? "Luyện tập" : "Bài học"} title={shown.title} />

            <GuestNotice className="mb-4" />

            {isPractice ? (
              <div className="space-y-4">
                {shown.questions.map((question) => (
                  <GrammarQuestionCard
                    key={question.id}
                    question={question}
                    token={token}
                    onCorrect={(questionId) =>
                      setJustCorrect((prev) =>
                        prev.lessonId === lessonId
                          ? { lessonId, ids: new Set(prev.ids).add(questionId) }
                          : { lessonId, ids: new Set([questionId]) },
                      )
                    }
                  />
                ))}
              </div>
            ) : (
              /* Nền trắng (`bg-panel`) chứ không nền xám của trang: đây là tài
                 liệu đọc dài, và design system đã có sẵn bề mặt trắng cho việc
                 đó. */
              <Panel className="p-6 sm:p-8">
                <MarkdownLite text={shown.body} className="text-lesson" />
              </Panel>
            )}
          </Page>
        )}

        {/* Sticky trong cột nội dung, không fixed toàn màn: thanh đáy chạy hết
            chiều rộng PHẦN CÒN LẠI và nằm gọn giữa mép phải của cột bài học với
            mép phải cửa sổ — `fixed inset-x-0` sẽ đè lên cả hai sidebar. */}
        {shown && status === "authenticated" && (
          <div className="sticky bottom-0 mt-auto border-t border-rule bg-panel/95 backdrop-blur">
            <div className="flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
              <span className="text-small text-ink-muted">
                {isPractice
                  ? `${answeredCorrect}/${shown.questions.length} câu đã làm đúng`
                  : shown.completed
                    ? "Bạn đã học xong bài này."
                    : "Đọc xong? Đánh dấu để đi tiếp."}
              </span>
              <div className="flex items-center gap-2">
                {lessonDone && (
                  <Button variant="quiet" size="sm" onClick={unmarkComplete}>
                    Bỏ hoàn thành
                  </Button>
                )}
                {lessonDone ? (
                  shown.next_lesson ? (
                    <Link
                      href={`/learn/grammar/${topicId}/${shown.next_lesson.id}`}
                      className="inline-flex items-center gap-1.5 rounded border border-action bg-action px-3 py-1.5 text-small font-semibold text-on-action hover:bg-action-hover"
                    >
                      Học bài tiếp theo
                      <ArrowRight size={13} strokeWidth={2} aria-hidden />
                    </Link>
                  ) : shown.next_topic ? (
                    /* Bài cuối chủ đề nhưng còn chủ đề kế: KHÔNG nói "Hết chủ
                     đề" — đối chọi với đúng cái nút đang nằm ở sidebar. Hành
                     động đã có chỗ của nó; thanh này chỉ còn lời xác nhận. */
                    <span className="text-small text-ink-faint">Bạn đã học xong chủ đề này.</span>
                  ) : (
                    <Link
                      href={`/learn/grammar/${topicId}`}
                      className="inline-flex items-center gap-1.5 rounded border border-rule-strong px-3 py-1.5 text-small font-semibold"
                    >
                      <Check size={13} strokeWidth={2} className="text-ok" aria-hidden />
                      Hết chủ đề — quay lại danh sách
                    </Link>
                  )
                ) : (
                  <Button onClick={markComplete}>
                    <Check size={13} strokeWidth={2} aria-hidden />
                    Hoàn thành
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
