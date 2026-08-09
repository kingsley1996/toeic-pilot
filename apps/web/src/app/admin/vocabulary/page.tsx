"use client";

import {
  API_ROUTES,
  type CommitResult,
  type TopicAdmin,
  type VocabularyAdmin,
  type VocabularyParseResponse,
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

const PLACEHOLDER = `invoice | noun | /ˈɪnvɔɪs/ | a bill for goods | hóa đơn | Please pay the invoice. | Vui lòng thanh toán.
deadline | noun | /ˈdedlaɪn/ | the latest time | hạn chót`;

/** One stale clip is enough to block publishing, so the worst state is the one shown. */
function worstAudioState(entry: VocabularyAdmin): string {
  const states = entry.audio.map((slot) => slot.state);
  if (states.length === 0 || states.includes("missing")) return "missing";
  if (states.includes("stale")) return "stale";
  return "current";
}

export default function AdminVocabularyPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [raw, setRaw] = useState("");
  const [parsed, setParsed] = useState<VocabularyParseResponse | null>(null);
  const [topics, setTopics] = useState<TopicAdmin[]>([]);
  const [topicId, setTopicId] = useState("");
  const [entries, setEntries] = useState<VocabularyAdmin[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((t: string) => {
    apiFetch<VocabularyAdmin[]>(API_ROUTES.adminVocabulary, { token: t })
      .then(setEntries)
      .catch(() => setError("Không tải được danh sách từ."));
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
      // Parsing writes nothing: the rows come back for review, and only what the
      // editor approves is sent to the commit endpoint.
      setParsed(
        await apiFetch<VocabularyParseResponse>(API_ROUTES.adminVocabularyParse, {
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
      const result = await apiFetch<CommitResult>(API_ROUTES.adminVocabulary, {
        method: "POST",
        token,
        body: JSON.stringify({ rows: parsed.rows, topic_id: topicId || null }),
      });
      setNotice(
        `Đã lưu ${result.created} từ ở dạng nháp${result.skipped ? `, bỏ qua ${result.skipped}` : ""}. Bước tiếp theo là sinh audio.`,
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
      await apiFetch(API_ROUTES.adminVocabularyPublish(id), { method: "POST", token });
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
        title="Từ vựng"
        description="Dán nhiều dòng để tạo, sửa từng từ, rồi xuất bản khi audio đã sẵn sàng."
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
        <Field
          label="Dán hàng loạt"
          hint="headword | pos | phonetic | meaning_en | meaning_vi | example | example_vi"
        >
          <Textarea
            value={raw}
            onChange={(event) => setRaw(event.target.value)}
            rows={6}
            placeholder={PLACEHOLDER}
            className="font-mono text-xs"
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
          <ParsePreview
            parsed={parsed}
            render={(row) => (
              <>
                <span className="font-medium">{row.headword || "—"}</span>
                <span className="ml-2 text-xs text-text-subtle">{row.part_of_speech}</span>
                {row.meaning_vi && <span className="ml-2 text-text-muted">· {row.meaning_vi}</span>}
              </>
            )}
          />
          <Button
            className="mt-4"
            disabled={parsed.ok_count === 0 || busy}
            onClick={() => void commit()}
          >
            {busy && <Spinner />}
            Lưu {parsed.ok_count} từ ở dạng nháp
          </Button>
        </>
      )}

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Tất cả từ</h2>
        {!entries && <SkeletonList rows={3} />}

        {entries?.length === 0 && (
          <EmptyState
            icon="🗂️"
            title="Chưa có từ nào"
            description="Dán vài dòng ở trên để bắt đầu."
          />
        )}

        <div className="space-y-2">
          {entries?.map((entry) => (
            <Card key={entry.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <span className="font-medium">{entry.headword}</span>
                <span className="ml-2 text-xs text-text-subtle">{entry.part_of_speech}</span>
                <p className="truncate text-sm text-text-muted">{entry.meaning_vi}</p>
              </div>
              <Badge tone={entry.status === "published" ? "success" : "neutral"}>
                {entry.status}
              </Badge>
              <AudioBadge state={worstAudioState(entry)} />
              {entry.status !== "published" && (
                <Button
                  size="sm"
                  variant="success"
                  disabled={!entry.publishable || !canPublish}
                  onClick={() => void publish(entry.id)}
                  title={
                    !canPublish
                      ? "Chỉ admin mới publish được"
                      : entry.publishable
                        ? "Publish"
                        : "Audio chưa khớp với text"
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
