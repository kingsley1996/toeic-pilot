"use client";

import { API_ROUTES, type ReviewCard, type ReviewSession } from "@toeic-pilot/shared";
import { CalendarCheck, CircleCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

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
 * Bốn mức chất lượng SM-2, thay cho sáu mức của bản gốc.
 *
 * 0, 1 và 2 đều có nghĩa "quên" và không ai phân biệt được ba mức đó một cách
 * đáng tin, nên chúng gộp làm một. Ba mức còn lại giữ nguyên ý nghĩa số học,
 * và đó là lý do dãy số nhảy từ 0 lên 3.
 *
 * Thang này là THỨ TỰ (kém → tốt), không phải phân loại — nên màu chạy thành
 * một dải alert → ok chứ không phải bốn sắc rời rạc. Bốn nút tô đặc bốn màu
 * cũng sẽ tranh mất chỗ với màu hành động, vốn chỉ dành cho "việc cần làm".
 */
const GRADES = [
  { grade: 0, label: "Quên", hint: "Lại từ đầu", key: "1", bar: "bg-alert" },
  { grade: 3, label: "Khó", hint: "Chật vật", key: "2", bar: "bg-warn" },
  { grade: 4, label: "Được", hint: "Nhớ ra", key: "3", bar: "bg-ink-muted" },
  { grade: 5, label: "Dễ", hint: "Nhớ ngay", key: "4", bar: "bg-ok" },
];

export default function ReviewPage() {
  const { status, token } = useRequireSession();
  const [cards, setCards] = useState<ReviewCard[] | null>(null);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (t: string) =>
      apiFetch<ReviewSession>(API_ROUTES.reviewSession, { token: t })
        .then((session) => {
          setCards(session.cards);
          setIndex(0);
          setFlipped(false);
        })
        .catch(() => setError("Không tải được phiên ôn tập.")),
    [],
  );

  useEffect(() => {
    if (token) void load(token);
  }, [token, load]);

  const card = cards?.[index];

  const submit = useCallback(
    async (grade: number) => {
      if (!card || !token || saving) return;
      setSaving(true);
      try {
        await apiFetch(API_ROUTES.submitReview(card.id), {
          method: "POST",
          token,
          body: JSON.stringify({ grade }),
        });
        setFlipped(false);
        setIndex((current) => current + 1);
      } catch {
        setError("Không lưu được câu trả lời.");
      } finally {
        setSaving(false);
      }
    },
    [card, token, saving],
  );

  // Space để lật, 1–4 để chấm. Một phiên ôn là hàng chục quyết định giống hệt
  // nhau nối tiếp; phải với tay ra chuột mỗi lần là khác biệt giữa một công cụ
  // và một việc vặt.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!card) return;
      if (event.code === "Space" || event.key === "Enter") {
        event.preventDefault();
        if (!flipped) setFlipped(true);
        return;
      }
      if (!flipped) return;
      const match = GRADES.find((entry) => entry.key === event.key);
      if (match) void submit(match.grade);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, flipped, submit]);

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
        {/* Về LỊCH, không phải về thành tựu — nên icon là lịch. */}
        <EmptyState
          icon={CalendarCheck}
          title="Không còn từ nào đến hạn"
          description="Lịch ôn tập giãn ra theo trí nhớ của bạn, nên hôm nay trống là đúng. Quay lại vào ngày mai."
          action={<ButtonLink href="/learn">Về Learning Hub</ButtonLink>}
        />
      </Page>
    );
  }

  if (index >= cards.length) {
    return (
      <Page className="max-w-2xl">
        {/* Về HOÀN THÀNH — icon khác hẳn trạng thái trên, vì hai chuyện khác nhau. */}
        <EmptyState
          icon={CircleCheck}
          title={`Xong ${cards.length} thẻ`}
          description="Mỗi lần trả lời đã được ghi lại, và lịch ôn kế tiếp đã được tính."
          action={
            <div className="flex gap-2">
              <Button onClick={() => token && void load(token)}>Tải phiên mới</Button>
              <ButtonLink href="/learn" variant="secondary">
                Về Learning Hub
              </ButtonLink>
            </div>
          }
        />
      </Page>
    );
  }

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

      <Panel className="px-6 py-10 text-center sm:px-10">
        <p className="font-display text-readout leading-none">{card?.headword}</p>
        <p className="mt-3 text-label font-semibold uppercase text-ink-faint">
          {card?.part_of_speech}
        </p>
        {card?.phonetic && <p className="mt-2 font-data text-ink-muted">{card.phonetic}</p>}

        <AccentRow clips={card?.headword_audio ?? []} className="mt-5 justify-center" />

        {flipped ? (
          <div className="animate-settle mt-8 border-t border-rule pt-6 text-left">
            <p className="text-title">{card?.meaning_vi}</p>
            <p className="mt-1 text-small text-ink-muted">{card?.meaning_en}</p>

            {card?.example && (
              <div className="mt-5 rounded border border-rule bg-recess p-4">
                <p className="italic">{card.example}</p>
                {card.example_vi && (
                  <p className="mt-1 text-small text-ink-muted">{card.example_vi}</p>
                )}
                <AccentRow clips={card.example_audio} className="mt-3" />
              </div>
            )}
          </div>
        ) : (
          <Button variant="secondary" size="lg" className="mt-8" onClick={() => setFlipped(true)}>
            Lật thẻ
            <Kbd>Space</Kbd>
          </Button>
        )}
      </Panel>

      {flipped && (
        <div className="animate-settle mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {GRADES.map((entry) => (
            <button
              key={entry.grade}
              type="button"
              disabled={saving}
              onClick={() => void submit(entry.grade)}
              className={cx(
                "flex items-center gap-3 rounded border border-rule-strong bg-panel px-3 py-2.5 text-left transition-colors",
                "hover:bg-recess disabled:cursor-not-allowed disabled:opacity-45",
              )}
            >
              {/* Vạch màu mã hoá thứ hạng; chữ mới là thứ mang nghĩa. */}
              <span aria-hidden className={cx("h-8 w-1 shrink-0 rounded-none", entry.bar)} />
              <span className="min-w-0 flex-1">
                <span className="block text-small font-semibold">{entry.label}</span>
                <span className="block text-label uppercase text-ink-faint">{entry.hint}</span>
              </span>
              <Kbd>{entry.key}</Kbd>
            </button>
          ))}
        </div>
      )}
    </Page>
  );
}
