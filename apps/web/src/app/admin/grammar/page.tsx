"use client";

import {
  API_ROUTES,
  type GrammarLessonAdmin,
  type GrammarLessonAdminPage,
  type GrammarTopicAdmin,
  type GrammarTopicAdminPage,
} from "@toeic-pilot/shared";
import { ArrowDown, ArrowUp, BookOpen, GraduationCap, PenLine, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { DestructiveButton } from "@/components/destructive-button";
import { AddChild, InlineRename, TreeEmpty, TreeNode } from "@/components/tree";
import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  IconButton,
  Page,
  PageHeader,
  PublishTag,
  SectionHeader,
  SkeletonList,
  Tag,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Ngữ pháp: chủ đề → bài học (SPEC-GRAMMAR G1).
 *
 * Hai tầng chứ không ba như cây dictation — một bài ngữ pháp không phải đơn vị
 * audio. Cổng publish của CHỦ ĐỀ đo bằng số câu thật trong kho nhãn (≥12), nên
 * mỗi hàng mang con số đó ngay trên giao diện: chủ đề dưới ngưỡng vẫn soạn được
 * bình thường, chỉ là chưa mở cho người học — và màn này phải nói rõ vì sao nút
 * mờ.
 */

const MIN_QUESTIONS = 12;

export default function AdminGrammarPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [topics, setTopics] = useState<GrammarTopicAdmin[] | null>(null);
  const [lessons, setLessons] = useState<GrammarLessonAdmin[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((t: string) => {
    void apiFetch<GrammarTopicAdminPage>(`${API_ROUTES.adminGrammarTopics}?limit=200`, { token: t })
      .then((page) => setTopics(page.items))
      .catch(() => setError("Không tải được danh sách chủ đề."));
    // Cả bài học trong MỘT lần đọc — màn này dựng theo cây, cắt trang danh sách
    // bài sẽ dựng ra cây khuyết mà không nói gì (như /admin/tests).
    void apiFetch<GrammarLessonAdminPage>(`${API_ROUTES.adminGrammarLessons}?limit=200`, {
      token: t,
    })
      .then((page) => setLessons(page.items))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (token) refresh(token);
  }, [token, refresh]);

  async function send(path: string, method: "POST" | "PATCH" | "PUT" | "DELETE", body?: unknown) {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(path, {
        method,
        token,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Thao tác không thành công.");
    }
  }

  // Đổi chỗ = gửi lại CẢ thứ tự, không phải "swap hai bài": cùng lập luận với
  // `StoryReorder` — một giao dịch gán 1..N, server từ chối nếu danh sách không
  // phủ đủ cây (client đang dùng ảnh cũ thì hỏng to, và nó nói cho mà biết).
  function moveLesson(topicId: string, ordered: GrammarLessonAdmin[], from: number, to: number) {
    if (to < 0 || to >= ordered.length) return;
    const ids = ordered.map((lesson) => lesson.id);
    const [moved] = ids.splice(from, 1);
    ids.splice(to, 0, moved);
    void send(API_ROUTES.adminGrammarTopicLessonOrder(topicId), "PUT", { lesson_ids: ids });
  }

  function moveTopic(ordered: GrammarTopicAdmin[], from: number, to: number) {
    if (to < 0 || to >= ordered.length) return;
    const ids = ordered.map((topic) => topic.id);
    const [moved] = ids.splice(from, 1);
    ids.splice(to, 0, moved);
    void send(API_ROUTES.adminGrammarTopicsOrder, "PUT", { topic_ids: ids });
  }

  if (status !== "authenticated") {
    return (
      <Page>
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="Ngữ pháp"
        description="Chủ đề là mã nhãn của taxonomy; bài tập cuối chủ đề rút tự động theo nhãn."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <Alert tone="info">
        Chủ đề chỉ xuất bản được khi kho có đủ {MIN_QUESTIONS} câu published mang nhãn — một chủ đề
        mỏng vẫn chấm được và trông hoàn toàn bình thường, cho tới khi người học làm xong nó trong
        ba phút.
      </Alert>

      <section className="mt-8">
        <SectionHeader
          title="Chủ đề"
          aside={
            <>
              <AddChild
                label="Thêm chủ đề"
                fields={[
                  { name: "code", placeholder: "GRAMMAR_TENSE", className: "max-w-[14rem]" },
                  { name: "slug", placeholder: "thi", className: "max-w-[10rem]" },
                  { name: "title", placeholder: "Thì" },
                ]}
                onSubmit={(values) => void send(API_ROUTES.adminGrammarTopics, "POST", values)}
              />
              {/* AddChild bắt mọi ô có chữ — nên "không mã" không thể là một ô
                  trống, nó phải là một nút riêng, nói rõ mình tạo gì. */}
              <AddChild
                label="Thêm bài nền tảng (không mã)"
                fields={[
                  { name: "slug", placeholder: "kien-thuc-co-ban-1", className: "max-w-[16rem]" },
                  { name: "title", placeholder: "Kiến thức cơ bản 1: từ loại và cụm từ" },
                ]}
                onSubmit={(values) => void send(API_ROUTES.adminGrammarTopics, "POST", values)}
              />
            </>
          }
        />

        {!topics && <SkeletonList rows={2} />}

        {topics?.length === 0 && (
          <EmptyState
            icon={GraduationCap}
            title="Chưa có chủ đề nào"
            description="Tạo một chủ đề ứng với một mã GRAMMAR_* của taxonomy."
          />
        )}

        <div className="space-y-3">
          {topics?.map((topic, topicIndex) => {
            const inTopic = lessons.filter((lesson) => lesson.topic_id === topic.id);
            // Hai cổng publish khác nhau theo code (server giữ luật thật, ở đây
            // chỉ là nút mờ nói đúng lý do): có mã → đo kho nhãn; không mã →
            // phải có ít nhất một bài đã publish.
            const enough = topic.code
              ? topic.question_count >= MIN_QUESTIONS
              : topic.lesson_count > 0;
            return (
              <TreeNode
                key={topic.id}
                icon={GraduationCap}
                name={
                  <InlineRename
                    value={topic.title}
                    onSave={(title) =>
                      void send(API_ROUTES.adminGrammarTopic(topic.id), "PATCH", { title })
                    }
                  />
                }
                meta={
                  <>
                    {topic.code ? (
                      <span className="font-data text-small text-ink-faint">{topic.code}</span>
                    ) : (
                      <span className="text-small text-ink-faint">nền tảng</span>
                    )}
                    {topic.code && (
                      <Tag tone={enough ? "ok" : "warn"}>
                        {topic.question_count}/{MIN_QUESTIONS} câu
                      </Tag>
                    )}
                    <span className="font-data text-small text-ink-muted">
                      {topic.lesson_count} bài
                    </span>
                    <PublishTag status={topic.status} />
                  </>
                }
                actions={
                  <>
                    <IconButton
                      icon={ArrowUp}
                      aria-label="Lên trước"
                      disabled={topicIndex === 0}
                      onClick={() => void moveTopic(topics, topicIndex, topicIndex - 1)}
                    />
                    <IconButton
                      icon={ArrowDown}
                      aria-label="Xuống sau"
                      disabled={topicIndex === topics.length - 1}
                      onClick={() => void moveTopic(topics, topicIndex, topicIndex + 1)}
                    />
                    {topic.status !== "published" && (
                      <Button
                        size="sm"
                        disabled={!canPublish || !enough}
                        title={
                          !canPublish
                            ? "Chỉ admin mới xuất bản được"
                            : enough
                              ? "Xuất bản chủ đề"
                              : topic.code
                                ? `Cần tối thiểu ${MIN_QUESTIONS} câu published mang nhãn này`
                                : "Chủ đề nền tảng cần ít nhất một bài đã xuất bản"
                        }
                        onClick={() =>
                          void send(API_ROUTES.adminGrammarTopicPublish(topic.id), "POST")
                        }
                      >
                        <Send size={13} strokeWidth={2} aria-hidden />
                        Xuất bản
                      </Button>
                    )}
                    <DestructiveButton
                      label="Xoá"
                      confirmLabel={`Xoá cả ${topic.lesson_count} bài?`}
                      disabled={!canPublish}
                      title={
                        canPublish
                          ? "Xoá chủ đề và mọi bài bên trong. Câu hỏi và lượt làm không bị chạm tới."
                          : "Chỉ admin mới xoá được"
                      }
                      onConfirm={() => void send(API_ROUTES.adminGrammarTopic(topic.id), "DELETE")}
                    />
                  </>
                }
              >
                {inTopic.length === 0 && <TreeEmpty>Chủ đề này chưa có bài học nào.</TreeEmpty>}

                {inTopic.map((lesson, index) => (
                  <TreeNode
                    key={lesson.id}
                    level={1}
                    icon={lesson.kind === "practice" ? PenLine : BookOpen}
                    name={
                      <InlineRename
                        value={lesson.title}
                        onSave={(title) =>
                          void send(API_ROUTES.adminGrammarLesson(lesson.id), "PATCH", { title })
                        }
                      />
                    }
                    meta={
                      <>
                        <span className="font-data text-small text-ink-muted">
                          {lesson.question_count} câu
                        </span>
                        <PublishTag status={lesson.status} />
                      </>
                    }
                    actions={
                      <>
                        <IconButton
                          icon={ArrowUp}
                          aria-label="Lên trước"
                          disabled={index === 0}
                          onClick={() => void moveLesson(topic.id, inTopic, index, index - 1)}
                        />
                        <IconButton
                          icon={ArrowDown}
                          aria-label="Xuống sau"
                          disabled={index === inTopic.length - 1}
                          onClick={() => void moveLesson(topic.id, inTopic, index, index + 1)}
                        />
                        <ButtonLink
                          size="sm"
                          variant="quiet"
                          href={`/admin/grammar/lessons/${lesson.id}`}
                        >
                          Sửa bài
                        </ButtonLink>
                        {lesson.status !== "published" && (
                          <Button
                            size="sm"
                            disabled={!canPublish}
                            title={canPublish ? "Xuất bản bài" : "Chỉ admin mới xuất bản được"}
                            onClick={() =>
                              void send(API_ROUTES.adminGrammarLessonPublish(lesson.id), "POST")
                            }
                          >
                            <Send size={13} strokeWidth={2} aria-hidden />
                            Xuất bản
                          </Button>
                        )}
                        <DestructiveButton
                          label="Xoá"
                          confirmLabel="Xoá bài này?"
                          disabled={!canPublish}
                          title={
                            canPublish
                              ? "Xoá bài. Câu hỏi không bị xoá theo."
                              : "Chỉ admin mới xoá được"
                          }
                          onConfirm={() =>
                            void send(API_ROUTES.adminGrammarLesson(lesson.id), "DELETE")
                          }
                        />
                      </>
                    }
                  />
                ))}

                <div className="pt-0.5">
                  <ButtonLink
                    size="sm"
                    variant="quiet"
                    href={`/admin/grammar/lessons/new/${topic.id}`}
                  >
                    Thêm bài
                  </ButtonLink>
                </div>
              </TreeNode>
            );
          })}
        </div>
      </section>
    </Page>
  );
}
