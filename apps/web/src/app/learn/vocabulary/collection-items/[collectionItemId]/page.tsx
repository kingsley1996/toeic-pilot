"use client";

import {
  API_ROUTES,
  type VocabularyItemDetail,
  type VocabularyPage as VocabularyListPage,
  type VocabularyProgress,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import { Gamepad2, Keyboard, Layers, Library } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import {
  Alert,
  ButtonLink,
  EmptyState,
  Page,
  PageHeader,
  PanelLink,
  Skeleton,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

import { MIN_WORDS, TopicSession } from "../../_games";

/*
 * Trang cuốn sách của cây từ vựng: hai cột.
 *
 * TRÁI: "Danh sách chủ đề (topic)" — học viên chọn chủ đề, mặc định chủ đề đầu
 * tiên vì vào cuốn sách là để HỌC NGAY, không phải để chọn tiếp một lần nữa.
 * PHẢI: ba module học cho chủ đề đang chọn, bày qua tabs. Cả ba CHUNG MỘT cơ
 * chế: đi qua TỪNG TỪ, xong phần tương tác thì hiện năm nút tự chấm
 * (TopicSession) — chỉ khác cách từ đó xuất hiện (gõ / thẻ lật / trắc nghiệm).
 * Bàn cờ ghép từ tạm thời không nằm ở đây.
 */

const TABS = [
  { id: "typing", label: "Gõ từ", Icon: Keyboard },
  { id: "flashcard", label: "Thẻ lật", Icon: Layers },
  { id: "quiz", label: "Trắc nghiệm", Icon: Gamepad2 },
] as const;

type TabId = (typeof TABS)[number]["id"];

function CollectionItemDetail() {
  const itemId = String(useParams<{ collectionItemId: string }>().collectionItemId ?? "");
  const { status, token } = useSession();
  /* `?topic=<slug>` mở thẳng một chủ đề cụ thể thay vì chủ đề đầu tiên. Cần cho
     lối "học tiếp" trên trang chủ: nếu học viên đang dở chủ đề thứ tư của cuốn
     sách, dẫn họ về cuốn sách rồi mở chủ đề đầu tiên là ném họ ra khỏi đúng chỗ
     họ vừa rời đi. Chỉ là giá trị KHỞI TẠO — bấm sang chủ đề khác không viết
     lại URL, vì làm thế sẽ nhồi lịch sử trình duyệt bằng từng cú bấm tab. */
  const wantedSlug = useSearchParams().get("topic");

  const [detail, setDetail] = useState<VocabularyItemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Slug đang chọn; NULL nghĩa là "chưa từng bấm" — chỉ dùng đúng một lần để đặt
  // mặc định sang chủ đề đầu tiên.
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("typing");
  // Hồ từ cache theo slug: chuyển chủ đề qua lại không đáng tải lại cùng một danh
  // sách. Từ là tĩnh với người học nên không cần làm mới giữa phiên. Giá trị
  // `undefined` = chưa từng tải (đang loading); mảng rỗng = đã tải nhưng không
  // có từ (hoặc tải lỗi) — nhờ đó không cần một state loading riêng.
  const [pools, setPools] = useState<Record<string, VocabularySummary[]>>({});
  // Tiến độ cache theo slug y hệt hồ từ: key undefined = chưa tải (meter ẩn),
  // có giá trị = đã tải. Đổi chủ đề KHÔNG tự xoá cache — số liệu cũ thuộc về
  // slug cũ và meter chỉ đọc của slug đang mở. Bump lên số mới mỗi lần một từ
  // được chấm xong để effect đọc lại con số thật từ server thay vì tự cộng ở
  // client.
  const [progressBySlug, setProgressBySlug] = useState<Record<string, VocabularyProgress>>({});
  const [progressKey, setProgressKey] = useState(0);

  useEffect(() => {
    if (!itemId) return;
    let stale = false;
    apiFetch<VocabularyItemDetail>(API_ROUTES.vocabularyCollectionItem(itemId))
      .then((body) => {
        if (stale) return;
        setDetail(body);
        // Mặc định chủ đề đầu tiên — đặt ĐÚNG MỘT LẦN lúc dữ liệu về, dùng
        // `activeSlug === null` làm cờ. Đặt ở đây chứ không phải một effect
        // riêng: không có vòng re-render nào ngoài vòng tải dữ liệu.
        if (body.topics.length > 0) {
          // Slug trong URL chỉ được dùng khi nó THUỘC cuốn sách này; một slug
          // lạc (chủ đề đã chuyển sách, link cũ) rơi về chủ đề đầu tiên chứ
          // không để trang trống.
          const wanted = body.topics.find((topic) => topic.slug === wantedSlug);
          setActiveSlug((current) => current ?? wanted?.slug ?? body.topics[0]!.slug);
        }
      })
      .catch(() => setError("Không tải được cuốn sách này."));
    return () => {
      stale = true;
    };
  }, [itemId, wantedSlug]);

  const topics = detail?.topics ?? [];
  const activeTopic = topics.find((topic) => topic.slug === activeSlug) ?? topics[0] ?? null;
  const progress = activeTopic ? progressBySlug[activeTopic.slug] : undefined;

  useEffect(() => {
    if (!activeTopic || pools[activeTopic.slug] !== undefined) return;
    let stale = false;
    apiFetch<VocabularyListPage>(
      `${API_ROUTES.vocabulary}?topic=${encodeURIComponent(activeTopic.slug)}&limit=200`,
    )
      .then((page) => {
        if (stale) return;
        setPools((prev) => ({ ...prev, [activeTopic.slug]: page.items }));
      })
      .catch(() => {
        if (stale) return;
        // Hồ từ hỏng KHÔNG được làm trắng cả trang: trả về mảng rỗng để module
        // nói "chưa có từ" thay vì treo skeleton mãi.
        setPools((prev) => ({ ...prev, [activeTopic.slug]: [] }));
      });
    return () => {
      stale = true;
    };
  }, [activeTopic, pools]);

  // Tiến độ đọc lại theo (token, chủ đề, lần chấm xong): không auth thì không có
  // con số nào mà hiện — meter biến mất, không hiện số 0 giả.
  useEffect(() => {
    if (!token || !activeTopic) return;
    let stale = false;
    apiFetch<VocabularyProgress>(
      `${API_ROUTES.vocabularyProgress}?topic=${encodeURIComponent(activeTopic.slug)}`,
      { token },
    )
      .then((body) => {
        if (!stale) setProgressBySlug((prev) => ({ ...prev, [activeTopic.slug]: body }));
      })
      .catch(() => {});
    return () => {
      stale = true;
    };
  }, [token, activeTopic, progressKey]);

  return (
    <Page>
      {detail && (
        <Breadcrumbs
          trail={[
            { href: "/learn/vocabulary", label: "Từ vựng" },
            {
              href: `/learn/vocabulary/collections/${detail.collection_id}`,
              label: detail.collection_name,
            },
          ]}
        />
      )}

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {!detail && !error && (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 2 }, (_, index) => (
            <Skeleton key={index} className="h-40" />
          ))}
        </div>
      )}

      {detail && (
        <>
          <PageHeader title={detail.name} description={detail.description ?? undefined} />

          {topics.length === 0 && (
            <EmptyState
              icon={Library}
              title="Chưa có chủ đề nào trong cuốn sách này"
              description="Quay lại sau nhé."
            />
          )}

          {activeTopic && (
            <div className="grid items-start gap-4 lg:grid-cols-[18rem_1fr]">
              {/* Danh sách chủ đề — panel cố định chiều rộng, cuộn cùng trang. */}
              <section
                aria-label="Danh sách chủ đề (topic)"
                className="rounded border border-rule-strong bg-panel"
              >
                <h2 className="border-b border-rule px-4 py-3 text-small font-semibold uppercase tracking-wide text-ink-faint">
                  Danh sách chủ đề (topic)
                </h2>
                <div className="flex flex-row gap-1 overflow-x-auto p-2 lg:flex-col">
                  {topics.map((topic) => {
                    const isActive = topic.slug === activeTopic.slug;
                    return (
                      <button
                        key={topic.id}
                        type="button"
                        onClick={() => setActiveSlug(topic.slug)}
                        aria-current={isActive ? "true" : undefined}
                        className={cx(
                          "min-w-44 shrink-0 rounded border px-3 py-2 text-left transition-colors lg:min-w-0",
                          isActive
                            ? "border-action bg-action-tint"
                            : "border-transparent hover:bg-recess",
                        )}
                      >
                        <span
                          className={cx(
                            "block text-small font-semibold",
                            isActive ? "text-action-ink" : "text-ink",
                          )}
                        >
                          {topic.name}
                        </span>
                        <span className="block font-data text-label tabular-nums text-ink-faint">
                          {topic.entry_count} từ
                        </span>
                      </button>
                    );
                  })}
                </div>
              </section>

              {/* Các module học — một hồ từ chung cho cả tab, tải một lần theo chủ đề. */}
              <section aria-label={`Học chủ đề ${activeTopic.name}`}>
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <h2 className="text-subtitle">{activeTopic.name}</h2>
                  <span className="font-data text-small text-ink-muted">
                    {activeTopic.entry_count} từ
                  </span>
                  {/* Chỉ cho người đã đăng nhập. Điều kiện là `authenticated`
                      chứ không phải phủ định của `anonymous`: phiên còn
                      `loading` thì chưa biết là ai, và hiện trước rồi gỡ đi là
                      một nút nháy lên rồi biến mất ngay dưới con trỏ. */}
                  {status === "authenticated" && (
                    <PanelLink
                      href={`/learn/vocabulary/${activeTopic.slug}`}
                      className="ml-auto border-rule px-3 py-1.5 text-small font-semibold hover:bg-recess"
                    >
                      Xem danh sách từ
                    </PanelLink>
                  )}
                </div>

                {/* Meter tiến độ chủ đề: đếm từ ĐÃ CHẤM — bấm bất kỳ mức nào
                    (kể cả "Học lại") là từ ra khỏi `new`, nên con số nhích sau
                    MỖI từ chấm. `mastered` chỉ tăng khi interval chạm ngưỡng,
                    không phải thước đo của một phiên học. Đọc lại sau mỗi lần
                    chấm, không tự cộng ở client. Không auth thì không hiện:
                    con số 0 cho khách là lời nói dối chứ không phải "chưa có
                    dữ liệu". */}
                {progress && progress.total > 0 && (
                  <div
                    aria-label={`Tiến độ ${progress.total - progress.new} trên ${progress.total} từ`}
                    className="mb-4 rounded border border-rule-strong bg-panel px-4 py-3"
                  >
                    <div className="flex flex-wrap justify-between gap-2 font-data text-small tabular-nums text-ink-muted">
                      <span>Tiến độ</span>
                      <span>
                        {progress.total - progress.new}/{progress.total}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded bg-recess">
                      <div
                        className="h-full rounded bg-ok transition-all"
                        style={{
                          width: `${Math.round(((progress.total - progress.new) / progress.total) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

                {/* Nút chọn module: gạch action đánh dấu cái đang mở — màu là tín
                    hiệu, chữ vẫn mang nghĩa (icon + nhãn không đổi). Không dùng
                    role="tablist": widget đó đòi hỏi điều hướng phím mũi tên, mà
                    đây chỉ là chuyển nội dung, nên aria-pressed nói đúng hơn. */}
                <div className="mb-4 flex flex-wrap gap-1 border-b border-rule">
                  {TABS.map(({ id, label, Icon }) => {
                    const isActive = tab === id;
                    return (
                      <button
                        key={id}
                        type="button"
                        aria-pressed={isActive}
                        onClick={() => setTab(id)}
                        className={cx(
                          "-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-small font-semibold transition-colors",
                          isActive
                            ? "border-action text-ink"
                            : "border-transparent text-ink-muted hover:text-ink",
                        )}
                      >
                        <Icon size={14} strokeWidth={2} aria-hidden />
                        {label}
                      </button>
                    );
                  })}
                </div>

                {pools[activeTopic.slug] === undefined ? (
                  <Skeleton className="h-56" />
                ) : (
                  /* key CHỈ theo slug, KHÔNG theo tab: chuyển tab là đổi cách
                     TƯƠNG TÁC với cùng từ đang học trên cùng bàn cờ — giữ
                     nguyên instance thì khung, từ hiện tại và chỗ đứng trong
                     ván không đổi, nên không có giật render khi bấm tab. Đổi
                     chủ đề mới remount. */
                  <TopicModules
                    key={activeTopic.slug}
                    tab={tab}
                    topicId={activeTopic.id}
                    pool={pools[activeTopic.slug]!}
                    token={token}
                    onGraded={() => setProgressKey((value) => value + 1)}
                  />
                )}
              </section>
            </div>
          )}
        </>
      )}
    </Page>
  );
}

function TopicModules({
  tab,
  topicId,
  pool,
  token,
  onGraded,
}: {
  tab: TabId;
  /** Id của topic — bàn cờ học tới đâu được lưu theo (user, topic) trên server,
      dùng chung cho cả ba module và sống sót qua F5. */
  topicId: string;
  pool: VocabularySummary[];
  token: string | null;
  /** Một từ vừa được chấm xong — điểm ĐÃ ghi trên server, đọc lại tiến độ. */
  onGraded?: () => void;
}) {
  if (pool.length === 0) {
    return (
      <EmptyState
        title="Chưa có từ trong chủ đề này"
        description="Nội dung đang được biên soạn. Quay lại sau nhé."
      />
    );
  }

  if (pool.length < MIN_WORDS[tab]) {
    return (
      <EmptyState
        title="Chưa đủ từ để học"
        description={`Cần ít nhất ${MIN_WORDS[tab]} từ, hiện có ${pool.length}.`}
      />
    );
  }

  // Cả ba module đều GHI điểm qua /review, nên cả ba đều cần tài khoản — không
  // chấm được thì chơi vẫn chạy nhưng "đã thuộc" đứng yên, còn tệ hơn là nói rõ.
  if (!token) {
    return (
      <EmptyState
        icon={Keyboard}
        title="Đăng nhập để bắt đầu học"
        description="Mỗi lượt tự chấm sẽ ghi vào lịch ôn của bạn, nên cần một tài khoản."
        action={<ButtonLink href="/login">Đăng nhập</ButtonLink>}
      />
    );
  }

  return (
    <TopicSession pool={pool} token={token} mode={tab} topicId={topicId} onGraded={onGraded} />
  );
}

export default function CollectionItemDetailPage() {
  // useSearchParams đẩy route ra khỏi render tĩnh trừ khi nó nằm trong một
  // Suspense boundary — cùng lý do đã ghi ở `/learn/vocabulary/[slug]`.
  return (
    <Suspense
      fallback={
        <Page>
          <Skeleton className="h-9 w-64" />
          <Skeleton className="mt-6 h-64" />
        </Page>
      }
    >
      <CollectionItemDetail />
    </Suspense>
  );
}
