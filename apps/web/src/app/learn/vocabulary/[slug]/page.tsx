"use client";

import {
  API_ROUTES,
  type TopicPublic,
  type VocabularyDetail,
  type VocabularyPage as VocabularyListPage,
  type VocabularyProgress,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import {
  ChevronDown,
  Circle,
  CircleCheck,
  CircleDot,
  Gamepad2,
  Library,
  ListChecks,
  Lock,
} from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";

import { AccentRow } from "@/components/audio-button";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { LoginModal } from "@/components/login-modal";
import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  Meter,
  Page,
  PageHeader,
  Pager,
  Panel,
  SkeletonList,
  StatusTag,
  Tag,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/**
 * Ba mức thành thạo, luôn kèm icon chứ không chỉ có màu (DESIGN-SYSTEM §9.4).
 *
 * Thang này là THỨ TỰ — chưa học → đang học → đã thuộc — nên icon cũng đi theo
 * một dãy liền mạch của cùng một họ (vòng tròn rỗng → có chấm → có dấu tích).
 */
const MASTERY = {
  new: { tone: "neutral", icon: Circle, label: "chưa học" },
  learning: { tone: "action", icon: CircleDot, label: "đang học" },
  mastered: { tone: "ok", icon: CircleCheck, label: "đã thuộc" },
} as const;

type MasteryLevel = keyof typeof MASTERY;

const PAGE_SIZE = 50;

function WordList() {
  // `all` là lối xem toàn bộ; các slug khác lọc theo chủ đề.
  const rawSlug = String(useParams<{ slug: string }>().slug ?? "");
  const topicSlug = rawSlug === "all" ? null : rawSlug;
  const params = useSearchParams();
  const offset = Math.max(0, Number(params.get("offset") ?? 0) || 0);
  const { canEdit, status, token } = useSession();
  const router = useRouter();
  // Suy ra "hộp thoại đang mở" từ phiên + một lần đóng tay, không mở nó bằng
  // `setState` trong effect — luật `react-hooks/set-state-in-effect`.
  const [dismissed, setDismissed] = useState(false);

  const [topic, setTopic] = useState<TopicPublic | null>(null);
  const [loaded, setLoaded] = useState<{
    topic: string | null;
    offset: number;
    words: VocabularySummary[];
  } | null>(null);
  const [total, setTotal] = useState(0);
  const [progressState, setProgressState] = useState<{
    topic: string | null;
    data: VocabularyProgress;
  } | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<VocabularyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated") return;
    if (!topicSlug) return;
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then((topics) => setTopic(topics.find((t) => t.slug === topicSlug) ?? null))
      .catch(() => {});
  }, [topicSlug, status]);

  useEffect(() => {
    // Khách vãng lai không được xem trang này, nên cũng không đi lấy dữ liệu cho
    // nó. `GET /vocabulary` vốn công khai; đây là chuyện đỡ một vòng mạng, và
    // không để danh sách từ hiện ra sau lưng hộp thoại.
    if (status !== "authenticated") return;
    // `openId`/`detail` KHÔNG xoá ở đây: `loaded` đóng dấu chủ đề nên danh sách cũ
    // không bao giờ hiện dưới nhãn mới, và một openId trỏ vào từ không còn trong
    // danh sách thì đơn giản là không render. Xoá đồng bộ trong thân effect là
    // một lượt render dây chuyền — đúng thứ rule `react-hooks/set-state-in-effect`
    // chặn thẳng.
    const parts = [topicSlug ? `topic=${encodeURIComponent(topicSlug)}` : "", `offset=${offset}`];
    const query = `?${parts.filter(Boolean).join("&")}`;
    apiFetch<VocabularyListPage>(`${API_ROUTES.vocabulary}${query}`)
      .then((page) => {
        setLoaded({ topic: topicSlug, offset, words: page.items });
        setTotal(page.total);
      })
      .catch(() => setError("Không tải được danh sách từ."));
  }, [topicSlug, offset, status]);

  // Tiến độ chỉ tồn tại khi đã đăng nhập. Khách vãng lai vẫn duyệt được từ —
  // `GET /vocabulary` là endpoint công khai — nhưng không có gì để hiện, và
  // hiện "chưa học" cho mọi từ thì là nói dối chứ không phải để trống.
  useEffect(() => {
    if (!token) return;
    const query = topicSlug ? `?topic=${encodeURIComponent(topicSlug)}` : "";
    apiFetch<VocabularyProgress>(`${API_ROUTES.vocabularyProgress}${query}`, { token })
      .then((data) => setProgressState({ topic: topicSlug, data }))
      .catch(() => {});
  }, [token, topicSlug]);

  // Đóng dấu CẢ hai: danh sách của trang trước dưới nhãn trang sau cũng sai y
  // như danh sách chủ đề cũ dưới tiêu đề chủ đề mới.
  const words = loaded?.topic === topicSlug && loaded.offset === offset ? loaded.words : null;
  const progress = token && progressState?.topic === topicSlug ? progressState.data : null;
  const masteryById = new Map(
    progress?.entries.map((entry) => [entry.entry_id, entry.mastery as MasteryLevel]) ?? [],
  );

  function toggle(id: string) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    setDetail(null);
    apiFetch<VocabularyDetail>(API_ROUTES.vocabularyDetail(id))
      .then(setDetail)
      .catch(() => setError("Không tải được chi tiết từ này."));
  }

  // `quiz`/`match` là segment TĨNH đứng trước `[slug]`, nên chúng thắng trong
  // cuộc đua bắt đường dẫn — `/learn/vocabulary/quiz/business` không rơi vào
  // trang danh sách với slug "quiz".
  const quizHref = `/learn/vocabulary/quiz/${rawSlug}`;
  const matchHref = `/learn/vocabulary/match/${rawSlug}`;

  if (status === "loading") {
    return (
      <Page>
        <SkeletonList rows={5} />
      </Page>
    );
  }

  /*
   * Danh sách từ đứng SAU cổng đăng nhập, khác với cây tuyển tập ở trên nó.
   *
   * Tuyển tập và cuốn sách trả lời "ở đây có gì để học" — phải xem được trước
   * khi quyết định lập tài khoản. Trang này thì đã là chính nội dung: toàn bộ
   * từ, nghĩa, ví dụ, bốn giọng đọc. Và nó là chỗ duy nhất trong khu từ vựng
   * mà mức thành thạo của từng từ hiện ra, thứ chỉ tồn tại khi có tài khoản.
   *
   * Chặn ở cả hai đầu, cùng luật với khu luyện thi: hai lối vào ("Xem toàn bộ
   * từ vựng" ở trang tuyển tập, "Xem danh sách từ" ở trang cuốn sách) đã ẩn với
   * khách, còn trang này chặn người gõ thẳng URL hay mở lại dấu trang.
   */
  if (status === "anonymous") {
    return (
      <Page>
        <Breadcrumbs trail={[{ href: "/learn/vocabulary", label: "Từ vựng" }]} />
        <div className="mt-4">
          <EmptyState
            icon={Lock}
            title="Đăng nhập để xem danh sách từ"
            description="Cần tài khoản để lưu mức thuộc của từng từ và lịch ôn của bạn."
            action={<Button onClick={() => setDismissed(false)}>Đăng nhập</Button>}
          />
        </div>
        <LoginModal
          open={!dismissed}
          onClose={() => setDismissed(true)}
          onSuccess={() => setDismissed(true)}
          next={`/learn/vocabulary/${rawSlug}`}
          title="Đăng nhập để xem danh sách từ"
          description="Cần tài khoản để lưu mức thuộc của từng từ và lịch ôn của bạn."
        />
      </Page>
    );
  }

  return (
    <Page>
      <Breadcrumbs
        trail={[
          { href: "/learn/vocabulary", label: "Từ vựng" },
          { href: "", label: topic?.name ?? (topicSlug ? topicSlug : "Tất cả từ vựng") },
        ]}
      />

      <PageHeader
        eyebrow="Từ vựng"
        title={topic ? topic.name : "Tất cả từ vựng"}
        description={
          topic?.description ?? "Bấm vào một từ để xem nghĩa, ví dụ và phát âm bốn giọng."
        }
      />

      {progress && progress.total > 0 && (
        <Panel className="mb-6 px-4 py-4">
          <Meter
            value={progress.mastered}
            max={progress.total}
            label="Đã thuộc"
            ticks={Math.min(progress.total, 8)}
          />
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="text-small text-ink-muted">
              {progress.learning} đang học · {progress.new} chưa học
            </span>
            <div className="flex-1" />
            {progress.due > 0 ? (
              <ButtonLink href="/learn/review" size="sm">
                Ôn {progress.due} từ đến hạn
              </ButtonLink>
            ) : (
              <ButtonLink
                href="/learn/review"
                size="sm"
                variant={progress.new > 0 ? "primary" : "secondary"}
              >
                {progress.new > 0 ? "Học từ mới" : "Không còn từ đến hạn"}
              </ButtonLink>
            )}
          </div>
        </Panel>
      )}

      {/* Hai minigame lấy chính các từ của trang này — trắc nghiệm và ghép nối. */}
      {total > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          <ButtonLink href={quizHref} size="sm" variant="secondary">
            <Gamepad2 size={14} strokeWidth={2} aria-hidden />
            Trắc nghiệm nhanh
          </ButtonLink>
          <ButtonLink href={matchHref} size="sm" variant="secondary">
            <ListChecks size={14} strokeWidth={2} aria-hidden />
            Ghép từ với nghĩa
          </ButtonLink>
        </div>
      )}

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!words && <SkeletonList rows={5} />}

      {words?.length === 0 && (
        <EmptyState
          icon={Library}
          title={topic ? `Chủ đề ${topic.name} chưa có từ nào` : "Chưa có từ nào"}
          description={
            canEdit
              ? "Từ mới phải có đủ audio bốn giọng trước khi xuất bản được."
              : "Nội dung đang được biên soạn."
          }
          action={canEdit ? <ButtonLink href="/admin/vocabulary">Thêm từ</ButtonLink> : undefined}
        />
      )}

      <div className="space-y-2">
        {words?.map((word) => {
          const open = openId === word.id;
          const level = masteryById.get(word.id);
          return (
            <Panel key={word.id} className={cx("overflow-hidden", open && "border-rule-strong")}>
              <button
                type="button"
                onClick={() => toggle(word.id)}
                aria-expanded={open}
                className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-recess"
              >
                <div className="min-w-0 flex-1">
                  <span className="font-semibold">{word.headword}</span>
                  {word.phonetic && (
                    <span className="ml-2 font-data text-small text-ink-faint">
                      {word.phonetic}
                    </span>
                  )}
                </div>
                <span className="hidden truncate text-small text-ink-muted sm:block">
                  {word.meaning_vi}
                </span>
                {level && (
                  <StatusTag tone={MASTERY[level].tone} icon={MASTERY[level].icon}>
                    {MASTERY[level].label}
                  </StatusTag>
                )}
                <Tag>{word.part_of_speech}</Tag>
                <ChevronDown
                  size={16}
                  strokeWidth={1.75}
                  aria-hidden
                  className={cx(
                    "shrink-0 text-ink-faint transition-transform",
                    open && "rotate-180",
                  )}
                />
              </button>

              {open && (
                <div className="animate-settle border-t border-rule bg-recess px-4 py-4">
                  {!detail ? (
                    <SkeletonList rows={1} />
                  ) : (
                    <>
                      <p className="font-semibold sm:hidden">{detail.meaning_vi}</p>
                      <p className="text-small text-ink-muted">{detail.meaning_en}</p>
                      {/* `showMissing` để giọng chưa có clip vẫn hiện ở dạng vô
                          hiệu hoá — người học cần biết nó tồn tại nhưng chưa
                          được thu, chứ không tưởng app chỉ có ba giọng. */}
                      <AccentRow clips={detail.headword_audio} showMissing className="mt-3" />
                      {detail.example && (
                        <div className="mt-4 rounded border border-rule bg-panel p-4">
                          <p className="italic">{detail.example}</p>
                          {detail.example_vi && (
                            <p className="mt-1 text-small text-ink-muted">{detail.example_vi}</p>
                          )}
                          <AccentRow clips={detail.example_audio} className="mt-3" />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </Panel>
          );
        })}
      </div>

      <Pager
        total={total}
        limit={PAGE_SIZE}
        offset={offset}
        onOffset={(next) => {
          const parts = [topicSlug ? `topic=${topicSlug}` : "", next ? `offset=${next}` : ""];
          const query = parts.filter(Boolean).join("&");
          router.push(
            query ? `/learn/vocabulary/${rawSlug}?${query}` : `/learn/vocabulary/${rawSlug}`,
          );
        }}
      />
    </Page>
  );
}

export default function VocabularyTopicPage() {
  // useSearchParams đẩy route ra khỏi render tĩnh trừ khi nó nằm trong một
  // Suspense boundary; không có cái này thì build cảnh báo và trang bị ship
  // dưới dạng dynamic route mà chẳng để làm gì.
  return (
    <Suspense
      fallback={
        <Page>
          <SkeletonList rows={5} />
        </Page>
      }
    >
      <WordList />
    </Suspense>
  );
}
