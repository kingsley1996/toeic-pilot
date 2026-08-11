"use client";

import {
  API_ROUTES,
  type DictationSectionAdmin,
  type DictationSectionAdminPage,
  type DictationStoryAdmin,
  type DictationStoryAdminPage,
  type DictationTopicAdmin,
} from "@toeic-pilot/shared";
import { Check, Pencil, Send, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Field,
  Input,
  Page,
  PageHeader,
  Panel,
  PublishTag,
  SectionHeader,
  Select,
  SkeletonList,
  Tag,
} from "@/components/ui";
import { DestructiveButton } from "@/components/destructive-button";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Cây nội dung dictation: chủ đề → phần → bài.
 *
 * Ba tầng trên một màn hình chứ không ba màn hình riêng: lúc dựng cây, người ta
 * tạo một chủ đề rồi tạo ngay phần bên trong nó, rồi bài bên trong phần. Bắt họ
 * điều hướng qua lại giữa ba trang là biến một thao tác liền mạch thành ba.
 */
export default function AdminDictationTreePage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [topics, setTopics] = useState<DictationTopicAdmin[] | null>(null);
  const [sections, setSections] = useState<DictationSectionAdmin[]>([]);
  const [stories, setStories] = useState<DictationStoryAdmin[]>([]);
  const [error, setError] = useState<string | null>(null);
  // 0 = không bị cắt; khác 0 là tổng số bài thật.
  const [truncated, setTruncated] = useState(0);

  const [topicForm, setTopicForm] = useState({ slug: "", name: "" });
  const [sectionForm, setSectionForm] = useState({ topic_id: "", name: "" });
  const [storyForm, setStoryForm] = useState({ section_id: "", title: "" });

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

  async function create(path: string, body: unknown) {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(path, { method: "POST", token, body: JSON.stringify(body) });
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được.");
    }
  }

  const [editing, setEditing] = useState<{ id: string; value: string } | null>(null);

  async function send(path: string, method: "PATCH" | "DELETE", body?: unknown) {
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

  /** Ô sửa tên tại chỗ: đổi tên là thao tác hay dùng nhất, không đáng phải mở một trang khác. */
  function NameCell({
    id,
    name,
    save,
  }: {
    id: string;
    name: string;
    save: (value: string) => void;
  }) {
    if (editing?.id !== id) {
      return (
        <>
          <span className="font-semibold">{name}</span>
          <Button
            size="sm"
            variant="quiet"
            aria-label={`Sửa tên ${name}`}
            title="Sửa tên"
            onClick={() => setEditing({ id, value: name })}
          >
            <Pencil size={14} strokeWidth={2} aria-hidden />
          </Button>
        </>
      );
    }
    return (
      <span className="flex min-w-0 flex-1 items-center gap-1">
        <Input
          value={editing.value}
          autoFocus
          onChange={(e) => setEditing({ id, value: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Enter" && editing.value.trim()) save(editing.value.trim());
            if (e.key === "Escape") setEditing(null);
          }}
          className="max-w-xs"
        />
        <Button
          size="sm"
          aria-label="Lưu tên"
          disabled={!editing.value.trim()}
          onClick={() => save(editing.value.trim())}
        >
          <Check size={14} strokeWidth={2} aria-hidden />
        </Button>
        <Button size="sm" variant="quiet" aria-label="Huỷ sửa" onClick={() => setEditing(null)}>
          <X size={14} strokeWidth={2} aria-hidden />
        </Button>
      </span>
    );
  }

  async function publish(path: string) {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(path, { method: "POST", token });
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không xuất bản được.");
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
        title="Cây nội dung"
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
        <SectionHeader title="Chủ đề" />
        <Panel className="p-4">
          <div className="grid gap-3 sm:grid-cols-[10rem_1fr_auto] sm:items-end">
            <Field label="Slug" hint="dùng trong URL">
              <Input
                value={topicForm.slug}
                onChange={(e) => setTopicForm({ ...topicForm, slug: e.target.value })}
                placeholder="short-stories"
              />
            </Field>
            <Field label="Tên hiển thị">
              <Input
                value={topicForm.name}
                onChange={(e) => setTopicForm({ ...topicForm, name: e.target.value })}
                placeholder="Short stories"
              />
            </Field>
            <Button
              disabled={!topicForm.slug.trim() || !topicForm.name.trim()}
              onClick={() => {
                void create(API_ROUTES.adminDictationTopics, topicForm);
                setTopicForm({ slug: "", name: "" });
              }}
            >
              Thêm chủ đề
            </Button>
          </div>
        </Panel>

        {!topics && <SkeletonList rows={2} />}
        <div className="mt-3 space-y-2">
          {topics?.map((topic) => (
            <Panel key={topic.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <NameCell
                id={topic.id}
                name={topic.name}
                save={(value) => {
                  setEditing(null);
                  void send(API_ROUTES.adminDictationTopic(topic.id), "PATCH", { name: value });
                }}
              />
              <span className="font-data text-small text-ink-faint">/{topic.slug}</span>
              <span className="font-data text-small text-ink-muted">
                {topic.section_count} phần
              </span>
              <span className="ml-auto flex items-center gap-2">
                <PublishTag status={topic.status} />
                {topic.status !== "published" && (
                  <Button
                    size="sm"
                    disabled={!canPublish}
                    title={canPublish ? "Xuất bản chủ đề" : "Chỉ admin mới xuất bản được"}
                    onClick={() => void publish(API_ROUTES.adminDictationTopicPublish(topic.id))}
                  >
                    <Send size={14} strokeWidth={2} aria-hidden />
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
                  onConfirm={() => void send(API_ROUTES.adminDictationTopic(topic.id), "DELETE")}
                />
              </span>
            </Panel>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader title="Phần" />
        <Panel className="p-4">
          <div className="grid gap-3 sm:grid-cols-[14rem_1fr_auto] sm:items-end">
            <Field label="Thuộc chủ đề">
              <Select
                value={sectionForm.topic_id}
                onChange={(e) => setSectionForm({ ...sectionForm, topic_id: e.target.value })}
              >
                <option value="">(chọn chủ đề)</option>
                {topics?.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Tên phần" hint="Unit 1, Level A, Tuần 3 — tuỳ bạn">
              <Input
                value={sectionForm.name}
                onChange={(e) => setSectionForm({ ...sectionForm, name: e.target.value })}
                placeholder="Unit 1"
              />
            </Field>
            <Button
              disabled={!sectionForm.topic_id || !sectionForm.name.trim()}
              onClick={() => {
                void create(API_ROUTES.adminDictationSections, sectionForm);
                setSectionForm({ topic_id: "", name: "" });
              }}
            >
              Thêm phần
            </Button>
          </div>
        </Panel>

        <div className="mt-3 space-y-2">
          {sections.map((section) => (
            <Panel key={section.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="font-data text-small text-ink-faint">{section.topic_name} /</span>
              <NameCell
                id={section.id}
                name={section.name}
                save={(value) => {
                  setEditing(null);
                  void send(API_ROUTES.adminDictationSection(section.id), "PATCH", { name: value });
                }}
              />
              <span className="font-data text-small text-ink-muted">{section.story_count} bài</span>
              <span className="ml-auto flex items-center gap-2">
                <PublishTag status={section.status} />
                {section.status !== "published" && (
                  <Button
                    size="sm"
                    disabled={!canPublish}
                    onClick={() =>
                      void publish(API_ROUTES.adminDictationSectionPublish(section.id))
                    }
                  >
                    <Send size={14} strokeWidth={2} aria-hidden />
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
              </span>
            </Panel>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader title="Bài" />
        <Panel className="p-4">
          <div className="grid gap-3 sm:grid-cols-[14rem_1fr_auto] sm:items-end">
            <Field label="Thuộc phần">
              <Select
                value={storyForm.section_id}
                onChange={(e) => setStoryForm({ ...storyForm, section_id: e.target.value })}
              >
                <option value="">(chọn phần)</option>
                {sections.map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.topic_name} / {section.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Tên bài">
              <Input
                value={storyForm.title}
                onChange={(e) => setStoryForm({ ...storyForm, title: e.target.value })}
                placeholder="A Day at the Office"
              />
            </Field>
            <Button
              disabled={!storyForm.section_id || !storyForm.title.trim()}
              onClick={() => {
                void create(API_ROUTES.adminDictationStories, storyForm);
                setStoryForm({ section_id: "", title: "" });
              }}
            >
              Thêm bài
            </Button>
          </div>
        </Panel>

        <div className="mt-3 space-y-2">
          {stories.map((story) => (
            <Panel key={story.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="font-data text-small text-ink-faint">
                {story.topic_name} / {story.section_name} /
              </span>
              <NameCell
                id={story.id}
                name={story.title}
                save={(value) => {
                  setEditing(null);
                  void send(API_ROUTES.adminDictationStory(story.id), "PATCH", { title: value });
                }}
              />
              <Tag tone={story.published_item_count > 0 ? "ok" : "neutral"}>
                {story.published_item_count}/{story.item_count} câu đã xuất bản
              </Tag>
              <span className="ml-auto flex items-center gap-2">
                <PublishTag status={story.status} />
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
                    onClick={() => void publish(API_ROUTES.adminDictationStoryPublish(story.id))}
                  >
                    <Send size={14} strokeWidth={2} aria-hidden />
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
                  onConfirm={() => void send(API_ROUTES.adminDictationStory(story.id), "DELETE")}
                />
              </span>
            </Panel>
          ))}
        </div>
      </section>
    </Page>
  );
}
