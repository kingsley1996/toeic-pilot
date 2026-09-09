"use client";

import {
  API_ROUTES,
  type CollocationParseResponse,
  type CollocationRow,
  type CollocationUpdate,
  type CommitResult,
  type TopicAdmin,
  type VocabularyAdmin,
  type VocabularyAdminPage,
} from "@toeic-pilot/shared";
import { Library, Pencil, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BackfillHint, ParsePreview } from "@/components/admin-bits";
import {
  Alert,
  AudioTag,
  Button,
  EmptyState,
  Field,
  Page,
  PageHeader,
  Pager,
  Panel,
  PublishTag,
  SectionHeader,
  Select,
  SkeletonList,
  Spinner,
  Textarea,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

const PLACEHOLDER = `submit a report | submit | submit | VERB_NOUN | nộp báo cáo | Please submit the report by Friday. | Vui lòng nộp báo cáo trước thứ Sáu. | make,do,take
interested in | interest | in | ADJ_PREP | quan tâm đến | She is interested in the position. | Cô ấy quan tâm đến vị trí này. | to,on,about
in accordance with | accordance | | PREP_PHRASE | theo đúng | Công việc... | Công việc... |`;

const PATTERNS = [
  "VERB_NOUN",
  "ADJ_PREP",
  "NOUN_NOUN",
  "VERB_PREP",
  "PREP_PHRASE",
  "ADJ_NOUN",
  "VERB_ADJ",
];

const PAGE_SIZE = 50;

export default function AdminCollocationPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [raw, setRaw] = useState("");
  const [parsed, setParsed] = useState<CollocationParseResponse | null>(null);
  const [topics, setTopics] = useState<TopicAdmin[]>([]);
  const [topicId, setTopicId] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [entries, setEntries] = useState<VocabularyAdmin[] | null>(null);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);

  // Form sửa sau commit (§12): tra theo entry id, sửa detail, PATCH.
  const [editEntryId, setEditEntryId] = useState("");
  const [editRow, setEditRow] = useState<CollocationRow | null>(null);
  const [editPattern, setEditPattern] = useState("");
  const [editGap, setEditGap] = useState("");
  const [editBase, setEditBase] = useState("");
  const [editDistractors, setEditDistractors] = useState("");

  const loadDetail = useCallback((entryId: string, t: string) => {
    apiFetch<CollocationRow>(API_ROUTES.adminCollocationUpdate(entryId), { token: t })
      .then((row) => {
        setEditRow(row);
        setEditBase(row.base_word);
        setEditGap(row.gap_word ?? "");
        setEditPattern(row.pattern);
        setEditDistractors(row.distractors.join(","));
        // Đưa form sửa vào tầm mắt sau khi bấm từ bảng.
        window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
      })
      .catch(() => {
        setEditRow(null);
        setError("Entry này không phải collocation (không có detail).");
      });
  }, []);

  const refresh = useCallback((t: string, at = 0) => {
    // `collocation=1` lọc theo tồn tại của collocation_detail — đúng định nghĩa
    // spec §2.1, không phải POS='phrase' (59 hàng phrase cũ không phải collocation).
    apiFetch<VocabularyAdminPage>(`${API_ROUTES.adminVocabulary}?collocation=1&offset=${at}`, {
      token: t,
    })
      .then((page) => {
        setEntries(page.items);
        setTotal(page.total);
      })
      .catch(() => setError("Không tải được danh sách collocation."));
  }, []);

  useEffect(() => {
    if (!token) return;
    apiFetch<TopicAdmin[]>(API_ROUTES.adminTopics, { token })
      .then(setTopics)
      .catch(() => {});
    refresh(token);
  }, [token, refresh]);

  async function publish(id: string) {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(API_ROUTES.adminVocabularyPublish(id), { method: "POST", token });
      refresh(token, offset);
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

  async function parse() {
    if (!token) return;
    setNotice(null);
    setError(null);
    setBusy(true);
    try {
      setParsed(
        await apiFetch<CollocationParseResponse>(API_ROUTES.adminCollocationParse, {
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
      const result = await apiFetch<CommitResult>(API_ROUTES.adminCollocationCommit, {
        method: "POST",
        token,
        body: JSON.stringify({ rows: parsed.rows, topic_id: topicId || null }),
      });
      setNotice(
        `Đã lưu ${result.created} collocation ở dạng nháp${result.skipped ? `, bỏ qua ${result.skipped}` : ""}.`,
      );
      setParsed(null);
      setRaw("");
      if (token) refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được.");
    } finally {
      setBusy(false);
    }
  }

  async function patchDetail() {
    if (!token || !editEntryId) return;
    setBusy(true);
    setError(null);
    try {
      const body: CollocationUpdate = {
        base_word: editBase,
        gap_word: editGap,
        pattern: editPattern,
        distractors: editDistractors
          .split(",")
          .map((word) => word.trim())
          .filter(Boolean),
      };
      await apiFetch(API_ROUTES.adminCollocationUpdate(editEntryId), {
        method: "PATCH",
        token,
        body: JSON.stringify(body),
      });
      setNotice("Đã cập nhật collocation detail.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không sửa được.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page>
      <PageHeader
        title="Collocation"
        description="Nhập cụm từ ghép: parse → duyệt → commit, cùng pipeline từ vựng. Commit luôn ở dạng nháp."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && (
        <div className="mb-4">
          <Alert tone="ok">{notice}</Alert>
        </div>
      )}

      <Panel className="p-5">
        <Field
          label="Dán hàng loạt"
          hint="headword | base | gap | pattern | nghĩa_VN | example_EN | example_VN | distractors"
        >
          <Textarea
            value={raw}
            onChange={(event) => setRaw(event.target.value)}
            rows={6}
            placeholder={PLACEHOLDER}
            className="font-data text-small"
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
      </Panel>

      {parsed && (
        <>
          <ParsePreview
            parsed={parsed}
            render={(row) => (
              <>
                <span className="font-semibold">{row.headword || "—"}</span>
                <span className="ml-2 text-label uppercase text-ink-faint">{row.pattern}</span>
                {row.gap_word && <span className="ml-2 text-ink-muted">gap: {row.gap_word}</span>}
                {row.meaning_vi && <span className="ml-2 text-ink-muted">· {row.meaning_vi}</span>}
              </>
            )}
          />
          <Button
            className="mt-4"
            disabled={parsed.ok_count === 0 || busy}
            onClick={() => void commit()}
          >
            {busy && <Spinner />}
            Lưu {parsed.ok_count} collocation ở dạng nháp
          </Button>
        </>
      )}

      <section className="mt-12">
        <SectionHeader title={`Tất cả collocation (${total})`} />
        {!entries && <SkeletonList rows={3} />}

        {entries?.length === 0 && (
          <EmptyState
            icon={Library}
            title="Chưa có collocation nào"
            description="Dán nội dung ở trên và bấm Kiểm tra để bắt đầu."
          />
        )}

        <div className="space-y-2">
          {entries?.map((entry) => (
            <Panel key={entry.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <span className="font-semibold">{entry.headword}</span>
                <PublishTag status={entry.status} />
                <AudioTag
                  state={
                    entry.audio.some((slot) => slot.state === "missing")
                      ? "missing"
                      : entry.audio.some((slot) => slot.state === "stale")
                        ? "stale"
                        : "current"
                  }
                />
                <p className="truncate text-small text-ink-muted">{entry.meaning_vi}</p>
              </div>
              {entry.status !== "published" && (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!entry.publishable || !canPublish}
                  onClick={() => void publish(entry.id)}
                  title={
                    !canPublish
                      ? "Chỉ admin mới publish được"
                      : entry.publishable
                        ? "Xuất bản collocation này"
                        : "Audio chưa khớp với text — chạy backfill_audio"
                  }
                >
                  <Send size={14} strokeWidth={2} aria-hidden />
                  Xuất bản
                </Button>
              )}
              <Button
                size="sm"
                variant="secondary"
                onClick={() => token && loadDetail(entry.id, token)}
              >
                <Pencil size={14} strokeWidth={2} aria-hidden />
                Sửa
              </Button>
            </Panel>
          ))}
        </div>

        <Pager
          total={total}
          limit={PAGE_SIZE}
          offset={offset}
          onOffset={(next) => {
            setOffset(next);
            if (token) refresh(token, next);
          }}
        />
      </section>

      <section className="mt-12">
        <SectionHeader title="Sửa sau commit" />
        <Panel className="p-5">
          <p className="text-small text-ink-muted">
            Nhập entry id của một collocation đã commit để sửa base/gap/pattern/distractors.
            Distractor sai là lỗi máy không thấy được — đây là chỗ người duyệt sửa.
          </p>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <Field label="Entry ID">
              <input
                value={editEntryId}
                onChange={(event) => setEditEntryId(event.target.value)}
                placeholder="uuid của entry"
                className="w-72 rounded border border-rule bg-panel px-3 py-2 font-data text-small"
              />
            </Field>
            <Button
              variant="secondary"
              disabled={!editEntryId.trim() || busy}
              onClick={() => editEntryId && token && loadDetail(editEntryId.trim(), token)}
            >
              Tải
            </Button>
          </div>

          {editRow && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Field label="Base word">
                <input
                  value={editBase}
                  onChange={(event) => setEditBase(event.target.value)}
                  className="w-full rounded border border-rule bg-panel px-3 py-2 text-small"
                />
              </Field>
              <Field label="Gap word (để trống = không ra đề)">
                <input
                  value={editGap}
                  onChange={(event) => setEditGap(event.target.value)}
                  className="w-full rounded border border-rule bg-panel px-3 py-2 text-small"
                />
              </Field>
              <Field label="Pattern">
                <Select
                  value={editPattern}
                  onChange={(event) => setEditPattern(event.target.value)}
                >
                  {PATTERNS.map((pattern) => (
                    <option key={pattern} value={pattern}>
                      {pattern}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Distractors (phân tách bởi dấu phẩy, tối đa 3)">
                <input
                  value={editDistractors}
                  onChange={(event) => setEditDistractors(event.target.value)}
                  className="w-full rounded border border-rule bg-panel px-3 py-2 text-small"
                />
              </Field>
              <div>
                <Button disabled={busy} onClick={() => void patchDetail()}>
                  {busy && <Spinner />}
                  Lưu thay đổi
                </Button>
              </div>
            </div>
          )}
        </Panel>
      </section>

      {!parsed && !editRow && entries?.length === 0 && (
        <div className="mt-8">
          <EmptyState
            icon={Library}
            title="Chưa có gì để duyệt"
            description="Dán nội dung ở trên hoặc tải một detail để sửa."
          />
        </div>
      )}

      <div className="mt-12">
        <BackfillHint />
      </div>
    </Page>
  );
}
