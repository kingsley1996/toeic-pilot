"use client";

import { API_ROUTES, type GrammarLessonAdmin } from "@toeic-pilot/shared";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MarkdownLite } from "@/components/markdown-lite";
import {
  Alert,
  Button,
  Field,
  Input,
  Page,
  PageHeader,
  Panel,
  Select,
  SkeletonList,
  Textarea,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

type LessonKind = "theory" | "practice";

type TopicQuestion = {
  id: string;
  part: number;
  prompt_text: string | null;
  grammar_code?: string | null;
};

type GrammarLabel = { code: string; label_vi: string };

/**
 * Trang soạn bài học — modal cũ bị chính nội dung của nó chèn ép: một trang
 * từ loại 1.000 dòng render trong hộp 34rem là không soạn được. Ở đây lý thuyết
 * là HAI CỘT đầy chiều cao trang: markdown | xem trước (SPEC-GRAMMAR §5 — cú
 * pháp viết sai hiện ra SAI chứ không nổ, nên người soạn phải thấy kết quả
 * ngay lúc gõ).
 *
 * Dùng chung cho hai route: `lessons/new/[topicId]` và `lessons/[lessonId]`.
 */
export function LessonForm({
  lessonId,
  topicId,
}: {
  lessonId: string | null;
  topicId: string | null;
}) {
  const { status, token } = useRequireSession({ canEdit: true });
  const router = useRouter();
  const [loaded, setLoaded] = useState(lessonId === null);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [kind, setKind] = useState<LessonKind>("theory");
  const [body, setBody] = useState("");
  const [initialQuestionIds, setInitialQuestionIds] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (lessonId === null || !token) return;
    apiFetch<GrammarLessonAdmin>(API_ROUTES.adminGrammarLesson(lessonId), { token })
      .then((lesson) => {
        setTitle(lesson.title);
        setSlug(lesson.slug);
        setKind(lesson.kind as LessonKind);
        setBody(lesson.body);
        setInitialQuestionIds(lesson.question_ids);
        setSelected(new Set(lesson.question_ids));
        setLoaded(true);
      })
      .catch(() => setFailure("Không tải được bài học này."));
  }, [lessonId, token]);

  if (status !== "authenticated") {
    return (
      <Page className="max-w-5xl">
        <SkeletonList rows={6} />
      </Page>
    );
  }

  async function save() {
    if (!token) return;
    setSaving(true);
    setFailure(null);
    try {
      let id = lessonId;
      if (id === null) {
        const created = await apiFetch<{ id: string }>(API_ROUTES.adminGrammarLessons, {
          method: "POST",
          token,
          body: JSON.stringify({ topic_id: topicId, slug, title, kind, body }),
        });
        id = created.id;
      } else {
        await apiFetch(API_ROUTES.adminGrammarLesson(id), {
          method: "PATCH",
          token,
          body: JSON.stringify({ title, slug, kind, body }),
        });
      }
      if (kind === "practice") {
        await apiFetch(API_ROUTES.adminGrammarLessonQuestions(id), {
          method: "PUT",
          token,
          body: JSON.stringify({ question_ids: [...selected] }),
        });
      }
      router.push("/admin/grammar");
    } catch (err) {
      setSaving(false);
      setFailure(err instanceof ApiError ? err.message : "Không lưu được.");
    }
  }

  if (!loaded) {
    return (
      <Page className="max-w-5xl">
        <SkeletonList rows={6} />
      </Page>
    );
  }

  return (
    <Page className="max-w-6xl">
      <Link
        href="/admin/grammar"
        className="mb-3 inline-flex items-center gap-1.5 text-small text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={13} strokeWidth={2} aria-hidden />
        Quay lại cây ngữ pháp
      </Link>

      <PageHeader
        eyebrow={lessonId === null ? "Bài học mới" : "Sửa bài học"}
        title={title || "(chưa đặt tên)"}
      />

      {failure && (
        <div className="mb-4">
          <Alert>{failure}</Alert>
        </div>
      )}

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <Field label="Tên bài">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Slug">
          <Input value={slug} onChange={(e) => setSlug(e.target.value)} className="font-data" />
        </Field>
        <Field label="Loại bài">
          <Select value={kind} onChange={(e) => setKind(e.target.value as LessonKind)}>
            <option value="theory">Lý thuyết</option>
            <option value="practice">Luyện tập</option>
          </Select>
        </Field>
      </div>

      {kind === "theory" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="Markdown">
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="h-[calc(100dvh-22rem)] min-h-[24rem] font-data text-small"
              spellCheck={false}
            />
          </Field>
          <Field label="Xem trước">
            <div className="h-[calc(100dvh-22rem)] min-h-[24rem] overflow-y-auto rounded border border-rule-strong bg-panel p-4">
              <MarkdownLite text={body} className="text-lesson" />
            </div>
          </Field>
        </div>
      ) : (
        <PracticePicker
          token={token}
          selected={selected}
          initialSelected={initialQuestionIds}
          onChange={setSelected}
        />
      )}

      <div className="sticky bottom-0 -mx-4 mt-6 flex items-center justify-end gap-2 border-t border-rule bg-ground/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <Button variant="quiet" onClick={() => router.push("/admin/grammar")}>
          Huỷ
        </Button>
        <Button
          disabled={saving || !title.trim() || !slug.trim() || (lessonId === null && !topicId)}
          onClick={() => void save()}
        >
          {saving ? "Đang lưu…" : "Lưu"}
        </Button>
      </div>
    </Page>
  );
}

