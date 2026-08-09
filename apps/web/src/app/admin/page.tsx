"use client";

import { API_ROUTES, type TopicAdmin } from "@toeic-pilot/shared";
import { Headphones, Library } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BackfillHint } from "@/components/admin-bits";
import {
  Alert,
  Button,
  Field,
  Input,
  Page,
  PageHeader,
  Panel,
  PanelLink,
  PublishTag,
  SectionHeader,
  SkeletonList,
  Tag,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

export default function AdminPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [topics, setTopics] = useState<TopicAdmin[] | null>(null);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((t: string) => {
    apiFetch<TopicAdmin[]>(API_ROUTES.adminTopics, { token: t })
      .then(setTopics)
      .catch(() => setError("Không tải được danh sách chủ đề."));
  }, []);

  useEffect(() => {
    if (token) refresh(token);
  }, [token, refresh]);

  async function createTopic() {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(API_ROUTES.adminTopics, {
        method: "POST",
        token,
        body: JSON.stringify({ slug, name }),
      });
      setSlug("");
      setName("");
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được chủ đề.");
    }
  }

  // Guard đã đẩy học viên đi nơi khác; đây chỉ là thứ hiện ra trên đường ra.
  if (status !== "authenticated") {
    return (
      <Page>
        <SkeletonList rows={3} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="Tổng quan"
        description="Nhập hàng loạt, xem lại, rồi xuất bản."
        actions={
          // Vai trò đã hiện ở thanh trên; ở đây chỉ nói thứ editor cần biết
          // trước khi soạn xong rồi mới phát hiện mình không bấm được nút.
          !canPublish ? <Tag tone="warn">chỉ admin mới xuất bản được</Tag> : undefined
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <PanelLink href="/admin/vocabulary">
          <Library size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
          <h2 className="mt-3 text-subtitle">Từ vựng</h2>
          <p className="mt-1 text-small text-ink-muted">
            Mỗi từ cần bốn giọng cho headword, và bốn giọng nữa nếu có câu ví dụ.
          </p>
        </PanelLink>
        <PanelLink href="/admin/dictation">
          <Headphones size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
          <h2 className="mt-3 text-subtitle">Câu nghe</h2>
          <p className="mt-1 text-small text-ink-muted">
            Transcript vừa là nguồn sinh audio vừa là đáp án chấm bài.
          </p>
        </PanelLink>
      </div>

      <section className="mt-12">
        <SectionHeader title="Chủ đề" />

        {error && (
          <div className="mb-4">
            <Alert>{error}</Alert>
          </div>
        )}

        <Panel className="p-5">
          <div className="grid gap-3 sm:grid-cols-[12rem_1fr_auto] sm:items-end">
            <Field label="Slug" hint="dùng trong URL">
              <Input
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                placeholder="business"
              />
            </Field>
            <Field label="Tên hiển thị">
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Kinh doanh"
              />
            </Field>
            <Button disabled={!slug.trim() || !name.trim()} onClick={() => void createTopic()}>
              Thêm chủ đề
            </Button>
          </div>
        </Panel>

        {!topics && (
          <div className="mt-4">
            <SkeletonList rows={2} />
          </div>
        )}

        {topics && topics.length > 0 && (
          <ul className="mt-4 space-y-2">
            {topics.map((topic) => (
              <Panel key={topic.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <span className="font-semibold">{topic.name}</span>
                <span className="font-data text-small text-ink-faint">/{topic.slug}</span>
                <span className="ml-auto">
                  <PublishTag status={topic.status} />
                </span>
              </Panel>
            ))}
          </ul>
        )}

        {topics?.length === 0 && (
          <p className="mt-4 text-small text-ink-muted">
            Chưa có chủ đề nào. Chủ đề là thứ học viên nhìn thấy đầu tiên, kể cả khi bên trong chưa
            có từ nào.
          </p>
        )}
      </section>

      <div className="mt-12">
        <BackfillHint />
      </div>
    </Page>
  );
}
