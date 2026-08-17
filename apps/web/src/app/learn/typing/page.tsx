"use client";

import {
  API_ROUTES,
  type RecallResult,
  type ReviewCard,
  type ReviewSession,
} from "@toeic-pilot/shared";
import { CalendarCheck, CircleCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { AccentRow } from "@/components/audio-button";
import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  Kbd,
  Meter,
  Page,
  Panel,
  Skeleton,
  Tag,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Gõ lại từ — cùng hàng đợi SM-2 với thẻ lật, khác ở chỗ ai chấm.
 *
 * Thẻ lật hỏi "bạn có nhớ không" rồi ghi thẳng câu trả lời, nên lật xong nghĩ
 * "à đúng rồi tôi biết mà" là đủ để bấm Dễ và không học được gì. Ở đây phải
 * viết ra được trước đã.
 *
 * Không có bộ chấm nào trong file này: server chấm và trả về `verdict`. Đó là
 * lựa chọn có ý thức, ngược với dictation — dictation chấm ở client để phản hồi
 * tức thì trên một câu dài và phải nuôi hai bộ chấm luôn có nguy cơ lệch nhau.
 * Một từ thì một vòng request là đủ nhanh, nên không tạo ra bản sao thứ hai.
 */

const VERDICTS = {
  correct: { label: "Đúng rồi", tone: "text-ok", ring: "border-ok" },
  typo: { label: "Gần đúng — sai một ký tự", tone: "text-warn", ring: "border-warn" },
  wrong: { label: "Chưa đúng", tone: "text-alert", ring: "border-alert" },
  unknown: { label: "Chưa biết từ này", tone: "text-ink-muted", ring: "border-rule-strong" },
} as const;

type Verdict = keyof typeof VERDICTS;

export default function TypingPage() {
  const { status, token } = useRequireSession();
  const [cards, setCards] = useState<ReviewCard[] | null>(null);
  const [index, setIndex] = useState(0);
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<RecallResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(
    (t: string) =>
      // `include_new=false` là điều kiện để chế độ này trả lời được. Bắt gõ
      // lại một từ chưa từng thấy thì không tồn tại câu trả lời đúng nào —
      // lối thoát duy nhất là đoán bừa rồi ăn điểm 0, và với người mới thì
      // 20/20 thẻ đều rơi vào cảnh đó.
      apiFetch<ReviewSession>(`${API_ROUTES.reviewSession}?include_new=false`, { token: t })
        .then((session) => {
          setCards(session.cards);
          setIndex(0);
          setTyped("");
          setResult(null);
        })
        .catch(() => setError("Không tải được phiên học.")),
    [],
  );

  useEffect(() => {
    if (token) void load(token);
  }, [token, load]);

  const card = cards?.[index];

  // Ô trống thì không gửi. Không có nó, một lần lỡ tay bấm Enter sẽ bị chấm là
  // SAI và ghi thẳng một `lapse` vào SM-2 — tức là bị phạt lịch ôn vì trượt
  // phím, cho một từ chưa kịp trả lời.
  const answerable = typed.trim().length > 0;

  const check = useCallback(
    async ({ easy = false, giveUp = false } = {}) => {
      if (!card || !token || saving || result) return;
      // Bỏ trống chỉ chặn được khi học viên đang cố TRẢ LỜI. "Tôi chưa biết"
      // thì ô trống chính là nội dung đúng của nó.
      if (!giveUp && !answerable) return;
      setSaving(true);
      try {
        setResult(
          await apiFetch<RecallResult>(API_ROUTES.submitRecall(card.id), {
            method: "POST",
            token,
            body: JSON.stringify({ typed, easy, give_up: giveUp }),
          }),
        );
      } catch {
        setError("Không lưu được câu trả lời.");
      } finally {
        setSaving(false);
      }
    },
    [card, token, saving, result, typed, answerable],
  );

  const advance = useCallback(() => {
    setResult(null);
    setTyped("");
    setIndex((current) => current + 1);
  }, []);

  // Enter kiểm tra, Enter lần nữa thì sang từ sau — cùng nhịp với dictation, nên
  // người học không phải đổi thói quen giữa hai phần. Chặn `event.repeat` vì giữ
  // phím sinh ra keydown tự lặp và một lần bấm sẽ nhảy qua cả một từ, đúng lỗi
  // đã sửa ở dictation.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Enter" || event.repeat || !card) return;
      event.preventDefault();
      if (result) advance();
      else void check({ easy: event.shiftKey });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, result, check, advance]);

  // Con trỏ phải nằm sẵn trong ô nhập ở mỗi từ: một phiên là hàng chục lượt gõ
  // giống hệt nhau, và phải với tay ra chuột mỗi lần là khác biệt giữa một công
  // cụ và một việc vặt.
  //
  // Phụ thuộc `card?.id` chứ KHÔNG phải `index`: lần render đầu tiên là skeleton
  // (chưa có `<input>` nào để focus), và khi phiên tải xong thì `index` vẫn là 0
  // — không đổi, nên effect không chạy lại và từ đầu tiên mất con trỏ. Lỗi này
  // chỉ lộ ra khi gõ thử, vì nhìn code thì effect trông như đã chạy đúng lúc.
  useEffect(() => {
    if (!result) inputRef.current?.focus();
  }, [card?.id, result]);

  if (status !== "authenticated" || !cards) {
    return (
      <Page className="max-w-2xl">
        <Skeleton className="h-2 w-full" />
        <Skeleton className="mt-6 h-72 w-full" />
      </Page>
    );
  }

  if (error && cards.length === 0) {
    return (
      <Page className="max-w-2xl">
        <Alert>{error}</Alert>
      </Page>
    );
  }

  if (cards.length === 0) {
    return (
      <Page className="max-w-2xl">
        {/* Rỗng ở đây thường KHÔNG phải "hết việc hôm nay" mà là "chưa gặp từ
            nào để mà viết lại" — nên lối ra phải là thẻ lật, không phải lời
            khuyên quay lại ngày mai. */}
        <EmptyState
          icon={CalendarCheck}
          title="Chưa có từ nào để gõ lại"
          description="Chế độ này chỉ dùng những từ đã đến hạn ôn. Hãy làm quen bằng thẻ lật trước — chúng sẽ xuất hiện ở đây vào lần đến hạn kế tiếp, thường là ngày mai."
          action={
            <div className="flex gap-2">
              <ButtonLink href="/learn/review">Học bằng thẻ lật</ButtonLink>
              <ButtonLink href="/dashboard" variant="secondary">
                Về trang chính
              </ButtonLink>
            </div>
          }
        />
      </Page>
    );
  }

  if (index >= cards.length) {
    return (
      <Page className="max-w-2xl">
        <EmptyState
          icon={CircleCheck}
          title={`Xong ${cards.length} từ`}
          description="Mỗi lần gõ đã được chấm và ghi lại, và lịch ôn kế tiếp đã được tính."
          action={
            <div className="flex gap-2">
              <Button onClick={() => token && void load(token)}>Tải phiên mới</Button>
              <ButtonLink href="/dashboard" variant="secondary">
                Về Learning Hub
              </ButtonLink>
            </div>
          }
        />
      </Page>
    );
  }

  const verdict = result ? VERDICTS[result.verdict as Verdict] : null;

  return (
    <Page className="max-w-2xl">
      <div className="mb-6 flex items-center gap-4">
        <div className="flex-1">
          <Meter value={index} max={cards.length} ticks={Math.min(cards.length, 8)} />
        </div>
        <span className="shrink-0 font-data text-small text-ink-muted">
          {index + 1}/{cards.length}
        </span>
        {card?.is_new && <Tag tone="action">từ mới</Tag>}
      </div>

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <Panel className="px-6 py-8 sm:px-10">
        <p className="text-label font-semibold uppercase text-ink-faint">{card?.part_of_speech}</p>
        <p className="mt-2 font-display text-title">{card?.meaning_vi}</p>
        <p className="mt-1 text-small text-ink-muted">{card?.meaning_en}</p>

        <input
          ref={inputRef}
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          readOnly={result !== null}
          spellCheck={false}
          autoComplete="off"
          autoCapitalize="off"
          aria-label="Viết lại từ tiếng Anh"
          placeholder="viết từ tiếng Anh…"
          className={cx(
            "mt-6 w-full rounded border bg-recess px-4 py-3 font-data text-title outline-none",
            // Viền focus chỉ tồn tại khi còn gõ được. Để nguyên thì `focus:` đè
            // lên màu kết quả và ô vừa chấm xong vẫn mang màu "đang nhập" —
            // trong khi lúc đó nó đã `readOnly`, không còn gì để nhập nữa.
            verdict ? verdict.ring : "border-rule-strong focus:border-action",
          )}
        />

        {result ? (
          <div className="animate-settle mt-5">
            <p className={cx("font-semibold", verdict?.tone)}>{verdict?.label}</p>
            {/* Đáp án chỉ hiện khi chưa gõ đúng hẳn. In ra sau một câu trả lời
                đúng là thừa, và làm màn hình nhiễu đúng lúc đáng lẽ chỉ cần
                một tín hiệu "xong, đi tiếp". */}
            {result.verdict !== "correct" && (
              <p className="mt-1 font-data text-title">{result.expected}</p>
            )}
            <div className="mt-4 border-t border-rule pt-4">
              <p className="italic">{card?.example}</p>
              {card?.example_vi && (
                <p className="mt-1 text-small text-ink-muted">{card.example_vi}</p>
              )}
              <AccentRow clips={card?.headword_audio ?? []} className="mt-3" />
            </div>
            <Button className="mt-5" onClick={advance}>
              Từ tiếp theo
              <Kbd>Enter</Kbd>
            </Button>
          </div>
        ) : (
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Button disabled={saving || !answerable} onClick={() => void check()}>
              Kiểm tra
              <Kbd>Enter</Kbd>
            </Button>
            {/* Lời khai "nhớ ngay" chỉ được xét SAU khi server xác nhận là gõ
                đúng, nên bấm nhầm nút này lúc viết sai không nâng được điểm. */}
            <Button
              variant="secondary"
              disabled={saving || !answerable}
              onClick={() => void check({ easy: true })}
            >
              Nhớ ngay
              <Kbd>⇧ Enter</Kbd>
            </Button>
            <div className="flex-1" />
            {/* Lối ra trung thực. Không có nó thì cách duy nhất để đi tiếp là
                bịa một câu trả lời — tức là app đang dạy người ta đoán bừa, và
                lịch sử ôn tập đầy những lần "đã thử" mà thật ra chưa từng thử. */}
            <Button variant="quiet" disabled={saving} onClick={() => void check({ giveUp: true })}>
              Tôi chưa biết
            </Button>
          </div>
        )}
      </Panel>
    </Page>
  );
}