/**
 * Chọn câu cho bài practice: từ KHO (tìm theo chữ, lọc theo nhãn grammar) hoặc
 * THÊM TAY tại chỗ — không suy ra từ nhãn chủ đề. Câu đã chọn nhưng ngoài kết
 * quả lọc vẫn hiện để bỏ chọn được: không thì chúng là những câu "ma" bị PUT đi
 * mà mắt không kiểm được.
 */
function PracticePicker({
  token,
  selected,
  initialSelected,
  onChange,
}: {
  token: string | null;
  selected: Set<string>;
  initialSelected: string[];
  onChange: (next: Set<string>) => void;
}) {
  const [bank, setBank] = useState<TopicQuestion[] | null>(null);
  const [labels, setLabels] = useState<GrammarLabel[]>([]);
  const [codeFilter, setCodeFilter] = useState("");
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  function loadBank(query: string, code: string) {
    if (!token) return;
    const params = new URLSearchParams({ limit: "100" });
    if (query) params.set("search", query);
    if (code) params.set("code", code);
    apiFetch<TopicQuestion[]>(`${API_ROUTES.adminGrammarQuestionBank}?${params}`, { token })
      .then(setBank)
      .catch(() => setBank([]));
  }

  useEffect(() => {
    loadBank("", "");
    apiFetch<GrammarLabel[]>(API_ROUTES.adminGrammarLabels, { token: token ?? undefined })
      .then(setLabels)
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const toggle = (id: string, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    onChange(next);
  };

  const inBank = new Set(bank?.map((q) => q.id) ?? []);

  return (
    <Panel className="p-4">
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-small font-semibold">
            Câu đã chọn: <span className="font-data">{selected.size}</span>
          </p>
          <Button size="sm" variant="quiet" onClick={() => setAdding((v) => !v)}>
            {adding ? "Đóng form thêm câu" : "Thêm câu mới…"}
          </Button>
        </div>

        {failure && <Alert>{failure}</Alert>}

        {adding && (
          <NewQuestionForm
            token={token}
            onCreated={(question) => {
              toggle(question.id, true);
              setBank((prev) => [question, ...(prev ?? [])]);
              setAdding(false);
            }}
            onError={setFailure}
          />
        )}

        {initialSelected
          .filter((id) => !inBank.has(id) && selected.has(id))
          .map((id) => (
            <p key={id} className="font-data text-small text-ink-faint">
              ✓ {id} <span className="text-ink-muted">(không nằm trong lọc)</span>
            </p>
          ))}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            loadBank(search, codeFilter);
          }}
          className="flex flex-wrap items-center gap-2"
        >
          <Select
            value={codeFilter}
            onChange={(e) => {
              setCodeFilter(e.target.value);
              loadBank(search, e.target.value);
            }}
            className="max-w-[16rem]"
            aria-label="Lọc theo nhãn ngữ pháp"
          >
            <option value="">Mọi nhãn grammar</option>
            {labels.map((label) => (
              <option key={label.code} value={label.code}>
                {label.label_vi} ({label.code})
              </option>
            ))}
          </Select>
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm trong kho theo chữ trong câu…"
            className="max-w-md flex-1"
          />
          <Button size="sm" type="submit">
            Tìm
          </Button>
        </form>

        {!bank && <SkeletonList rows={3} />}
        {bank && bank.length === 0 && (
          <p className="text-small text-ink-muted">Kho không có câu nào khớp.</p>
        )}
        <div className="max-h-[28rem] space-y-1 overflow-y-auto rounded border border-rule-strong bg-panel p-2">
          {bank?.map((question) => (
            <label
              key={question.id}
              className="flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 text-small hover:bg-recess"
            >
              <input
                type="checkbox"
                checked={selected.has(question.id)}
                onChange={(e) => toggle(question.id, e.target.checked)}
                className="mt-0.5"
              />
              <span className="font-data text-ink-faint">P{question.part}</span>
              {question.grammar_code && (
                <span className="shrink-0 rounded border border-rule px-1 py-0.5 text-label uppercase text-ink-faint">
                  {question.grammar_code.replace("GRAMMAR_", "")}
                </span>
              )}
              <span className="min-w-0 flex-1 font-data">{question.prompt_text}</span>
            </label>
          ))}
        </div>
      </div>
    </Panel>
  );
}

