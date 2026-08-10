"use client";

import {
  API_ROUTES,
  type CollectionAdmin,
  type GroupDraft,
  type ImageAssetPublic,
  type QuestionAdmin,
  type SetAdmin,
  type TestAdmin,
  type TestPartParseResponse,
} from "@toeic-pilot/shared";
import { ArrowLeft, Check, CircleAlert, Copy, ImageIcon, Pencil, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  EmptyState,
  Page,
  Field,
  Input,
  Panel,
  PublishTag,
  SectionHeader,
  Select,
  SkeletonList,
  Tag,
  Textarea,
  cx,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/*
 * Soạn một đề (ADR-007).
 *
 * Ba bước, không phải một: dán → xem trước → ghi. Bước xem trước tồn tại vì
 * `parse` **không ghi gì vào database** (ADR-005 §3.4), nên biên tập viên còn
 * cơ hội sửa trước khi có hàng nào được tạo — và đó cũng là lý do định dạng dán
 * là khối chứ không phải một dòng dài ngăn bằng dấu gạch đứng: dòng vài trăm ký
 * tự thì mắt người không soát được, mà soát được mới là điểm của bước này.
 */

// Lượt 1 mới làm phần Đọc. Part 1–4 cần audio và thuộc lượt 2 (ADR-007 §3b).
const PARTS = [5, 6, 7] as const;

const NO_COLLECTION = "__none__";

const PLACEHOLDER: Record<number, string> = {
  5: `[QUESTION]
The board approved the ____ budget for the next quarter.
(A) annual
(B) annually
(C) annualize
(D) annuity
answer: A
source: original
explanation: Cần một tính từ bổ nghĩa cho "budget".`,
  6: `[PASSAGE] Thư báo lịch bảo trì
Dear tenants,

The lobby entrance will be closed (131) ____ Wednesday. During this time,
please use the side entrance on Le Loi Street. Deliveries will (132) ____ be
redirected there. We expect the work to finish by Friday.

[QUESTION]
(131)
(A) since
(B) from
(C) during
(D) until
answer: B
source: original
explanation: "from + mốc thời gian" chỉ thời điểm bắt đầu.

[QUESTION]
(132)
(A) also
(B) never
(C) rarely
(D) instead
answer: A
source: original
explanation: Câu này bổ sung thêm một việc cùng chiều với câu trước.`,
  7: `[PASSAGE] Thông báo bảo trì
The lobby entrance will be closed from Wednesday.
Please use the side entrance on Le Loi Street.

[QUESTION]
What is the notice mainly about?
(A) A change of address
(B) Building maintenance
(C) A new tenant
(D) A rent increase
answer: B
source: original
explanation: Đoạn văn nói về việc đóng cửa sảnh để bảo trì.`,
};

export default function AdminTestPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const { status, token, canPublish } = useRequireSession({ canEdit: true });

  const [test, setTest] = useState<TestAdmin | null>(null);
  const [collections, setCollections] = useState<CollectionAdmin[]>([]);
  const [sets, setSets] = useState<SetAdmin[]>([]);
  const [library, setLibrary] = useState<ImageAssetPublic[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [questions, setQuestions] = useState<QuestionAdmin[] | null>(null);
  const [part, setPart] = useState<number>(5);
  const [raw, setRaw] = useState("");
  const [parsed, setParsed] = useState<TestPartParseResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    (t: string) => {
      apiFetch<TestAdmin>(API_ROUTES.adminTest(slug), { token: t })
        .then(setTest)
        .catch(() => setError("Không mở được đề này."));
      apiFetch<QuestionAdmin[]>(API_ROUTES.adminTestQuestions(slug), { token: t })
        .then(setQuestions)
        .catch(() => {});
      apiFetch<CollectionAdmin[]>(API_ROUTES.adminTestCollections, { token: t })
        .then(setCollections)
        .catch(() => {});
      apiFetch<SetAdmin[]>(API_ROUTES.adminTestSets(slug), { token: t })
        .then(setSets)
        .catch(() => {});
      apiFetch<ImageAssetPublic[]>(API_ROUTES.adminImages, { token: t })
        .then(setLibrary)
        .catch(() => {});
    },
    [slug],
  );

  useEffect(() => {
    if (token) refresh(token);
  }, [token, refresh]);

  async function run<T>(work: () => Promise<T>, done?: (value: T) => void) {
    if (!token || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      done?.(await work());
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Có lỗi xảy ra.");
    } finally {
      setBusy(false);
    }
  }

  const parse = () =>
    run(
      () =>
        apiFetch<TestPartParseResponse>(API_ROUTES.adminTestPartParse(slug, part), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ raw_text: raw }),
        }),
      setParsed,
    );

  const commit = () =>
    run(
      () =>
        apiFetch<TestAdmin>(API_ROUTES.adminTestParts(slug), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ part, groups: parsed?.groups ?? [] }),
        }),
      (updated) => {
        setTest(updated);
        setParsed(null);
        setRaw("");
        setNotice(`Đã ghi vào Part ${part}. Nội dung ở trạng thái nháp cho tới khi xuất bản.`);
        if (token) refresh(token);
      },
    );

  const publishQuestion = (id: string) =>
    run(
      () =>
        apiFetch<QuestionAdmin>(API_ROUTES.adminQuestionPublish(id), {
          method: "POST",
          token: token ?? undefined,
        }),
      () => token && refresh(token),
    );

  const moveToCollection = (target: string) =>
    run(
      () =>
        apiFetch<TestAdmin>(API_ROUTES.adminTest(slug), {
          method: "PATCH",
          token: token ?? undefined,
          // `null` là *gỡ khỏi bộ*, khác hẳn với không gửi khoá này. Chuỗi rỗng
          // của <select> phải được dịch sang null ở đây, nếu không nó sẽ đi
          // xuống dưới dạng "" và biến thành một slug không tồn tại.
          body: JSON.stringify({ collection_slug: target === NO_COLLECTION ? null : target }),
        }),
      setTest,
    );

  const saveQuestion = (id: string, changes: Record<string, unknown>) =>
    run(
      () =>
        apiFetch<QuestionAdmin>(API_ROUTES.adminQuestion(id), {
          method: "PATCH",
          token: token ?? undefined,
          body: JSON.stringify(changes),
        }),
      () => {
        setEditing(null);
        if (token) refresh(token);
      },
    );

  const assignPassageImage = (setId: string, slot: number, imageId: string | null) =>
    run(
      () =>
        apiFetch<SetAdmin>(API_ROUTES.adminPassageImage(setId), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ slot, image_id: imageId }),
        }),
      () => {
        if (token) refresh(token);
      },
    );

  const publishTest = () =>
    run(
      () =>
        apiFetch<TestAdmin>(API_ROUTES.adminTestPublish(slug), {
          method: "POST",
          token: token ?? undefined,
        }),
      (updated) => {
        setTest(updated);
        setNotice("Đề đã được xuất bản.");
      },
    );

  if (status === "loading" || (test === null && error === null)) {
    return (
      <Page>
        <SkeletonList rows={4} />
      </Page>
    );
  }

  if (test === null) {
    return (
      <Page>
        <EmptyState
          icon={CircleAlert}
          title="Không mở được đề này"
          description={error ?? "Có thể nó đã bị gỡ."}
        />
      </Page>
    );
  }

  const inPart = (questions ?? []).filter((question) => question.part === part);
  const allPublished =
    (questions ?? []).length > 0 && (questions ?? []).every((q) => q.status === "published");

  return (
    <Page>
      <Link
        href="/admin/tests"
        className="inline-flex items-center gap-1.5 text-small font-semibold text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={14} strokeWidth={2} aria-hidden />
        Đề thi
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1>{test.title}</h1>
            <PublishTag status={test.status} />
          </div>
          <p className="mt-1 text-small text-ink-muted">
            <span className="font-data">{test.slug}</span> ·{" "}
            <span className="font-data tabular-nums">{test.question_count}</span> câu
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-small text-ink-muted">Thuộc bộ đề</span>
            <Select
              value={test.collection_slug ?? NO_COLLECTION}
              onChange={(event) => void moveToCollection(event.target.value)}
              disabled={busy}
              className="w-auto"
            >
              <option value={NO_COLLECTION}>— chưa thuộc bộ nào —</option>
              {collections.map((collection) => (
                <option key={collection.id} value={collection.slug}>
                  {collection.title}
                </option>
              ))}
            </Select>
            {/* Đề không thuộc bộ nào thì người học không có đường nào tới nó.
                Nói ra ở đây, vì nó trông y hệt một đề bình thường. */}
            {test.collection_slug === null && (
              <span className="text-small text-warn">Người học chưa nhìn thấy đề này</span>
            )}
          </div>
        </div>
        {canPublish && test.status !== "published" && (
          <Button
            onClick={() => void publishTest()}
            disabled={busy || !allPublished}
            title={
              allPublished
                ? undefined
                : "Còn câu chưa xuất bản — xuất bản từng câu trước, rồi mới xuất bản đề"
            }
          >
            <Send size={14} strokeWidth={2} aria-hidden />
            Xuất bản đề
          </Button>
        )}
      </div>

      {error && (
        <div className="mt-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}
      {notice && (
        <div className="mt-4">
          <Alert tone="ok">{notice}</Alert>
        </div>
      )}

      {/* Thanh part. Part 1–4 hiện ra nhưng khoá lại, chứ không giấu đi: giấu
          thì người soạn tưởng đề chỉ có ba phần và đó là thiết kế. */}
      <div className="mt-6 flex flex-wrap items-center gap-1.5">
        {[1, 2, 3, 4, 5, 6, 7].map((value) => {
          const reading = PARTS.includes(value as (typeof PARTS)[number]);
          const summary = test.parts.find((p) => p.part === value);
          return (
            <button
              key={value}
              type="button"
              disabled={!reading}
              onClick={() => {
                setPart(value);
                setParsed(null);
              }}
              title={reading ? undefined : "Phần nghe thuộc lượt sau — cần audio"}
              className={cx(
                "inline-flex items-center gap-1.5 rounded border px-3 py-1.5 text-small font-semibold disabled:opacity-45",
                part === value
                  ? "border-rule-strong bg-recess text-action-ink"
                  : "border-rule bg-panel hover:border-rule-strong",
              )}
            >
              Part {value}
              {summary && (
                <span className="font-data tabular-nums text-label text-ink-faint">
                  {summary.published_count}/{summary.question_count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <section className="mt-6">
        <SectionHeader
          title={`Dán nội dung Part ${part}`}
          aside={<CopyFormatButton template={PLACEHOLDER[part]} part={part} />}
        />
        {/* Mốc và khoá bằng tiếng Anh ASCII — dạng có dấu từng hỏng vì macOS
            trả chữ Â ở dạng phân rã, và hai chuỗi thì hiện lên giống hệt nhau.
            Nội dung `explanation` viết tiếng Việt vì người học đọc nó. */}
        <p className="mb-2 text-small text-ink-muted">
          Mốc và khoá viết bằng tiếng Anh: <span className="font-data">[PASSAGE]</span>,{" "}
          <span className="font-data">[QUESTION]</span>, <span className="font-data">answer:</span>,{" "}
          <span className="font-data">source:</span>,{" "}
          <span className="font-data">explanation:</span>. Phần giải thích thì viết tiếng Việt —
          người học sẽ đọc nó.
        </p>
        <Textarea
          value={raw}
          onChange={(event) => setRaw(event.target.value)}
          rows={12}
          className="font-data text-small"
          placeholder={PLACEHOLDER[part]}
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={() => void parse()} disabled={busy || !raw.trim()}>
            Phân tích
          </Button>
          {parsed && parsed.error_count === 0 && parsed.groups.length > 0 && (
            <Button onClick={() => void commit()} disabled={busy}>
              Ghi {parsed.groups.reduce((sum, g) => sum + g.questions.length, 0)} câu vào đề
            </Button>
          )}
        </div>

        {parsed && <GroupPreview parsed={parsed} />}
      </section>

      {part !== 5 && (
        <section className="mt-10">
          <SectionHeader title={`Ngữ liệu Part ${part}`} />
          {sets.filter((stimulus) => stimulus.part === part).length === 0 ? (
            <p className="text-small text-ink-muted">Phần này chưa có cụm nào.</p>
          ) : (
            <div className="space-y-3">
              {sets
                .filter((stimulus) => stimulus.part === part)
                .map((stimulus) => (
                  <SetPanel
                    key={stimulus.id}
                    stimulus={stimulus}
                    library={library}
                    busy={busy}
                    onAssign={(slot, imageId) =>
                      void assignPassageImage(stimulus.id, slot, imageId)
                    }
                    // Chỉ Part 7 có ảnh. Part 6 là Text Completion — một đoạn
                    // văn có các chỗ trống, toàn chữ.
                    allowImages={part === 7}
                  />
                ))}
            </div>
          )}
        </section>
      )}

      <section className="mt-10">
        <SectionHeader
          title={`Câu hỏi Part ${part}`}
          aside={
            <span className="text-small text-ink-muted">
              <span className="font-data tabular-nums">{inPart.length}</span> câu
            </span>
          }
        />
        {inPart.length === 0 ? (
          <p className="text-small text-ink-muted">Phần này chưa có câu nào.</p>
        ) : (
          <div className="space-y-2">
            {inPart.map((question) => (
              <Panel key={question.id} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-data tabular-nums font-semibold">
                        Câu {question.number}
                      </span>
                      <PublishTag status={question.status} />
                      <Tag>{question.source}</Tag>
                    </div>
                    <p className="mt-1.5 text-small">{question.prompt_text}</p>
                    <ul className="mt-2 space-y-0.5">
                      {question.options.map((option) => (
                        <li
                          key={option.label}
                          className={cx(
                            "text-small",
                            option.is_correct ? "font-semibold text-ok" : "text-ink-muted",
                          )}
                        >
                          ({option.label}) {option.content}
                        </li>
                      ))}
                    </ul>
                    {question.problems.map((problem) => (
                      <p
                        key={problem}
                        className="mt-1.5 flex items-center gap-1.5 text-small text-alert"
                      >
                        <CircleAlert size={14} strokeWidth={2} aria-hidden className="shrink-0" />
                        {problem}
                      </p>
                    ))}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      size="sm"
                      variant="quiet"
                      onClick={() => setEditing(editing === question.id ? null : question.id)}
                    >
                      <Pencil size={13} strokeWidth={2} aria-hidden />
                      {editing === question.id ? "Đóng" : "Sửa"}
                    </Button>
                    {canPublish && question.status !== "published" && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => void publishQuestion(question.id)}
                        disabled={busy || question.problems.length > 0}
                        title={
                          question.problems.length > 0
                            ? "Sửa các lỗi ở trên rồi mới xuất bản được"
                            : undefined
                        }
                      >
                        Xuất bản
                      </Button>
                    )}
                  </div>
                </div>

                {editing === question.id && (
                  <QuestionEditor
                    question={question}
                    busy={busy}
                    onSave={(changes) => void saveQuestion(question.id, changes)}
                  />
                )}
              </Panel>
            ))}
          </div>
        )}
      </section>
    </Page>
  );
}

function GroupPreview({ parsed }: { parsed: TestPartParseResponse }) {
  return (
    <Panel className="mt-4 overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-rule bg-recess px-4 py-2.5">
        <Tag tone="ok">{parsed.ok_count} cụm hợp lệ</Tag>
        {parsed.error_count > 0 && <Tag tone="alert">{parsed.error_count} cụm lỗi</Tag>}
        {/* Câu này phải nói ra, vì nó là toàn bộ lý do bước xem trước tồn tại. */}
        <span className="text-small text-ink-muted">Chưa có gì được ghi vào cơ sở dữ liệu</span>
      </div>
      <ul className="divide-y divide-rule">
        {parsed.groups.map((group) => (
          <GroupRow key={group.line} group={group} />
        ))}
      </ul>
    </Panel>
  );
}

function GroupRow({ group }: { group: GroupDraft }) {
  const broken = group.problems.length > 0 || group.questions.some((q) => q.problems.length > 0);
  return (
    <li className={cx("px-4 py-3", broken && "bg-alert-tint/50")}>
      {group.title && <p className="text-small font-semibold">{group.title}</p>}

      {group.passages.map((passage, index) => (
        <p
          key={index}
          className="mt-1.5 line-clamp-3 whitespace-pre-wrap rounded border border-rule bg-recess p-2 text-small text-ink-muted"
        >
          {passage}
        </p>
      ))}

      {group.problems.map((problem) => (
        <p key={problem} className="mt-1.5 flex items-center gap-1.5 text-small text-alert">
          <CircleAlert size={14} strokeWidth={2} aria-hidden className="shrink-0" />
          {problem}
        </p>
      ))}

      {group.questions.map((question) => (
        <div key={question.line} className="mt-2.5 border-l-2 border-rule pl-3">
          <div className="flex items-start gap-2">
            <span className="w-6 shrink-0 text-right font-data text-small text-ink-faint">
              {question.line}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-small">{question.prompt_text || <em>thiếu đề bài</em>}</p>
              <p className="mt-0.5 text-small text-ink-muted">
                {question.options.map((option) => (
                  <span
                    key={option.label}
                    className={cx("mr-3", option.is_correct && "font-semibold text-ok")}
                  >
                    ({option.label}) {option.content}
                  </span>
                ))}
              </p>
              {question.problems.map((problem) => (
                <p key={problem} className="mt-1 flex items-center gap-1.5 text-small text-alert">
                  <CircleAlert size={14} strokeWidth={2} aria-hidden className="shrink-0" />
                  {problem}
                </p>
              ))}
            </div>
          </div>
        </div>
      ))}
    </li>
  );
}

function CopyFormatButton({ template, part }: { template: string; part: number }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  /*
   * Sao chép CHÍNH chuỗi đang làm placeholder, không phải một bản mẫu viết
   * riêng: hai chuỗi mô tả cùng một định dạng thì sẽ lệch nhau, và bản lệch là
   * bản người ta dán vào — trong khi bản đúng là bản họ chỉ nhìn thấy mờ mờ.
   */
  async function copy() {
    try {
      // `navigator.clipboard` chỉ tồn tại ở secure context. Thiếu nó thì phải
      // NÓI RA chứ không im lặng không làm gì — cùng bài học với trình dán trả
      // về 0 cụm và 0 lỗi.
      if (!navigator.clipboard) throw new Error("no clipboard");
      // Chạy đua với đồng hồ, vì `writeText` có thể **không bao giờ settle**:
      // khi trình duyệt chặn (thiếu user activation, hoặc đang chờ một hộp xin
      // quyền không hiện ra), promise treo vô hạn. Không có nhánh nào chạy,
      // nút đứng im, và người dùng bấm lại vài lần rồi bỏ cuộc — đúng kiểu im
      // lặng mà trình dán vừa phải sửa. Đã gặp thật khi kiểm bằng trình duyệt.
      await Promise.race([
        navigator.clipboard.writeText(template),
        new Promise((_, reject) => window.setTimeout(() => reject(new Error("timeout")), 1500)),
      ]);
      setState("copied");
      window.setTimeout(() => setState("idle"), 2000);
    } catch {
      setState("failed");
      window.setTimeout(() => setState("idle"), 4000);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {state === "failed" && (
        <span className="text-small text-alert">Trình duyệt chặn — bấm vào ô mẫu rồi copy tay</span>
      )}
      <Button
        size="sm"
        variant="quiet"
        onClick={() => void copy()}
        title={`Chép mẫu định dạng Part ${part} vào clipboard`}
      >
        {state === "copied" ? (
          <>
            <Check size={14} strokeWidth={2} aria-hidden />
            Đã chép
          </>
        ) : (
          <>
            <Copy size={14} strokeWidth={2} aria-hidden />
            Chép mẫu
          </>
        )}
      </Button>
    </div>
  );
}

function SetPanel({
  stimulus,
  library,
  busy,
  onAssign,
  allowImages,
}: {
  stimulus: SetAdmin;
  library: ImageAssetPublic[];
  busy: boolean;
  onAssign: (slot: number, imageId: string | null) => void;
  allowImages: boolean;
}) {
  // Part 6 chỉ có MỘT đoạn văn; hiện ba ô là mô tả sai format, và nó mời người
  // soạn điền vào hai ô không tồn tại trong đề thật.
  const slots = allowImages ? stimulus.passages : stimulus.passages.slice(0, 1);

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-semibold">{stimulus.title ?? "Cụm không tên"}</p>
        <PublishTag status={stimulus.status} />
      </div>

      <div className="mt-3 space-y-3">
        {slots.map((passage) => (
          <div key={passage.slot} className="rounded border border-rule p-3">
            <p className="text-label font-semibold uppercase text-ink-muted">
              Ngữ liệu {passage.slot}
            </p>

            {passage.text ? (
              <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-small text-ink-muted">
                {passage.text}
              </p>
            ) : (
              <p className="mt-1 text-small text-ink-faint">— không có văn bản —</p>
            )}

            {passage.image_url && (
              <div className="mt-2 flex items-start gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={passage.image_url}
                  alt={passage.image_alt ?? ""}
                  className="h-20 w-28 rounded border border-rule object-cover"
                />
                <p className="min-w-0 flex-1 text-small text-ink-muted">{passage.image_alt}</p>
              </div>
            )}

            <div className={cx("mt-2 flex flex-wrap items-center gap-2", !allowImages && "hidden")}>
              <ImageIcon size={14} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
              <Select
                value={passage.image_id ?? ""}
                onChange={(event) => onAssign(passage.slot, event.target.value || null)}
                disabled={busy}
                className="w-auto"
              >
                <option value="">— không có ảnh —</option>
                {library.map((image) => (
                  <option key={image.id} value={image.id}>
                    {image.alt_text?.slice(0, 60) || image.storage_key.slice(-12)}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        ))}
      </div>

      {/* Nói ra ngay tại chỗ, vì đây là chỗ người ta sắp làm sai: phần lớn ngữ
          liệu KHÔNG cần ảnh, và bản văn bản thì tốt hơn thật. */}
      <p className="mt-3 text-small text-ink-muted">
        {allowImages
          ? "Bảng giá, lịch trình, mẫu đơn nên viết thành văn bản — đọc được bằng máy đọc màn hình, phóng to và tìm kiếm được. Ảnh dành cho biểu đồ, sơ đồ, bản đồ."
          : "Part 6 là một đoạn văn có các chỗ trống, mỗi chỗ trống là một câu hỏi. Không có ảnh và không có bài nhiều đoạn."}
      </p>
    </Panel>
  );
}

function QuestionEditor({
  question,
  busy,
  onSave,
}: {
  question: QuestionAdmin;
  busy: boolean;
  onSave: (changes: Record<string, unknown>) => void;
}) {
  const [prompt, setPrompt] = useState(question.prompt_text ?? "");
  const [explanation, setExplanation] = useState(question.explanation ?? "");
  const [correct, setCorrect] = useState(
    question.options.find((option) => option.is_correct)?.label ?? "A",
  );
  const [options, setOptions] = useState<Record<string, string>>(
    Object.fromEntries(question.options.map((option) => [option.label, option.content])),
  );

  return (
    <div className="mt-3 border-t border-rule pt-3">
      <Field label="Đề bài">
        <Textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={2} />
      </Field>

      <div className="mt-3 space-y-2">
        {question.options.map((option) => (
          <div key={option.label} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCorrect(option.label)}
              aria-pressed={correct === option.label}
              title="Đặt làm đáp án đúng"
              className={cx(
                "grid h-8 w-8 shrink-0 place-items-center rounded border font-semibold",
                correct === option.label
                  ? "border-ok bg-ok-tint text-ok"
                  : "border-rule-strong text-ink-muted hover:border-ok",
              )}
            >
              {option.label}
            </button>
            <Input
              value={options[option.label] ?? ""}
              onChange={(event) => setOptions({ ...options, [option.label]: event.target.value })}
            />
          </div>
        ))}
      </div>

      <div className="mt-3">
        <Field label="Giải thích" hint="Viết tiếng Việt — người học sẽ đọc nó.">
          <Textarea
            value={explanation}
            onChange={(event) => setExplanation(event.target.value)}
            rows={2}
          />
        </Field>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          onClick={() =>
            onSave({
              prompt_text: prompt,
              explanation: explanation || null,
              correct_label: correct,
              options,
            })
          }
          disabled={busy}
        >
          Lưu
        </Button>
        {/* Sửa một câu đã xuất bản sẽ đưa nó về nháp, và người soạn phải biết
            trước khi bấm — không phải phát hiện sau khi cái badge đổi màu. */}
        {question.status === "published" && (
          <span className="text-small text-warn">Lưu xong câu này quay về trạng thái nháp</span>
        )}
      </div>
    </div>
  );
}
