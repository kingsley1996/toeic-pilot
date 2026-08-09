"use client";

import {
  API_ROUTES,
  type CommitResult,
  type DictationAdmin,
  type DictationParseResponse,
  type TopicAdmin,
} from "@toeic-pilot/shared";
import { useCallback, useEffect, useState } from "react";

import { AudioBadge, BackfillHint, ParsePreview } from "@/components/admin-bits";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Page,
  PageHeader,
  Select,
  SkeletonList,
  Spinner,
  Textarea,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

const PLACEHOLDER = `The quarterly report is due before the end of the month.
Please submit your expense claims to the finance department.`;

export default function AdminDictationPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [raw, setRaw] = useState("");
  const [parsed, setParsed] = useState<DictationParseResponse | null>(null);
  const [topics, setTopics] = useState<TopicAdmin[]>([]);
  const [topicId, setTopicId] = useState("");
  const [items, setItems] = useState<DictationAdmin[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((t: string) => {
    apiFetch<DictationAdmin[]>(API_ROUTES.adminDictation, { token: t })
      .then(setItems)
      .catch(() => setError("Không tải được danh sách câu."));
  }, []);

  useEffect(() => {
    if (!token) return;
    apiFetch<TopicAdmin[]>(API_ROUTES.adminTopics, { token })
      .then(setTopics)
      .catch(() => {});
    refresh(token);
  }, [token, refresh]);

  async function parse() {
    if (!token) return;
    setNotice(null);
    setError(null);
    setBusy(true);
    try {
      setParsed(
        await apiFetch<DictationParseResponse>(API_ROUTES.adminDictationParse, {
          method: "POST",
          token,
          body: JSON.stringify({ raw_text: raw }),
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không phân tích được.");
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (!token || !parsed) return;
    setBusy(true);
    try {
      const result = await apiFetch<CommitResult>(API_ROUTES.adminDictation, {
        method: "POST",
        token,
        body: JSON.stringify({ rows: parsed.rows, topic_id: topicId || null }),
      });
      setNotice(
        `Đã lưu ${result.created} câu ở dạng nháp. Chúng chưa có audio — bước tiếp theo là sinh.`,
      );
      setParsed(null);
      setRaw("");
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được.");
    } finally {
      setBusy(false);
    }
  }

  async function publish(id: string) {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(API_ROUTES.adminDictationPublish(id), { method: "POST", token });
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không publish được.");
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
        eyebrow="Nội dung"
        title="Câu nghe"
        description="Transcript vừa là nguồn sinh audio vừa là đáp án chấm bài — sửa nó là audio cũ thành sai."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && (
        <div className="mb-4">
          <Alert tone="success">{notice}</Alert>
        </div>
      )}

      <Card className="p-5">
        <Field label="Dán hàng loạt" hint="Mỗi dòng một câu">
          <Textarea
            value={raw}
            onChange={(event) => setRaw(event.target.value)}
            rows={6}
            placeholder={PLACEHOLDER}
          />
        </Field>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <Button variant="secondary" disabled={!raw.trim() || busy} onClick={() => void parse()}>
            {busy && <Spinner />}
            Kiểm tra
          </Button>
          <Field label="Gán vào chủ đề">
            <Select value={topicId} onChange={(event) => setTopicId(event.target.value)}>
              <option value="">(không gán)</option>
              {topics.map((topic) => (
                <option key={topic.id} value={topic.id}>
                  {topic.name}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      {parsed && (
        <>
          <ParsePreview parsed={parsed} render={(row) => <span>{row.transcript}</span>} />
          <Button
            className="mt-4"
            disabled={parsed.ok_count === 0 || busy}
            onClick={() => void commit()}
          >
            {busy && <Spinner />}
            Lưu {parsed.ok_count} câu ở dạng nháp
          </Button>
        </>
      )}

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Tất cả câu</h2>
        {!items && <SkeletonList rows={3} />}

        {items?.length === 0 && (
          <EmptyState
            icon="🎧"
            title="Chưa có câu nào"
            description="Dán vài câu ở trên để bắt đầu."
          />
        )}

        <div className="space-y-2">
          {items?.map((item) => (
            <Card key={item.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <p className="min-w-0 flex-1 text-sm">{item.transcript}</p>
              <Badge tone={item.status === "published" ? "success" : "neutral"}>
                {item.status}
              </Badge>
              <AudioBadge state={item.audio_state} />
              {item.status !== "published" && (
                <Button
                  size="sm"
                  variant="success"
                  disabled={!item.publishable || !canPublish}
                  onClick={() => void publish(item.id)}
                  title={
                    !canPublish
                      ? "Chỉ admin mới publish được"
                      : item.publishable
                        ? "Publish"
                        : "Audio chưa khớp với transcript"
                  }
                >
                  Publish
                </Button>
              )}
            </Card>
          ))}
        </div>
      </section>

      <div className="mt-10">
        <BackfillHint />
      </div>
    </Page>
  );
}
