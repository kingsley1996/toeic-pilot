"use client";

import {
  API_ROUTES,
  type AttemptState,
  type PartBreakdown,
  type TestDetail,
} from "@toeic-pilot/shared";
import { ArrowLeft, BookOpen, Clock, FileText, Headphones, Lock, Users } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { LoginModal } from "@/components/login-modal";
import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  Page,
  Panel,
  SectionHeader,
  Skeleton,
  Tag,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

type ReviewMode = "exam" | "practice";

const MODES: Array<{ value: ReviewMode; title: string; description: string }> = [
  {
    value: "exam",
    title: "Luyện thi",
    description: "Giống thi thật — không xem đáp án khi đang làm.",
  },
  {
    value: "practice",
    title: "Luyện tập",
    description: "Xem đáp án ngay từng câu, làm lại thoải mái.",
  },
];

export default function TestDetailPage() {
  const params = useParams<{ slug: string; testSlug: string }>();
  const router = useRouter();
  const { status, token } = useSession();
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [test, setTest] = useState<TestDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [mode, setMode] = useState<ReviewMode>("exam");
  const [chosen, setChosen] = useState<Set<number>>(new Set());
  // Suy ra "hộp thoại đang mở" từ phiên + một lần đóng tay, chứ không mở nó
  // bằng `setState` trong effect — luật `react-hooks/set-state-in-effect`.
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Khách vãng lai không được xem trang này, nên cũng không đi lấy dữ liệu
    // cho nó. Endpoint vốn công khai; đây là chuyện đỡ một vòng mạng và không
    // để trạng thái "không có đề này" hiện ra sau lưng hộp thoại.
    if (status !== "authenticated") return;
    if (!params.testSlug) return;
    let cancelled = false;
    apiFetch<TestDetail>(API_ROUTES.practiceTest(params.testSlug))
      .then((data) => {
        if (!cancelled) setTest(data);
      })
      .catch(() => {
        if (!cancelled) setMissing(true);
      });
    return () => {
      cancelled = true;
    };
  }, [params.testSlug, status]);

  const available = useMemo(() => (test?.parts ?? []).filter((part) => part.has_content), [test]);

  /*
   * Không chọn part nào = làm CẢ ĐỀ, chứ không phải làm rỗng.
   *
   * Khớp với schema: `scope='full'` thì bảng `attempt_part` để trống. Bắt người
   * dùng tick đủ bảy ô để nói "làm cả đề" là biến trường hợp phổ biến nhất
   * thành trường hợp tốn công nhất.
   */
  const isFullTest = chosen.size === 0 || chosen.size === available.length;
  const selectedCount = isFullTest
    ? available.reduce((sum, part) => sum + part.question_count, 0)
    : available
        .filter((part) => chosen.has(part.part))
        .reduce((sum, part) => sum + part.question_count, 0);

  async function start() {
    if (!token || starting) return;
    setStarting(true);
    setStartError(null);
    try {
      const attempt = await apiFetch<AttemptState>(API_ROUTES.attempts, {
        method: "POST",
        token,
        body: JSON.stringify({
          test_slug: params.testSlug,
          review_mode: mode,
          // Rỗng = làm CẢ ĐỀ, khớp với `scope='full'` ở schema. Gửi đủ bảy
          // part để nói "làm tất" sẽ tạo ra bảy hàng `attempt_part` mô tả đúng
          // thứ mà việc không có hàng nào đã mô tả rồi.
          parts: isFullTest ? [] : [...chosen],
        }),
      });
      router.push(`/learn/attempts/${attempt.id}`);
    } catch {
      setStartError("Không mở được đề. Kiểm tra kết nối rồi thử lại.");
      setStarting(false);
    }
  }

  function toggle(part: number) {
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(part)) next.delete(part);
      else next.add(part);
      return next;
    });
  }

  if (status === "loading") {
    return (
      <Page>
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-6 h-96 w-full" />
      </Page>
    );
  }

  /*
   * Ranh giới của khu luyện thi nằm ở ĐÂY, không ở danh sách.
   *
   * Bộ đề và danh sách đề mở cho mọi người — phải xem được có những đề gì rồi
   * mới quyết định lập tài khoản. Từ trang này trở đi thì mọi thứ đều gắn với
   * một bài làm được lưu, nên chặn ở đây là chặn đúng chỗ đầu tiên mà tài khoản
   * thật sự có nghĩa.
   *
   * Chặn ở cả hai đầu: danh sách bắt lần bấm, còn trang này bắt người gõ thẳng
   * URL hay mở lại dấu trang. Chỉ chặn ở nút bấm thì cái chốt chỉ là trang trí.
   */
  if (status === "anonymous") {
    const here = `/learn/tests/${params.slug}/${params.testSlug}`;
    return (
      <Page>
        <Link
          href={`/learn/tests/${params.slug}`}
          className="inline-flex items-center gap-1.5 text-small font-semibold text-ink-muted hover:text-ink"
        >
          <ArrowLeft size={14} strokeWidth={2} aria-hidden />
          Bộ đề thi
        </Link>

        <div className="mt-4">
          <EmptyState
            icon={Lock}
            title="Đăng nhập để xem đề"
            description={
              <>
                Đề thi thử <strong className="font-semibold text-ink">miễn phí</strong>. Cần tài
                khoản để lưu bài làm và điểm số.
              </>
            }
            action={<Button onClick={() => setDismissed(false)}>Đăng nhập</Button>}
          />
        </div>

        <LoginModal
          open={!dismissed}
          onClose={() => setDismissed(true)}
          onSuccess={() => setDismissed(true)}
          next={here}
        />
      </Page>
    );
  }

  if (missing) {
    return (
      <Page>
        <EmptyState
          icon={FileText}
          title="Không có đề này"
          description="Có thể nó đã được gỡ, hoặc đường dẫn bị gõ sai."
          action={<ButtonLink href="/learn/tests">Về danh sách bộ đề</ButtonLink>}
        />
      </Page>
    );
  }

  if (test === null) {
    return (
      <Page>
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-6 h-96 w-full" />
      </Page>
    );
  }

  const blocked = test.parts.filter((part) => !part.has_content);

  return (
    <Page>
      <Link
        href={`/learn/tests/${params.slug}`}
        className="inline-flex items-center gap-1.5 text-small font-semibold text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={14} strokeWidth={2} aria-hidden />
        Bộ đề thi
      </Link>

      <h1 className="mt-3">{test.title}</h1>
      {test.description && <p className="mt-1.5 text-ink-muted">{test.description}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-small text-ink-muted">
        <span className="inline-flex items-center gap-1.5">
          <FileText size={14} strokeWidth={1.75} aria-hidden />
          <span className="font-data tabular-nums text-ink">{test.question_count}</span> câu hỏi
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Users size={14} strokeWidth={1.75} aria-hidden />
          <span className="font-data tabular-nums text-ink">{test.attempt_count}</span> lượt làm
        </span>
        {test.time_limit_seconds !== null && (
          <span className="inline-flex items-center gap-1.5">
            <Clock size={14} strokeWidth={1.75} aria-hidden />
            <span className="font-data tabular-nums text-ink">
              {Math.round(test.time_limit_seconds / 60)}
            </span>{" "}
            phút
          </span>
        )}
      </div>

      {blocked.length > 0 && (
        <div className="mt-5">
          {/*
           * Nói thẳng phần nào đang thiếu thay vì lặng lẽ bỏ qua. Giấu đi thì
           * người học tưởng đề chỉ có ngần ấy phần và đó là thiết kế; nói ra thì
           * họ biết chính xác cái gì chưa có.
           */}
          <Alert tone="info">
            Đề này chưa có{" "}
            <span className="font-semibold">
              {blocked.map((part) => `Part ${part.part}`).join(" và ")}
            </span>
            . Câu hỏi cho những phần đó đang được biên soạn.
          </Alert>
        </div>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
        {/* --- cấu trúc đề ------------------------------------------------ */}
        <section>
          <SectionHeader title="Cấu trúc đề" />
          <Panel className="overflow-hidden">
            <table className="w-full text-small">
              <thead>
                <tr className="border-b border-rule bg-recess text-label uppercase text-ink-muted">
                  <th className="px-4 py-2.5 text-left font-semibold">Section</th>
                  <th className="px-4 py-2.5 text-left font-semibold">Part</th>
                  <th className="px-4 py-2.5 text-left font-semibold">Dạng</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Số câu</th>
                </tr>
              </thead>
              <tbody>
                {test.parts.map((part) => (
                  <PartRow key={part.part} part={part} />
                ))}
              </tbody>
            </table>
          </Panel>
        </section>

        {/* --- chọn cách làm ---------------------------------------------- */}
        <section>
          <SectionHeader title="Chế độ làm bài" />
          <div className="grid gap-3 sm:grid-cols-2">
            {MODES.map((option) => {
              const active = mode === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setMode(option.value)}
                  aria-pressed={active}
                  className={cx(
                    "rounded border p-4 text-left transition-colors",
                    active
                      ? "border-rule-strong bg-recess"
                      : "border-rule bg-panel hover:border-rule-strong",
                  )}
                >
                  <p className={cx("font-semibold", active && "text-action-ink")}>{option.title}</p>
                  <p className="mt-1 text-small text-ink-muted">{option.description}</p>
                </button>
              );
            })}
          </div>

          <div className="mt-6">
            <SectionHeader
              title="Chọn phần muốn làm"
              aside={
                <div className="flex items-center gap-3">
                  {/* "Chọn tất cả" và "Bỏ chọn" cho ra CÙNG một lượt làm bài —
                      không chọn part nào đã nghĩa là làm cả đề. Vẫn giữ cả hai
                      vì chúng trả lời hai câu khác nhau: một cái để tích hết
                      cho thấy rõ mình sắp làm những gì, một cái để xoá lựa chọn
                      dở dang. Ô tích rỗng mà lại làm cả đề là thứ gây ngờ vực
                      nếu không có cách nào tự nhìn thấy. */}
                  <button
                    type="button"
                    onClick={() => setChosen(new Set(available.map((part) => part.part)))}
                    disabled={available.length === 0}
                    className="text-small font-semibold text-ink-muted hover:text-ink disabled:opacity-50"
                  >
                    Chọn tất cả
                  </button>
                  <button
                    type="button"
                    onClick={() => setChosen(new Set())}
                    className="text-small font-semibold text-ink-muted hover:text-ink"
                  >
                    Bỏ chọn
                  </button>
                </div>
              }
            />
            <Panel className="p-4">
              {available.length === 0 ? (
                <p className="text-small text-ink-muted">Đề này chưa có phần nào có nội dung.</p>
              ) : (
                <div className="space-y-1.5">
                  {available.map((part) => (
                    <label
                      key={part.part}
                      className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 hover:bg-recess"
                    >
                      <input
                        type="checkbox"
                        checked={chosen.has(part.part)}
                        onChange={() => toggle(part.part)}
                        className="h-4 w-4 rounded border-rule-strong accent-action"
                      />
                      <span className="text-small font-semibold">
                        P{part.part} — {part.title}
                      </span>
                      <span className="font-data text-small text-ink-faint">
                        ({part.question_count})
                      </span>
                    </label>
                  ))}
                </div>
              )}

              <div className="mt-3 rounded border border-rule bg-recess px-3 py-2 text-small">
                {isFullTest ? (
                  <>
                    Toàn bộ <span className="font-data tabular-nums">{available.length}</span> phần
                    có nội dung — <span className="font-data tabular-nums">{selectedCount}</span>{" "}
                    câu
                  </>
                ) : (
                  <>
                    Đã chọn <span className="font-data tabular-nums">{chosen.size}</span> phần —{" "}
                    <span className="font-data tabular-nums">{selectedCount}</span> câu
                  </>
                )}
              </div>
            </Panel>
          </div>

          <p className="mt-4 text-small text-ink-muted">
            Bài thi tự động nộp khi hết giờ. Bạn có thể tạm dừng và làm tiếp sau.
          </p>

          {startError && (
            <div className="mt-4">
              <Alert tone="alert">{startError}</Alert>
            </div>
          )}

          <div className="mt-4">
            {/* Không còn nhánh "chưa đăng nhập" ở đây: cả trang đã chặn phía
                trên, nên tới được chỗ này là chắc chắn có tài khoản. */}
            <Button
              size="lg"
              className="w-full"
              disabled={available.length === 0 || starting}
              onClick={() => void start()}
            >
              {starting ? "Đang mở đề…" : "Bắt đầu làm bài"}
            </Button>
          </div>
        </section>
      </div>
    </Page>
  );
}

function PartRow({ part }: { part: PartBreakdown }) {
  const listening = part.section === "listening";
  return (
    <tr className={cx("border-b border-rule last:border-0", !part.has_content && "opacity-55")}>
      <td className="px-4 py-2.5">
        <Tag>
          {listening ? (
            <Headphones size={11} strokeWidth={2} aria-hidden />
          ) : (
            <BookOpen size={11} strokeWidth={2} aria-hidden />
          )}
          {listening ? "Nghe" : "Đọc"}
        </Tag>
      </td>
      <td className="px-4 py-2.5 font-semibold">Part {part.part}</td>
      <td className="px-4 py-2.5 text-ink-muted">{part.title}</td>
      <td className="px-4 py-2.5 text-right font-data tabular-nums">
        {part.has_content ? part.question_count : "—"}
      </td>
    </tr>
  );
}
