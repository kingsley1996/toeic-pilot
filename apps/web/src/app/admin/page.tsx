"use client";

import { API_ROUTES, type TopicAdmin } from "@toeic-pilot/shared";
import { useCallback, useEffect, useState } from "react";

import { BackfillHint } from "@/components/admin-bits";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardLink,
  Field,
  Input,
  Page,
  PageHeader,
  SkeletonList,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

export default function AdminPage() {
  const { status, token, user, canPublish } = useRequireSession({ canEdit: true });
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

  // The guard redirects a learner away; this is only what shows on the way out.
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
        eyebrow="Quản lý nội dung"
        title="Biên soạn"
        description="Nhập hàng loạt, xem lại, rồi xuất bản."
        actions={
          <Badge tone={canPublish ? "brand" : "neutral"}>
            {user?.role}
            {!canPublish && " · không publish được"}
          </Badge>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <CardLink href="/admin/vocabulary">
          <div aria-hidden className="text-2xl">
            🗂️
          </div>
          <h2 className="mt-3 font-semibold">Từ vựng</h2>
          <p className="mt-1 text-sm text-text-muted">
            Mỗi từ cần bốn giọng cho headword, và bốn giọng nữa nếu có câu ví dụ.
          </p>
        </CardLink>
        <CardLink href="/admin/dictation">
          <div aria-hidden className="text-2xl">
            🎧
          </div>
          <h2 className="mt-3 font-semibold">Câu nghe</h2>
          <p className="mt-1 text-sm text-text-muted">
            Transcript vừa là nguồn sinh audio vừa là đáp án chấm bài.
          </p>
        </CardLink>
      </div>

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Chủ đề</h2>

        {error && (
          <div className="mb-4">
            <Alert>{error}</Alert>
          </div>
        )}

        <Card className="p-5">
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
        </Card>

        {!topics && (
          <div className="mt-4">
            <SkeletonList rows={2} />
          </div>
        )}

        {topics && topics.length > 0 && (
          <ul className="mt-4 space-y-2">
            {topics.map((topic) => (
              <Card key={topic.id} className="flex items-center gap-3 px-5 py-3">
                <span className="font-medium">{topic.name}</span>
                <span className="font-mono text-xs text-text-subtle">/{topic.slug}</span>
                <Badge
                  tone={topic.status === "published" ? "success" : "neutral"}
                  className="ml-auto"
                >
                  {topic.status}
                </Badge>
              </Card>
            ))}
          </ul>
        )}

        {topics?.length === 0 && (
          <p className="mt-4 text-sm text-text-muted">
            Chưa có chủ đề nào. Chủ đề là thứ học viên nhìn thấy đầu tiên, kể cả khi bên trong chưa
            có từ nào.
          </p>
        )}
      </section>

      <div className="mt-10">
        <BackfillHint />
      </div>
    </Page>
  );
}
