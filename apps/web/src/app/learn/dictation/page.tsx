"use client";

import {
  API_ROUTES,
  type DictationDetail,
  type DictationResult,
  type DictationSummary,
} from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  Page,
  PageHeader,
  SkeletonList,
  Spinner,
  Textarea,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession, useSession } from "@/lib/session";

/** How each word of the comparison is drawn. */
const DIFF_STYLE: Record<string, string> = {
  match: "text-success",
  missing: "text-danger line-through decoration-2",
  extra: "text-warning italic",
};

function Score({ value }: { value: string }) {
  const numeric = Number(value);
  const tone = numeric >= 90 ? "success" : numeric >= 60 ? "warning" : "danger";
  return (
    <div className="flex items-baseline gap-2">
      <span
        className={cx(
          "text-4xl font-bold tabular-nums",
          tone === "success" && "text-success",
          tone === "warning" && "text-warning",
          tone === "danger" && "text-danger",
        )}
      >
        {numeric.toFixed(0)}%
      </span>
    </div>
  );
}

export default function DictationPage() {
  const { status, token } = useRequireSession();
  const { canEdit } = useSession();
  const [items, setItems] = useState<DictationSummary[] | null>(null);
  const [active, setActive] = useState<DictationDetail | null>(null);
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<DictationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DictationSummary[]>(API_ROUTES.dictation)
      .then(setItems)
      .catch(() => setError("Không tải được danh sách bài nghe."));
  }, []);

  function open(id: string) {
    setResult(null);
    setTyped("");
    setError(null);
    apiFetch<DictationDetail>(API_ROUTES.dictationDetail(id))
      .then(setActive)
      .catch(() => setError("Không tải được bài này."));
  }

  async function submit() {
    if (!active || !token) return;
    setBusy(true);
    try {
      setResult(
        await apiFetch<DictationResult>(API_ROUTES.submitDictation(active.id), {
          method: "POST",
          token,
          body: JSON.stringify({ submitted_text: typed }),
        }),
      );
    } catch {
      setError("Không nộp được bài.");
    } finally {
      setBusy(false);
    }
  }

  if (status !== "authenticated") {
    return (
      <Page className="max-w-2xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  // --- one exercise ------------------------------------------------------

  if (active) {
    return (
      <Page className="max-w-2xl">
        <PageHeader
          eyebrow="Dictation"
          title="Nghe và gõ lại"
          description={`${active.word_count} từ · nghe lại bao nhiêu lần cũng được`}
          actions={
            <Button variant="ghost" size="sm" onClick={() => setActive(null)}>
              Đóng
            </Button>
          }
        />

        {error && (
          <div className="mb-4">
            <Alert>{error}</Alert>
          </div>
        )}

        <Card className="p-6">
          {/* Native controls give scrubbing and replay for nothing, and need no
              CORS on the media origin. */}
          <audio controls src={active.audio_url} className="w-full" />

          <Textarea
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            rows={4}
            disabled={result !== null}
            placeholder="Gõ lại những gì bạn nghe được…"
            className="mt-5"
          />

          {!result && (
            <Button className="mt-4" disabled={!typed.trim() || busy} onClick={() => void submit()}>
              {busy && <Spinner />}
              Nộp bài
            </Button>
          )}
        </Card>

        {result && (
          <Card className="animate-rise mt-4 p-6">
            <div className="flex items-end justify-between">
              <Score value={result.accuracy} />
              <p className="text-sm text-text-muted">
                đúng {result.matched}/{result.expected} từ
              </p>
            </div>

            <p className="mt-5 text-lg leading-8">
              {result.diff.map((word, position) => (
                <span key={`${word.op}-${position}`} className={DIFF_STYLE[word.op]}>
                  {word.word}{" "}
                </span>
              ))}
            </p>

            <div className="mt-3 flex flex-wrap gap-3 text-xs text-text-muted">
              <span className="text-success">■ đúng</span>
              <span className="text-danger">■ thiếu / sai</span>
              <span className="text-warning">■ thừa</span>
            </div>

            <div className="mt-5 rounded-lg bg-surface-sunken p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-text-subtle">Đáp án</p>
              <p className="mt-1">{result.transcript}</p>
            </div>

            <div className="mt-5 flex gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setResult(null);
                  setTyped("");
                }}
              >
                Làm lại
              </Button>
              <Button variant="ghost" onClick={() => setActive(null)}>
                Bài khác
              </Button>
            </div>
          </Card>
        )}
      </Page>
    );
  }

  // --- the list ----------------------------------------------------------

  return (
    <Page className="max-w-2xl">
      <PageHeader
        eyebrow="Dictation"
        title="Luyện nghe chép chính tả"
        description="Mỗi bài là một câu. Chấm theo từng từ, bỏ qua hoa thường và dấu câu."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!items && <SkeletonList rows={4} />}

      {items?.length === 0 && (
        <EmptyState
          icon="🎧"
          title="Chưa có bài nghe nào"
          description={
            canEdit
              ? "Câu nghe cần audio khớp với transcript trước khi xuất bản được."
              : "Nội dung đang được biên soạn."
          }
          action={canEdit ? <ButtonLink href="/admin/dictation">Thêm câu</ButtonLink> : undefined}
        />
      )}

      <div className="space-y-2">
        {items?.map((item, position) => (
          <Card key={item.id}>
            <button
              type="button"
              onClick={() => open(item.id)}
              className="flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-surface-sunken"
            >
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-soft text-sm font-semibold text-brand-text tabular-nums">
                {position + 1}
              </span>
              <span className="flex-1 text-sm text-text-muted">{item.word_count} từ</span>
              <Badge
                tone={
                  item.difficulty <= 2 ? "success" : item.difficulty >= 4 ? "danger" : "neutral"
                }
              >
                độ khó {item.difficulty}
              </Badge>
            </button>
          </Card>
        ))}
      </div>
    </Page>
  );
}
