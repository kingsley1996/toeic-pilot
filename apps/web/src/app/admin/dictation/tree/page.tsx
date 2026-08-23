"use client";

import {
  API_ROUTES,
  type DictationSectionAdmin,
  type DictationSectionAdminPage,
  type DictationStoryAdmin,
  type DictationStoryAdminPage,
  type DictationTopicAdmin,
} from "@toeic-pilot/shared";
import { BookOpen, FileAudio, FolderTree, Headphones, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { DestructiveButton } from "@/components/destructive-button";
import { AddChild, InlineRename, TreeEmpty, TreeNode } from "@/components/tree";
import {
  Alert,
  Button,
  EmptyState,
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
 * Cây dictation: chủ đề → phần → bài.
 *
 * Cùng hình dạng với `/admin/vocabulary/tree` và `/admin/tests`, và đó là chủ
 * đích: ba cây khác nhau về nội dung nhưng giống hệt nhau về thao tác — đổi
 * tên, xuất bản, xoá, thêm con — nên chúng phải trông giống nhau. Bản trước in
 * ba danh sách phẳng chồng lên nhau, mỗi hàng con mang tên cha ở đầu dòng; quan
 * hệ cha–con khi đó là thứ người đọc phải tự ghép lại, và một phần rỗng thì
 * không hiện ra ở đâu cả.
 */
export default function AdminDictationTreePage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [topics, setTopics] = useState<DictationTopicAdmin[] | null>(null);
  const [sections, setSections] = useState<DictationSectionAdmin[]>([]);
  const [stories, setStories] = useState<DictationStoryAdmin[]>([]);
  const [error, setError] = useState<string | null>(null);
  // 0 = không bị cắt; khác 0 là tổng số bài thật.
  const [truncated, setTruncated] = useState(0);

  const refresh = useCallback((t: string) => {
    void apiFetch<DictationTopicAdmin[]>(API_ROUTES.adminDictationTopics, { token: t })
      .then(setTopics)
      .catch(() => setError("Không tải được cây nội dung."));
    void apiFetch<DictationSectionAdminPage>(`${API_ROUTES.adminDictationSections}?limit=200`, {
      token: t,
    })
      .then((page) => setSections(page.items))
      .catch(() => {});
    // Cùng lý do như `/admin/tests`: đây là CÂY (chủ đề → phần → bài), nên cắt
    // trang danh sách bài phẳng sẽ dựng ra một cây khuyết mà không nói gì.
    void apiFetch<DictationStoryAdminPage>(`${API_ROUTES.adminDictationStories}?limit=200`, {
      token: t,
    })
      .then((page) => {
        setStories(page.items);
        setTruncated(page.total > page.items.length ? page.total : 0);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (token) refresh(token);
  }, [token, refresh]);

  async function send(path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown) {
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
        title="Cây bài nghe"
        description="Chủ đề → phần → bài. Xuất bản từ dưới lên: bài trước, rồi phần, rồi chủ đề."
      />

      {truncated > 0 && (
        <Alert tone="warn">
          Đang hiện 200 bài đầu trong tổng số {truncated}. Màn này dựng theo cây nên chưa lật trang
          được.
        </Alert>
      )}

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {/* Xuất bản từ dưới lên là ràng buộc thật, không phải lời khuyên: học viên
          chỉ thấy một bài khi CẢ chủ đề, phần và bài đều đã xuất bản. */}
      <Alert tone="info">
        Học viên chỉ thấy một bài khi cả ba tầng đều đã xuất bản. Một bài không có câu nào đã xuất
        bản thì không xuất bản được — nó sẽ là một trang trống.
      </Alert>

      <section className="mt-8">
        <SectionHeader
          title="Chủ đề"
          aside={
            <AddChild
              label="Thêm chủ đề"
              fields={[
                { name: "slug", placeholder: "short-stories", className: "max-w-[10rem]" },
                { name: "name", placeholder: "Short stories" },
              ]}
              onSubmit={(values) => void send(API_ROUTES.adminDictationTopics, "POST", values)}
            />
          }
        />

        {!topics && <SkeletonList rows={2} />}

        {topics?.length === 0 && (
          <EmptyState
            icon={FolderTree}
            title="Chưa có chủ đề nào"
            description="Tạo một chủ đề, rồi thêm phần bên trong nó, rồi bài bên trong phần."
          />
        )}

        <div className="space-y-3">
          {topics?.map((topic) => {
            const inTopic = sections.filter((section) => section.topic_id === topic.id);
            return (
              <TreeNode
                key={topic.id}
                icon={Headphones}
                name={
                  <InlineRename
                    value={topic.name}
                    onSave={(name) =>
                      void send(API_ROUTES.adminDictationTopic(topic.id), "PATCH", { name })
                    }
                  />
                }
                meta={
                  <>
                    <span className="font-data text-small text-ink-faint">/{topic.slug}</span>
                    <span className="font-data text-small text-ink-muted">
                      {topic.section_count} phần
                    </span>
                    <PublishTag status={topic.status} />
                  </>
                }
                actions={
                  <>
                    {topic.status !== "published" && (
                      <Button
                        size="sm"
                        disabled={!canPublish}
                        title={canPublish ? "Xuất bản chủ đề" : "Chỉ admin mới xuất bản được"}
                        onClick={() =>
                          void send(API_ROUTES.adminDictationTopicPublish(topic.id), "POST")
                        }
                      >
                        <Send size={13} strokeWidth={2} aria-hidden />
                        Xuất bản
                      </Button>
                    )}
                    <DestructiveButton
                      label="Xoá"
                      confirmLabel={`Xoá cả ${topic.section_count} phần?`}
                      disabled={!canPublish}
                      title={
                        canPublish
                          ? "Xoá chủ đề và mọi phần, bài bên trong. Các câu nghe vẫn được giữ lại."
                          : "Chỉ admin mới xoá được"
                      }
                      onConfirm={() =>
                        void send(API_ROUTES.adminDictationTopic(topic.id), "DELETE")
                      }
                    />
                  </>
                }
              >
                {inTopic.length === 0 && <TreeEmpty>Chủ đề này chưa có phần nào.</TreeEmpty>}

                {inTopic.map((section) => {
                  const inSection = stories.filter((story) => story.section_id === section.id);
                  return (
                    <TreeNode
                      key={section.id}
                      level={1}
                      icon={BookOpen}
                      name={
                        <InlineRename
                          value={section.name}
                          onSave={(name) =>
                            void send(API_ROUTES.adminDictationSection(section.id), "PATCH", {
                              name,
                            })
                          }
                        />
                      }
                      meta={
                        <>
                          <span className="font-data text-small text-ink-muted">
                            {section.story_count} bài
                          </span>
                          <PublishTag status={section.status} />
                        </>
                      }
                      actions={
                        <>
                          {section.status !== "published" && (
                            <Button
                              size="sm"
                              disabled={!canPublish}
                              title={canPublish ? "Xuất bản phần" : "Chỉ admin mới xuất bản được"}
                              onClick={() =>
                                void send(
                                  API_ROUTES.adminDictationSectionPublish(section.id),
                                  "POST",
                                )
                              }
                            >
                              <Send size={13} strokeWidth={2} aria-hidden />
                              Xuất bản
                            </Button>
                          )}
                          <DestructiveButton
                            label="Xoá"
                            confirmLabel={`Xoá cả ${section.story_count} bài?`}
                            disabled={!canPublish}
                            title={
                              canPublish
                                ? "Xoá phần và mọi bài bên trong. Các câu nghe vẫn được giữ lại."
                                : "Chỉ admin mới xoá được"
                            }
                            onConfirm={() =>
                              void send(API_ROUTES.adminDictationSection(section.id), "DELETE")
                            }
                          />
                        </>
                      }
                    >
                      {inSection.length === 0 && <TreeEmpty>Phần này chưa có bài nào.</TreeEmpty>}

                      {inSection.map((story) => (
                        <TreeNode
                          key={story.id}
                          level={2}
                          icon={FileAudio}
                          name={
                            <InlineRename
                              value={story.title}
                              onSave={(title) =>
                                void send(API_ROUTES.adminDictationStory(story.id), "PATCH", {
                                  title,
                                })
                              }
                            />
                          }
                          meta={
                            <>
                              <Tag tone={story.published_item_count > 0 ? "ok" : "neutral"}>
                                {story.published_item_count}/{story.item_count} câu đã xuất bản
                              </Tag>
                              <PublishTag status={story.status} />
                            </>
                          }
                          actions={
                            <>
                              {story.status !== "published" && (
                                <Button
                                  size="sm"
                                  disabled={!canPublish || !story.publishable}
                                  // Nút mờ CHÍNH LÀ thông báo — nên nó phải nói được vì sao.
                                  title={
                                    !canPublish
                                      ? "Chỉ admin mới xuất bản được"
                                      : story.publishable
                                        ? "Xuất bản bài này"
                                        : "Bài chưa có câu nào được xuất bản"
                                  }
                                  onClick={() =>
                                    void send(
                                      API_ROUTES.adminDictationStoryPublish(story.id),
                                      "POST",
                                    )
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
                                    ? `Xoá bài. ${story.item_count} câu bên trong sẽ trở lại thành câu lẻ, không bị xoá.`
                                    : "Chỉ admin mới xoá được"
                                }
                                onConfirm={() =>
                                  void send(API_ROUTES.adminDictationStory(story.id), "DELETE")
                                }
                              />
                            </>
                          }
                        />
                      ))}

                      <div className="pt-0.5">
                        <AddChild
                          label="Thêm bài"
                          fields={[{ name: "title", placeholder: "A Day at the Office" }]}
                          onSubmit={(values) =>
                            void send(API_ROUTES.adminDictationStories, "POST", {
                              ...values,
                              section_id: section.id,
                            })
                          }
                        />
                      </div>
                    </TreeNode>
                  );
                })}

                <div className="pt-0.5">
                  <AddChild
                    label="Thêm phần"
                    fields={[{ name: "name", placeholder: "Unit 1" }]}
                    onSubmit={(values) =>
                      void send(API_ROUTES.adminDictationSections, "POST", {
                        ...values,
                        topic_id: topic.id,
                      })
                    }
                  />
                </div>
              </TreeNode>
            );
          })}
        </div>
      </section>
    </Page>
  );
}
