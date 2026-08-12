"use client";

import {
  API_ROUTES,
  type FacetCatalog,
  type LabelValue,
  type LlmStats,
  type QuestionLabelRow,
} from "@toeic-pilot/shared";
import { Bell, ListChecks, Tags } from "lucide-react";
import { useEffect, useState } from "react";

import { FacetAccuracyTable } from "@/components/facet-accuracy-table";
import { Modal } from "@/components/modal";
import {
  Alert,
  Button,
  EmptyState,
  Page,
  PageHeader,
  SectionHeader,
  Select,
  SkeletonList,
  Tag,
  ValueTile,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

type Envelope<T> = { items: T[]; total: number; limit: number; offset: number };
type Filter = "all" | "unlabelled" | "unreviewed" | "disagreeing";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unlabelled", label: "Unlabelled" },
  { value: "unreviewed", label: "Unreviewed" },
  { value: "disagreeing", label: "Corrected" },
];

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/** Mặt nào áp dụng cho part này, ở tầng sở hữu nào. */
function facetsFor(catalog: FacetCatalog[], part: number, owner: string): FacetCatalog[] {
  return catalog.filter(
    (facet) => facet.owner === owner && facet.labels.some((label) => label.parts.includes(part)),
  );
}

export default function SkillTagsPage() {
  const { status, token } = useRequireSession({ canEdit: true });

  const [stats, setStats] = useState<LlmStats | null>(null);
  const [catalog, setCatalog] = useState<FacetCatalog[]>([]);
  const [rows, setRows] = useState<Envelope<QuestionLabelRow> | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [truncated, setTruncated] = useState(0);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState<QuestionLabelRow | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Màn này dựng theo CÂY (đề → part), và cây thì không được phân trang danh
  // sách phẳng phía sau: cắt ở 50 sẽ hiện một đề có ba trong mười sáu câu mà
  // không gì nói phần còn lại tồn tại.
  const limit = 200;

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function load(bearer: string) {
      const [nextStats, nextCatalog] = await Promise.all([
        apiFetch<LlmStats>(API_ROUTES.adminAiStats, { token: bearer }),
        apiFetch<FacetCatalog[]>(API_ROUTES.adminAiLabelCatalog, { token: bearer }),
      ]);
      if (cancelled) return;
      setStats(nextStats);
      setCatalog(nextCatalog);
    }
    load(token).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token, reloadKey]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function load(bearer: string) {
      const page = await apiFetch<Envelope<QuestionLabelRow>>(
        `${API_ROUTES.adminAiLabels}?state=${filter}&limit=${limit}`,
        { token: bearer },
      );
      if (cancelled) return;
      setRows(page);
      setTruncated(page.total > page.items.length ? page.total : 0);
    }
    load(token).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token, filter, reloadKey]);

  async function ringDoorbell() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const ack = await apiFetch<{ queued: boolean }>(API_ROUTES.adminAiSkillTagRequests, {
        method: "POST",
        token,
      });
      // Nói đúng thứ đã xảy ra: đã ĐẶT YÊU CẦU, chưa phải đã gắn xong. Endpoint
      // trả 202 vì API không gắn nhãn được — nó chỉ rung chuông cho worker.
      setNotice(
        ack.queued
          ? "The worker has been notified. Labels appear gradually — reload in a few minutes."
          : "Recorded. The doorbell did not reach the worker, but its periodic sweep will still run.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not send the request");
    } finally {
      setBusy(false);
    }
  }

  /** Ghi nhãn cho MỘT mặt — của câu, hoặc của nhóm nếu mặt đó thuộc về nhóm. */
  async function save(row: QuestionLabelRow, facet: FacetCatalog, code: string) {
    if (!token || !code) return;
    setError(null);
    const setLevel = facet.owner === "set";
    if (setLevel && !row.set_id) return;
    try {
      await apiFetch<LabelValue>(
        setLevel
          ? API_ROUTES.adminAiSetLabelReview(row.set_id as string)
          : API_ROUTES.adminAiLabelReview(row.id),
        { method: "PATCH", token, body: JSON.stringify({ facet: facet.key, code }) },
      );
      setReloadKey((key) => key + 1);
      setEditing(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save the label");
    }
  }

  if (status === "loading") {
    return (
      <Page>
        <SkeletonList rows={6} />
      </Page>
    );
  }

  const coverage =
    stats && stats.questions_total > 0 ? stats.questions_labelled / stats.questions_total : 0;
  const reviewed = (stats?.facets ?? []).reduce((sum, f) => sum + f.reviewed, 0);
  const labelled = (stats?.facets ?? []).reduce((sum, f) => sum + f.labelled, 0);

  return (
    <Page>
      <PageHeader
        title="Skill labels"
        description="The machine proposes, a human confirms. The gap between the two columns is the accuracy KPI."
        actions={
          <Button onClick={ringDoorbell} disabled={busy}>
            <Bell size={15} strokeWidth={1.75} aria-hidden />
            {busy ? "Sending…" : "Run labelling"}
          </Button>
        }
      />

      {notice && (
        <div className="mb-6">
          <Alert tone="ok">{notice}</Alert>
        </div>
      )}
      {error && (
        <div className="mb-6">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      <section className="grid gap-3 sm:grid-cols-2">
        <ValueTile
          Icon={Tags}
          label="Questions labelled"
          value={stats ? pct(coverage) : null}
          hint={`${stats?.questions_labelled ?? 0} / ${stats?.questions_total ?? 0} questions — the bar is 100%`}
          empty="no questions yet"
        />
        <ValueTile
          Icon={ListChecks}
          label="Labels reviewed"
          value={stats ? String(reviewed) : null}
          unit={`/ ${labelled}`}
          hint="counted by LABEL, not by question — a Part 6 question has three, each reviewed separately"
          empty="no labels yet"
        />
      </section>

      <section className="mt-10">
        <SectionHeader title="Accuracy by facet" />
        <FacetAccuracyTable facets={stats?.facets ?? []} />
      </section>

      <section className="mt-10">
        <SectionHeader
          title="Review labels"
          aside={
            <Select
              className="w-auto"
              value={filter}
              onChange={(event) => setFilter(event.target.value as Filter)}
              aria-label="Filter questions"
            >
              {FILTERS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          }
        />
        {rows === null ? (
          <SkeletonList rows={5} />
        ) : rows.items.length === 0 ? (
          <EmptyState
            title="Nothing here"
            description="Change the filter, or press Run labelling so the worker picks up what is missing."
          />
        ) : (
          <>
            {truncated > 0 && (
              <p className="mb-3 rounded border border-warn bg-warn-tint px-3.5 py-2.5 text-small">
                Showing the first {limit} of {truncated}. This screen is a test → part tree, so it
                cannot paginate yet — narrow the filter before the list outgrows this.
              </p>
            )}
            <div className="space-y-2">
              {groupRows(rows.items).map((test) => (
                <details key={test.key} className="rounded border border-rule-strong bg-panel">
                  <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-3 px-4 py-3">
                    <span className="font-semibold">{test.title}</span>
                    <Counted done={test.reviewed} total={test.labels} />
                  </summary>
                  <div className="border-t border-rule px-3 pb-3 pt-1">
                    {test.parts.map((part) => (
                      <details key={part.part} className="mt-2 rounded border border-rule">
                        <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-3 px-3 py-2 text-small">
                          <span className="font-semibold">Part {part.part}</span>
                          <Counted done={part.reviewed} total={part.labels} />
                        </summary>
                        <ul className="border-t border-rule">
                          {part.rows.map((row) => (
                            <li key={row.id}>
                              <button
                                type="button"
                                onClick={() => setEditing(row)}
                                className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 border-b border-rule px-3 py-2 text-left text-small last:border-0 hover:bg-recess"
                              >
                                <span className="w-12 shrink-0 font-data tabular-nums">
                                  {row.question_number ? `#${row.question_number}` : "—"}
                                </span>
                                <span className="min-w-0 flex-1 truncate">
                                  {row.prompt_text ?? (
                                    <span className="text-ink-faint">spoken only</span>
                                  )}
                                </span>
                                <span className="flex shrink-0 flex-wrap gap-1">
                                  {[...row.labels, ...row.set_labels].map((label) => (
                                    <Tag
                                      key={label.facet}
                                      tone={label.reviewed_at ? "ok" : undefined}
                                    >
                                      {/* Dấu ~ = máy đoán, chưa ai xác nhận. */}
                                      {label.reviewed_at ? label.code : `~${label.code}`}
                                    </Tag>
                                  ))}
                                  {row.labels.length === 0 && row.set_labels.length === 0 && (
                                    <span className="text-ink-faint">none</span>
                                  )}
                                </span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      </details>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          </>
        )}
      </section>

      {editing && (
        // `key` đặt lại state theo cách của React, thay cho đồng bộ bằng effect.
        <ReviewDialog
          key={editing.id}
          row={editing}
          catalog={catalog}
          onClose={() => setEditing(null)}
          onSave={save}
        />
      )}
    </Page>
  );
}

/**
 * Hộp thoại duyệt: MỘT ô chọn cho mỗi mặt áp dụng với câu này.
 *
 * Mặt của ngữ liệu chung được đánh dấu rõ, vì sửa nó ảnh hưởng cả nhóm câu chứ
 * không riêng câu đang mở — người duyệt phải biết điều đó trước khi bấm.
 */
function ReviewDialog({
  row,
  catalog,
  onClose,
  onSave,
}: {
  row: QuestionLabelRow;
  catalog: FacetCatalog[];
  onClose: () => void;
  onSave: (row: QuestionLabelRow, facet: FacetCatalog, code: string) => Promise<void>;
}) {
  const current = new Map<string, LabelValue>();
  for (const label of [...row.labels, ...row.set_labels]) current.set(label.facet, label);

  const applicable = [
    ...facetsFor(catalog, row.part, "question"),
    ...(row.set_id ? facetsFor(catalog, row.part, "set") : []),
  ];

  return (
    <Modal
      open
      onClose={onClose}
      title={`Question ${row.question_number ?? "?"} · Part ${row.part}`}
      description={row.test_title ?? undefined}
    >
      <div className="space-y-4">
        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">Prompt</p>
          <p className="mt-1 text-small">
            {row.prompt_text ?? (
              <span className="text-ink-faint">
                This part prints no prompt — it is spoken only.
              </span>
            )}
          </p>
        </div>

        {applicable.map((facet) => (
          <FacetPicker
            key={facet.key}
            facet={facet}
            part={row.part}
            value={current.get(facet.key)}
            onSave={(code) => void onSave(row, facet, code)}
          />
        ))}
      </div>
    </Modal>
  );
}

function FacetPicker({
  facet,
  part,
  value,
  onSave,
}: {
  facet: FacetCatalog;
  part: number;
  value: LabelValue | undefined;
  onSave: (code: string) => void;
}) {
  const [picked, setPicked] = useState(value?.code ?? "");
  const usable = facet.labels.filter((label) => label.parts.includes(part));
  const changed = picked !== "" && picked !== value?.code;

  return (
    <div className="border-t border-rule pt-3">
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
          {facet.label_vi}
          {facet.owner === "set" && (
            // Nói rõ phạm vi TRƯỚC khi bấm: sửa chủ đề một hội thoại Part 3 đổi
            // nhãn của cả ba câu, và người duyệt không đoán ra điều đó từ giao diện.
            <span className="ml-2 font-normal normal-case text-ink-faint">
              applies to the whole set
            </span>
          )}
        </p>
        {value?.proposed_code && value.proposed_code !== value.code && (
          <span className="font-data text-label text-ink-faint">
            machine said {value.proposed_code}
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Select
          className="w-auto min-w-[16rem]"
          value={picked}
          onChange={(event) => setPicked(event.target.value)}
          aria-label={facet.label_vi}
        >
          <option value="" disabled>
            not set
          </option>
          {usable.map((label) => (
            <option key={label.code} value={label.code}>
              {label.label_vi}
            </option>
          ))}
        </Select>
        <Button onClick={() => onSave(picked)} disabled={picked === ""} size="sm">
          {/*
           * Hai nhãn nút cho hai ý nghĩa khác nhau dù cùng một endpoint: chỉ
           * "Xác nhận đúng" giữ code = proposed_code, tức là chỉ nó đóng góp
           * vào KPI độ đúng. Không có nút này thì hành động hay gặp nhất khi
           * duyệt — xác nhận máy đúng — là bất khả thi, và KPI vĩnh viễn 0%.
           */}
          {changed ? "Save new label" : "Confirm correct"}
        </Button>
        {value?.reviewed_at && <Tag tone="ok">reviewed</Tag>}
      </div>
    </div>
  );
}

type PartGroup = { part: number; rows: QuestionLabelRow[]; labels: number; reviewed: number };
type TestGroup = {
  key: string;
  title: string;
  parts: PartGroup[];
  labels: number;
  reviewed: number;
};

function countLabels(rows: QuestionLabelRow[]): [number, number] {
  let total = 0;
  let reviewed = 0;
  for (const row of rows) {
    for (const label of row.labels) {
      total += 1;
      if (label.reviewed_at) reviewed += 1;
    }
  }
  return [total, reviewed];
}

/**
 * Gom câu hỏi theo đề rồi theo part.
 *
 * Câu KHÔNG thuộc đề nào vẫn hiện, và hiện CUỐI: chúng có thật, và bỏ đi thì
 * tổng trên trang không khớp tổng của bộ lọc — một sai lệch không ai giải thích
 * được. Cùng lý do cây dictation giữ mục "Câu lẻ".
 *
 * Gom theo `test_slug` chứ không theo tên: dữ liệu thật có hai đề tên gần giống
 * nhau, và gom theo tên sẽ trộn chúng lại một cách trông rất hợp lý.
 */
function groupRows(rows: QuestionLabelRow[]): TestGroup[] {
  const byTest = new Map<string, QuestionLabelRow[]>();
  for (const row of rows) {
    const key = row.test_slug ?? "";
    const bucket = byTest.get(key);
    if (bucket) bucket.push(row);
    else byTest.set(key, [row]);
  }

  const groups: TestGroup[] = [];
  for (const [key, list] of byTest) {
    const byPart = new Map<number, QuestionLabelRow[]>();
    for (const row of list) {
      const bucket = byPart.get(row.part);
      if (bucket) bucket.push(row);
      else byPart.set(row.part, [row]);
    }
    const parts = [...byPart.entries()]
      .map(([part, partRows]) => {
        const sorted = partRows.sort((a, b) => (a.question_number ?? 0) - (b.question_number ?? 0));
        const [labels, reviewed] = countLabels(sorted);
        return { part, rows: sorted, labels, reviewed };
      })
      .sort((a, b) => a.part - b.part);
    const [labels, reviewed] = countLabels(list);
    groups.push({
      key: key || "(no test)",
      title: list[0].test_title ?? "Not in any test",
      parts,
      labels,
      reviewed,
    });
  }
  return groups.sort((a, b) => {
    if (a.key === "(no test)") return 1;
    if (b.key === "(no test)") return -1;
    return a.title.localeCompare(b.title, "vi");
  });
}

/** "12 / 16 nhãn đã kiểm" — con số duy nhất nói nhóm này còn việc hay không. */
function Counted({ done, total }: { done: number; total: number }) {
  return (
    <span className="whitespace-nowrap font-data text-label text-ink-faint">
      <span className={total > 0 && done === total ? "text-ok" : "text-ink-muted"}>{done}</span> /{" "}
      {total} labels reviewed
    </span>
  );
}
