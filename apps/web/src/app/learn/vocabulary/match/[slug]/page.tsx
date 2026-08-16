"use client";

import {
  API_ROUTES,
  type TopicPublic,
  type VocabularyPage as VocabularyListPage,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import { RotateCcw, Trophy } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  Page,
  PageHeader,
  Skeleton,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { recordReview, shuffle } from "@/lib/game";
import { useSession } from "@/lib/session";

// Lưới 4x4 = 8 cặp × 2 ô = 16 ô vuông, đúng chuẩn memory-match. Ít hơn thì ván
// xong trước khi vào nhịp, nhiều hơn thì phải cuộn — mất hết cái "lật cả bàn".
const ROUND_PAIRS = 8;
const GRADE_GOOD = 4;

type Tile = { entryId: string; text: string; kind: "word" | "meaning" };

function buildTiles(pool: VocabularySummary[]): Tile[] {
  const cards = shuffle(pool).slice(0, ROUND_PAIRS);
  return shuffle(
    cards.flatMap((word) => [
      { entryId: word.id, text: word.headword, kind: "word" as const },
      { entryId: word.id, text: word.meaning_vi, kind: "meaning" as const },
    ]),
  );
}

function MatchGame({
  pool,
  slug,
  token,
}: {
  pool: VocabularySummary[];
  slug: string;
  token: string | null;
}) {
  const [tiles, setTiles] = useState<Tile[]>(() => buildTiles(pool));
  // Ô đang chọn và các cặp đã xong — đều là CHỈ SỐ ô, vì cùng một từ hiện ở hai
  // ô khác nhau và phải ẩn được cả hai.
  const [picked, setPicked] = useState<number | null>(null);
  const [solvedTiles, setSolvedTiles] = useState<Set<number>>(new Set());
  // Hai ô báo đỏ trong giây lát sau một lần ghép sai. `locked` chặn bấm trong
  // lúc đó, để cái nháy đỏ kịp được nhìn thấy thay vì bị cú bấm kế tiếp nuốt mất.
  const [wrongTiles, setWrongTiles] = useState<Set<number>>(new Set());
  const [locked, setLocked] = useState(false);
  const [moves, setMoves] = useState(0);

  const done = solvedTiles.size === tiles.length;

  const restart = useCallback(() => {
    setTiles(buildTiles(pool));
    setPicked(null);
    setSolvedTiles(new Set());
    setWrongTiles(new Set());
    setLocked(false);
    setMoves(0);
  }, [pool]);

  // Ghép đúng một cặp = một lượt ôn được ghi (grade 4), y như tự chấm "good"
  // trên thẻ lật. Chơi game mà không ghi thì "đã thuộc" trên trang chủ không
  // bao giờ nhích lên từ những lượt chơi.
  function recordCorrect(entryId: string) {
    if (!token) return;
    recordReview(token, entryId, GRADE_GOOD);
  }

  function pick(index: number) {
    if (locked || done || solvedTiles.has(index)) return;
    if (picked === null) {
      setPicked(index);
      return;
    }
    if (picked === index) {
      setPicked(null);
      return;
    }

    const first = tiles[picked]!;
    const second = tiles[index]!;
    setMoves((value) => value + 1);

    if (first.entryId === second.entryId) {
      setSolvedTiles((prev) => new Set(prev).add(picked).add(index));
      setPicked(null);
      recordCorrect(first.entryId);
      return;
    }

    // Sai: cả hai ô báo đỏ rồi mở khoá, KHÔNG giữ lại lựa chọn — flash ngắn đủ
    // nói "sai rồi", và giữ nguyên tay đang chọn chỉ làm người chơi rón rén.
    setWrongTiles(new Set([picked, index]));
    setPicked(null);
    setLocked(true);
    window.setTimeout(() => {
      setWrongTiles(new Set());
      setLocked(false);
    }, 650);
  }

  if (done) {
    return (
      <div className="rounded border border-rule bg-panel px-6 py-10 text-center">
        <Trophy size={24} strokeWidth={1.75} aria-hidden className="mx-auto text-ok" />
        <p className="mt-3 text-subtitle font-semibold">Xong trong {moves} lượt</p>
        <p className="mt-1.5 text-small text-ink-muted">
          {moves === ROUND_PAIRS
            ? "Không một lần nhầm — đỉnh luôn."
            : "Càng ít lượt nhầm càng chắc tay."}
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Button onClick={restart}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden />
            Chơi lại
          </Button>
          <ButtonLink href={`/learn/vocabulary/${slug}`} variant="secondary">
            Về danh sách từ
          </ButtonLink>
        </div>
      </div>
    );
  }

  return (
    <>
      <p className="mb-3 font-data text-small tabular-nums text-ink-muted">
        Ghép {(tiles.length - solvedTiles.size) / 2} cặp còn lại · {moves} lượt đã thử
      </p>

      {/* `invisible` thay vì unmount: ô đã ghép biến mất nhưng BÀN CỜ GIỮ HÌNH —
          memory-match lật cả một lưới 4x4, và một lưới co lại theo từng cặp sẽ
          làm người chơi mất phương hướng. `max-w` ép bàn cờ hẹp hơn bề ngang
          nội dung: ô vuông bé lại một nhịp so với cả trang. */}
      <div className="mx-auto grid max-w-md grid-cols-4 gap-1.5 sm:gap-2">
        {tiles.map((tile, index) => {
          const isSolved = solvedTiles.has(index);
          const isPicked = picked === index;
          const isWrong = wrongTiles.has(index);
          return (
            <button
              key={`${tile.entryId}-${tile.kind}`}
              type="button"
              onClick={() => pick(index)}
              disabled={isSolved || locked}
              aria-label={isSolved ? "đã ghép" : undefined}
              className={cx(
                "grid aspect-square place-items-center rounded border p-1 text-center text-small leading-snug transition-colors",
                isSolved && "invisible",
                // Sai/picked luôn thắng màu chữ: màu của TRẠNG THÁI, không của
                // loại chữ — hai màu chồng nhau thì không đọc được trạng thái.
                isWrong &&
                  cx("border-alert bg-alert-tint text-alert", tile.kind === "word" && "font-bold"),
                !isSolved &&
                  !isWrong &&
                  isPicked &&
                  cx(
                    "border-action bg-action-tint",
                    tile.kind === "word" ? "font-bold text-action-ink" : "text-ink",
                  ),
                !isSolved &&
                  !isWrong &&
                  !isPicked &&
                  cx(
                    "border-rule-strong bg-panel hover:bg-recess",
                    tile.kind === "word" ? "font-bold text-action-ink" : "text-ink",
                  ),
              )}
            >
              <span className="line-clamp-3 overflow-hidden break-words">{tile.text}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}

export default function MatchPage() {
  const rawSlug = String(useParams<{ slug: string }>().slug ?? "");
  const topicSlug = rawSlug === "all" ? null : rawSlug;
  const { token } = useSession();

  const [topics, setTopics] = useState<TopicPublic[] | null>(null);
  const [pool, setPool] = useState<VocabularySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then(setTopics)
      .catch(() => {});
    const parts = [topicSlug ? `topic=${encodeURIComponent(topicSlug)}` : "", "limit=200"];
    apiFetch<VocabularyListPage>(`${API_ROUTES.vocabulary}?${parts.filter(Boolean).join("&")}`)
      .then((page) => setPool(page.items))
      .catch(() => setError("Không tải được từ vựng."));
  }, [topicSlug]);

  const topicName = useMemo(() => {
    if (!topicSlug) return "Tất cả từ vựng";
    return topics?.find((topic) => topic.slug === topicSlug)?.name ?? topicSlug;
  }, [topicSlug, topics]);

  return (
    <Page className="max-w-2xl">
      <Breadcrumbs
        trail={[
          { href: "/learn/vocabulary", label: "Từ vựng" },
          { href: `/learn/vocabulary/${rawSlug}`, label: topicName },
          { href: "", label: "Ghép từ" },
        ]}
      />
      <PageHeader
        eyebrow="Minigame"
        title="Ghép từ với nghĩa"
        description={`${topicName} — lật bàn cờ 4x4: mỗi từ có một ô và nghĩa của nó nằm ở ô khác. Ghép đúng thì cặp biến mất.`}
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {!pool && !error && <Skeleton className="h-56" />}

      {pool && pool.length < ROUND_PAIRS ? (
        <EmptyState
          title="Chưa đủ từ để chơi"
          description={`Cần ít nhất ${ROUND_PAIRS} từ, hiện có ${pool.length}.`}
          action={
            <ButtonLink href={`/learn/vocabulary/${rawSlug}`} variant="secondary">
              Về danh sách từ
            </ButtonLink>
          }
        />
      ) : (
        pool && (
          <MatchGame key={`${rawSlug}-${pool.length}`} pool={pool} slug={rawSlug} token={token} />
        )
      )}
    </Page>
  );
}
