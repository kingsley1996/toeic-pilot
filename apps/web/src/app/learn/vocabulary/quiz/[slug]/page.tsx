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
  Panel,
  Skeleton,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { recordReview, shuffle } from "@/lib/game";
import { useSession } from "@/lib/session";

// Số câu một ván. Đủ ngắn để chơi liền vài ván, đủ dài để gặp lại một từ.
const ROUND_SIZE = 10;
// Cùng thang SM-2 thẻ lật dùng: đúng = good, sai = forgot. Chơi game mà không
// ghi lượt ôn thì "đã thuộc" trên trang chủ không bao giờ nhích lên.
const GRADE_GOOD = 4;
const GRADE_FORGOT = 0;

interface Question {
  word: VocabularySummary;
  options: string[];
}

function buildRound(pool: VocabularySummary[]): Question[] {
  const cards = shuffle(pool).slice(0, ROUND_SIZE);
  return cards.map((word) => {
    // Nhiễu lấy từ chính hồ từ: cùng chủ đề nên hợp lý, và càng gần đúng càng
    // khó — đúng tinh thần trắc nghiệm TOEIC.
    const distractors = shuffle(pool.filter((entry) => entry.id !== word.id))
      .slice(0, 3)
      .map((entry) => entry.meaning_vi);
    return { word, options: shuffle([word.meaning_vi, ...distractors]) };
  });
}

function QuizGame({
  pool,
  slug,
  token,
}: {
  pool: VocabularySummary[];
  slug: string;
  token: string | null;
}) {
  // Khởi tạo lười: component chỉ mount SAU KHI pool đã tải (trang cha render có
  // điều kiện), nên ván đầu là một ván thật chứ không phải ván rỗng chờ effect.
  const [round, setRound] = useState<Question[]>(() => buildRound(pool));
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);

  const start = useCallback(() => {
    setRound(buildRound(pool));
    setIndex(0);
    setPicked(null);
    setScore(0);
    setDone(false);
  }, [pool]);

  if (done) {
    return (
      <Panel className="px-6 py-10 text-center">
        <Trophy size={24} strokeWidth={1.75} aria-hidden className="mx-auto text-ok" />
        <p className="mt-3 text-subtitle font-semibold">
          Đúng {score}/{round.length}
        </p>
        <p className="mt-1.5 text-small text-ink-muted">
          {score === round.length
            ? "Trọn vẹn! Chủ đề này đã nằm lòng."
            : score >= round.length / 2
              ? "Khá lắm. Chơi thêm một ván để chắc hơn."
              : "Đừng nản — lặp lại vài lần là nhớ."}
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Button onClick={start}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden />
            Chơi lại
          </Button>
          <ButtonLink href={`/learn/vocabulary/${slug}`} variant="secondary">
            Về danh sách từ
          </ButtonLink>
        </div>
      </Panel>
    );
  }

  const question = round[index];
  if (!question) return <Skeleton className="h-40" />;

  function pick(option: string) {
    if (picked !== null) return;
    setPicked(option);
    const correct = option === question!.word.meaning_vi;
    if (correct) setScore((value) => value + 1);
    if (token) recordReview(token, question!.word.id, correct ? GRADE_GOOD : GRADE_FORGOT);
  }

  function next() {
    if (index + 1 >= round.length) {
      setDone(true);
      return;
    }
    setIndex(index + 1);
    setPicked(null);
  }

  const correct = question.word.meaning_vi;

  return (
    <>
      <p className="mb-3 font-data text-small tabular-nums text-ink-muted">
        Câu {index + 1}/{round.length} · đúng {score}
      </p>
      <Panel className="p-6">
        <p className="text-label font-semibold uppercase text-ink-faint">Chọn nghĩa của</p>
        <p className="mt-2 text-[1.6rem] font-semibold leading-tight">{question.word.headword}</p>
        {question.word.phonetic && (
          <p className="mt-1 font-data text-small text-ink-faint">{question.word.phonetic}</p>
        )}

        <div className="mt-5 grid gap-2">
          {question.options.map((option) => {
            const isCorrect = option === correct;
            const isPicked = option === picked;
            return (
              <button
                key={option}
                type="button"
                onClick={() => pick(option)}
                disabled={picked !== null}
                className={[
                  "rounded border px-4 py-3 text-left transition-colors",
                  picked === null && "border-rule-strong hover:bg-recess",
                  picked !== null && isCorrect && "border-ok bg-ok-tint text-ok",
                  picked !== null &&
                    isPicked &&
                    !isCorrect &&
                    "border-alert bg-alert-tint text-alert",
                  picked !== null && !isPicked && !isCorrect && "border-rule opacity-60",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {option}
              </button>
            );
          })}
        </div>

        {picked !== null && (
          <div className="mt-5 flex items-center justify-between gap-3">
            <p className="text-small text-ink-muted">
              {picked === correct ? "Đúng rồi!" : `Đáp án: ${correct}`}
            </p>
            <Button size="sm" onClick={next}>
              {index + 1 >= round.length ? "Xem kết quả" : "Câu tiếp"}
            </Button>
          </div>
        )}
      </Panel>
    </>
  );
}

export default function QuizPage() {
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
          { href: "", label: "Trắc nghiệm" },
        ]}
      />
      <PageHeader
        eyebrow="Minigame"
        title="Trắc nghiệm nhanh"
        description={`${topicName} — chọn nghĩa đúng cho mỗi từ.`}
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {!pool && !error && <Skeleton className="h-56" />}

      {pool && pool.length < 4 ? (
        <EmptyState
          title="Chưa đủ từ để chơi"
          description={`Cần ít nhất 4 từ, hiện có ${pool.length}. Quay lại sau khi có thêm nội dung.`}
          action={
            <ButtonLink href={`/learn/vocabulary/${rawSlug}`} variant="secondary">
              Về danh sách từ
            </ButtonLink>
          }
        />
      ) : (
        pool && <QuizGame pool={pool} slug={rawSlug} token={token} />
      )}
    </Page>
  );
}
