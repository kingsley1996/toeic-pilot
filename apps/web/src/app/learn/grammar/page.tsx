"use client";

import { API_ROUTES, type GrammarTopicDetail, type GrammarTopicPublic } from "@toeic-pilot/shared";
import { BookOpen, Check, ChevronDown, GraduationCap, PenLine } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { GuestNotice } from "@/components/guest-notice";
import { Alert, EmptyState, Meter, Page, PageHeader, Panel, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/**
 * Tầng 1: chủ đề ngữ pháp, dạng accordion — bấm một chủ đề, danh sách bài mở
 * ra ngay bên dưới. Một trang toàn liên kết cấp hai bắt người học bấm vào rồi
 * bấm ra để biết bên trong có gì; accordion trả lời câu đó tại chỗ.
 */
export default function GrammarTopicsPage() {
  const { status, token } = useSession();
  const [topics, setTopics] = useState<GrammarTopicPublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, GrammarTopicDetail>>({});

  useEffect(() => {
    // Token PHẢI đi theo: `completed_lesson_count` do máy chủ tính từ
    // `get_optional_user`, thiếu token là nhận về số của người vô danh — 0 đều,
    // thanh tiến độ chết ở 0/Y ngay trước mắt người vừa bấm Hoàn thành.
    // `token` nằm trong deps vì phiên resolve sau lần dựng đầu.
    apiFetch<GrammarTopicPublic[]>(API_ROUTES.grammarTopics, { token: token ?? undefined })
      .then(setTopics)
      .catch(() => setError("Không tải được danh sách chủ đề."));
  }, [token]);

  function toggle(id: string) {
    const next = openId === id ? null : id;
    setOpenId(next);
    if (next && !details[next]) {
      apiFetch<GrammarTopicDetail>(API_ROUTES.grammarTopic(next), { token: token ?? undefined })
        .then((detail) => setDetails((prev) => ({ ...prev, [next]: detail })))
        .catch(() => {});
    }
  }

  if (status === "loading") {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  // Chủ đề hoàn thành khi có bài và mọi bài đã được bấm Hoàn thành. Chủ đề chưa
  // có bài nào KHÔNG được tính là xong rỗng — mẫu số 0 làm phép chia vô nghĩa.
  const isDone = (t: GrammarTopicPublic) =>
    t.lesson_count > 0 && t.completed_lesson_count === t.lesson_count;
  // Tiến độ tổng tính trên BÀI, không trên chủ đề: một chủ đề 8 bài học xong 7
  // vẫn là tiến độ thật, trong khi đếm chủ đề thì nó = 0 và không nhích cho tới
  // bài cuối — thanh tụt lại sau công việc của người học.
  const totalLessons = topics?.reduce((sum, t) => sum + t.lesson_count, 0) ?? 0;
  const doneLessons = topics?.reduce((sum, t) => sum + t.completed_lesson_count, 0) ?? 0;

  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Ngữ pháp"
        title="Lý thuyết ngữ pháp TOEIC"
        description="Mỗi chủ đề ứng với một điểm ngữ pháp của đề — học theo bài, rồi luyện ngay bằng câu thật."
      />

      <GuestNotice className="mb-4" />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!topics && !error && <SkeletonList rows={3} />}

      {status === "authenticated" && topics && topics.length > 0 && (
        <Panel className="mb-6 p-5">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-small font-semibold uppercase tracking-wide text-ink-faint">
              Tiến độ học tập
            </span>
            <span className="font-data text-title text-ink">
              {doneLessons}
              <span className="text-subtitle text-ink-faint">/{totalLessons}</span>
            </span>
          </div>
          <Meter
            value={doneLessons}
            max={totalLessons}
            label="Bài học đã hoàn thành"
            ticks={Math.min(totalLessons, 12)}
          />
        </Panel>
      )}

      <div className="space-y-2">
        {topics?.map((topic) => {
          const open = openId === topic.id;
          const detail = details[topic.id];
          return (
            <Panel key={topic.id} className="overflow-hidden">
              <button
                type="button"
                onClick={() => toggle(topic.id)}
                aria-expanded={open}
                className="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-recess"
              >
                <GraduationCap
                  size={18}
                  strokeWidth={1.75}
                  className="shrink-0 text-ink-muted"
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="block font-semibold">{topic.title}</span>
                    {isDone(topic) && (
                      <Check size={14} strokeWidth={2} className="shrink-0 text-ok" aria-hidden />
                    )}
                  </span>
                  {topic.summary && (
                    <span className="mt-0.5 block text-small text-ink-muted">{topic.summary}</span>
                  )}
                </span>
                <span className="font-data text-small text-ink-faint">
                  {topic.completed_lesson_count}/{topic.lesson_count} bài
                </span>
                <ChevronDown
                  size={16}
                  strokeWidth={2}
                  className={`shrink-0 text-ink-faint transition-transform ${open ? "rotate-180" : ""}`}
                  aria-hidden
                />
              </button>

              {open && (
                <div className="border-t border-rule px-4 py-3">
                  {!detail && <SkeletonList rows={2} />}
                  {detail && detail.lessons.length === 0 && (
                    <p className="text-small text-ink-muted">Chủ đề này chưa có bài nào.</p>
                  )}
                  {detail && (
                    <nav className="space-y-1">
                      {detail.lessons.map((lesson, index) => {
                        const LessonIcon = lesson.kind === "practice" ? PenLine : BookOpen;
                        return (
                          <Link
                            key={lesson.id}
                            href={`/learn/grammar/${topic.id}/${lesson.id}`}
                            className="flex items-center gap-2 rounded px-2 py-1.5 text-body hover:bg-recess"
                          >
                            <LessonIcon
                              size={14}
                              strokeWidth={1.75}
                              className="shrink-0 text-ink-muted"
                              aria-hidden
                            />
                            <span className="font-data text-small text-ink-faint">
                              {index + 1}.
                            </span>
                            <span className="min-w-0 flex-1">{lesson.title}</span>
                            {lesson.completed && (
                              <Check
                                size={13}
                                strokeWidth={2}
                                className="shrink-0 text-ok"
                                aria-hidden
                              />
                            )}
                          </Link>
                        );
                      })}
                    </nav>
                  )}
                </div>
              )}
            </Panel>
          );
        })}
      </div>

      {topics?.length === 0 && (
        <EmptyState
          icon={GraduationCap}
          title="Chưa có chủ đề nào"
          description="Nội dung đang được soạn."
        />
      )}
    </Page>
  );
}
