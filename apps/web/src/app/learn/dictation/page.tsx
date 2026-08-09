"use client";

import {
  API_ROUTES,
  type DictationDetail,
  type DictationResult,
  type DictationSummary,
} from "@toeic-pilot/shared";
import { Headphones, X } from "lucide-react";
import { useEffect, useState } from "react";

import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  IconButton,
  Page,
  PageHeader,
  Panel,
  SkeletonList,
  Spinner,
  Tag,
  Textarea,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession, useSession } from "@/lib/session";

/** Mỗi từ của phần đối chiếu được vẽ thế nào. */
const DIFF_STYLE: Record<string, string> = {
  match: "text-ink",
  missing: "text-alert line-through decoration-2",
  extra: "text-warn italic",
};

/*
 * Câu dài hơn ngần này thì bỏ hiệu ứng lệch nhịp và hiện cùng lúc: quá số này,
 * chờ xem kết quả trở thành chờ đợi chứ không còn là nhịp đọc.
 */
const STAGGER_LIMIT_WORDS = 25;
const STAGGER_STEP_MS = 24;
const STAGGER_CAP_MS = 600;

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

  // --- một bài -----------------------------------------------------------

  if (active) {
    const stagger = result !== null && result.diff.length <= STAGGER_LIMIT_WORDS;

    return (
      <Page className="max-w-2xl">
        <PageHeader
          eyebrow="Dictation"
          title="Nghe và gõ lại"
          description={`${active.word_count} từ · nghe lại bao nhiêu lần cũng được`}
          actions={<IconButton icon={X} aria-label="Đóng bài" onClick={() => setActive(null)} />}
        />

        {error && (
          <div className="mb-4">
            <Alert>{error}</Alert>
          </div>
        )}

        <Panel className="p-5">
          {/* Controls gốc của trình duyệt cho sẵn tua và phát lại, và không đòi
              CORS trên nguồn media. */}
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
        </Panel>

        {result && (
          <Panel className="mt-3 overflow-hidden">
            <div className="flex items-center justify-between border-b border-rule bg-recess px-4 py-2">
              <span className="text-label font-semibold uppercase text-ink-muted">
                Kết quả chấm
              </span>
              <span className="font-data text-label uppercase text-ink-faint">theo từng từ</span>
            </div>

            <div className="px-5 py-5">
              {/*
               * Từng từ hiện ra, trái sang phải — vì đó chính là cách người ta
               * nghe lại câu. Khoảnh khắc dàn dựng DUY NHẤT của cả app; mọi
               * chuyển động khác chỉ là đổi màu 120ms.
               */}
              <p className="text-subtitle leading-9">
                {result.diff.map((word, position) => (
                  <span
                    key={`${word.op}-${position}`}
                    className={cx(stagger && "animate-settle", DIFF_STYLE[word.op])}
                    style={
                      stagger
                        ? {
                            animationDelay: `${Math.min(position * STAGGER_STEP_MS, STAGGER_CAP_MS)}ms`,
                          }
                        : undefined
                    }
                  >
                    {word.word}{" "}
                  </span>
                ))}
              </p>

              <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-small text-ink-muted">
                <span className="flex items-center gap-1.5">
                  <span aria-hidden className="h-2 w-2 bg-ink" /> đúng
                </span>
                <span className="flex items-center gap-1.5">
                  <span aria-hidden className="h-2 w-2 bg-alert" /> nghe sót
                </span>
                <span className="flex items-center gap-1.5">
                  <span aria-hidden className="h-2 w-2 bg-warn" /> gõ thừa
                </span>
              </div>

              {/* Con số để trần, không tô màu theo ngưỡng. Nó là một SỐ ĐO, và
                  phần đánh giá đã nằm ở bảng đối chiếu ngay trên. */}
              <div className="mt-5 flex items-end justify-between border-t border-rule pt-4">
                <div>
                  <p className="text-label font-semibold uppercase text-ink-faint">Độ chính xác</p>
                  <p className="font-data text-readout leading-none text-ink">
                    {Number(result.accuracy).toFixed(0)}
                    <span className="text-title text-ink-faint">%</span>
                  </p>
                </div>
                <p className="font-data text-small text-ink-muted">
                  {result.matched}/{result.expected} từ
                </p>
              </div>

              <div className="mt-5 rounded border border-rule bg-recess p-4">
                <p className="text-label font-semibold uppercase text-ink-faint">Đáp án</p>
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
                <Button variant="quiet" onClick={() => setActive(null)}>
                  Bài khác
                </Button>
              </div>
            </div>
          </Panel>
        )}
      </Page>
    );
  }

  // --- danh sách ---------------------------------------------------------

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
          icon={Headphones}
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
          <Panel key={item.id} className="overflow-hidden">
            <button
              type="button"
              onClick={() => open(item.id)}
              className="flex w-full items-center gap-4 px-4 py-3.5 text-left transition-colors hover:bg-recess"
            >
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded border border-rule bg-recess font-data text-small text-ink-muted">
                {position + 1}
              </span>
              <span className="flex-1 text-small text-ink-muted">{item.word_count} từ</span>
              <Tag tone={item.difficulty <= 2 ? "ok" : item.difficulty >= 4 ? "alert" : "neutral"}>
                độ khó {item.difficulty}
              </Tag>
            </button>
          </Panel>
        ))}
      </div>
    </Page>
  );
}