/**
 * Thêm câu trắc nghiệm ngay trong màn soạn: prompt + 4 phương án + radio đáp
 * án đúng. Máy chủ chấm bằng đúng `validate_question` của khu luyện thi — form
 * này chỉ việc gửi, hỏng thì 422 hiện lên `failure`.
 */
function NewQuestionForm({
  token,
  onCreated,
  onError,
}: {
  token: string | null;
  onCreated: (question: TopicQuestion) => void;
  onError: (message: string) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [options, setOptions] = useState(["", "", "", ""]);
  const [correct, setCorrect] = useState("A");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!token || busy) return;
    setBusy(true);
    onError("");
    try {
      const created = await apiFetch<{ id: string; part: number; prompt_text: string }>(
        API_ROUTES.adminGrammarQuestions,
        {
          method: "POST",
          token,
          body: JSON.stringify({
            prompt_text: prompt,
            options: options.map((content, index) => ({
              label: "ABCD"[index],
              content,
              is_correct: "ABCD"[index] === correct,
            })),
          }),
        },
      );
      onCreated({ id: created.id, part: created.part, prompt_text: created.prompt_text });
    } catch (err) {
      setBusy(false);
      onError(err instanceof ApiError ? err.message : "Không tạo được câu.");
    }
  }

  return (
    <div className="space-y-2 rounded border border-rule-strong bg-recess p-3">
      <Input
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Câu hỏi — dùng ------- cho chỗ trống"
      />
      {options.map((content, index) => (
        <div key={index} className="flex items-center gap-2">
          <input
            type="radio"
            name="correct-option"
            checked={correct === "ABCD"[index]}
            onChange={() => setCorrect("ABCD"[index])}
            title={`Đáp án đúng là ${"ABCD"[index]}`}
          />
          <span className="font-data w-4 text-small text-ink-faint">{"ABCD"[index]}</span>
          <Input
            value={content}
            onChange={(e) =>
              setOptions((prev) => prev.map((v, i) => (i === index ? e.target.value : v)))
            }
            placeholder={`Phương án ${"ABCD"[index]}`}
          />
        </div>
      ))}
      <div className="flex justify-end">
        <Button
          size="sm"
          disabled={busy || !prompt.trim() || options.some((o) => !o.trim())}
          onClick={() => void submit()}
        >
          {busy ? "Đang tạo…" : "Tạo và chọn câu này"}
        </Button>
      </div>
    </div>
  );
}
