"use client";

import { API_ROUTES, type ReviewCard, type ReviewSession } from "@toeic-pilot/shared";
import { useCallback, useEffect, useState } from "react";

import { AccentRow } from "@/components/audio-button";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  Page,
  Skeleton,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * SM-2 quality grades, four buttons rather than the original six.
 *
 * 0, 1 and 2 all mean "forgot" and nobody can report the difference between them
 * reliably, so they collapse into one. The survivors keep their original
 * arithmetic meaning, which is why the numbers jump from 0 to 3.
 */
const GRADES = [
  { grade: 0, label: "Quên", hint: "Lại từ đầu", key: "1", className: "bg-danger text-white" },
  { grade: 3, label: "Khó", hint: "Chật vật", key: "2", className: "bg-warning text-white" },
  { grade: 4, label: "Được", hint: "Nhớ ra", key: "3", className: "bg-brand text-white" },
  { grade: 5, label: "Dễ", hint: "Nhớ ngay", key: "4", className: "bg-success text-white" },
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

  // Space to flip, 1–4 to grade. A review session is dozens of identical
  // decisions in a row; reaching for the mouse each time is the difference
  // between a tool and a chore.
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
        <EmptyState
          icon="✅"
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
        <EmptyState
          icon="🎉"
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

  const progress = (index / cards.length) * 100;

  return (
    <Page className="max-w-2xl">
      <div className="mb-6">
        <div className="mb-2 flex items-center justify-between text-sm text-text-muted">
          <span className="tabular-nums">
            {index + 1} / {cards.length}
          </span>
          {card?.is_new && <Badge tone="brand">từ mới</Badge>}
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-surface-sunken">
          <div
            className="h-full rounded-full bg-brand transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <Card className="px-6 py-10 text-center sm:px-10">
        <p className="text-4xl font-bold tracking-tight">{card?.headword}</p>
        <p className="mt-1 text-sm text-text-subtle">{card?.part_of_speech}</p>
        {card?.phonetic && <p className="mt-2 font-mono text-text-muted">{card.phonetic}</p>}

        <AccentRow clips={card?.headword_audio ?? []} className="mt-5 justify-center" />

        {flipped ? (
          <div className="animate-rise mt-8 border-t border-border pt-6 text-left">
            <p className="text-xl font-medium">{card?.meaning_vi}</p>
            <p className="mt-1 text-sm text-text-muted">{card?.meaning_en}</p>

            {card?.example && (
              <div className="mt-5 rounded-lg bg-surface-sunken p-4">
                <p className="italic">{card.example}</p>
                {card.example_vi && (
                  <p className="mt-1 text-sm text-text-muted">{card.example_vi}</p>
                )}
                <AccentRow clips={card.example_audio} className="mt-3" />
              </div>
            )}
          </div>
        ) : (
          <Button variant="secondary" size="lg" className="mt-8" onClick={() => setFlipped(true)}>
            Lật thẻ
            <kbd className="ml-1 rounded border border-border-strong px-1.5 text-[10px]">Space</kbd>
          </Button>
        )}
      </Card>

      {flipped && (
        <div className="animate-rise mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {GRADES.map((entry) => (
            <button
              key={entry.grade}
              type="button"
              disabled={saving}
              onClick={() => void submit(entry.grade)}
              className={cx(
                "rounded-lg px-2 py-3 transition-opacity hover:opacity-90 disabled:opacity-40",
                entry.className,
              )}
            >
              <span className="block text-sm font-semibold">{entry.label}</span>
              <span className="block text-xs opacity-80">{entry.hint}</span>
              <kbd className="mt-1 inline-block rounded bg-black/20 px-1.5 text-[10px]">
                {entry.key}
              </kbd>
            </button>
          ))}
        </div>
      )}
    </Page>
  );
}
