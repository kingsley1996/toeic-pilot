"use client";

import {
  API_ROUTES,
  type VocabularyItemDetail,
  type VocabularyPage as VocabularyListPage,
  type VocabularyProgress,
  type VocabularySummary,
  type VocabularyTopicProgress,
} from "@toeic-pilot/shared";
import { Check, Gamepad2, Keyboard, Layers, Library } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

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

/**
 * Trần chiều cao cho panel danh sách chủ đề, ĐO chứ không viết cứng.
 *
 * Panel không bắt đầu ở sát header — trên nó còn breadcrumb và tiêu đề trang,
 * và chiều cao khối đó đổi theo tên cuốn sách có xuống dòng hay không. Một
 * `calc(100dvh - 6rem)` viết tay vì thế đúng ở màn hình này và hụt ở màn hình
 * khác: panel thò xuống dưới mép màn hình đúng bằng phần chênh, và không có gì
 * báo.
 *
 * Cộng dồn `offsetTop` chứ không lấy `getBoundingClientRect`: panel là `sticky`,
 * nên rect trả về chỗ nó ĐANG được vẽ, còn `offsetTop` là chỗ nó nằm trong bố
 * cục — đo lúc đang ghim thì ra một con số nhỏ hơn thật.
 *
 * Sàn 240px: trên màn hình rất thấp thì thà panel thò ra một chút còn hơn co lại
 * thành một khe chỉ hở đúng một dòng.
 */
const LIST_GUTTER = 16;
const LIST_MIN = 240;

function fitTopicList(el: HTMLElement): void {
  let top = 0;
  for (let node: HTMLElement | null = el; node; node = node.offsetParent as HTMLElement | null) {
    top += node.offsetTop;
  }
  const room = Math.max(LIST_MIN, window.innerHeight - top - LIST_GUTTER);
  el.style.setProperty("--topic-list-max", `${room}px`);
}

function CollectionItemDetail() {
  const itemId = String(useParams<{ collectionItemId: string }>().collectionItemId ?? "");

  /* Đo ngay lúc node GẮN VÀO, qua ref callback. Panel nằm sau một nhánh điều
     kiện (`activeTopic &&`), nên một `useEffect` lúc mount chạy khi nó còn chưa
     tồn tại và không đo được gì — cùng cái bẫy mà `petland.tsx` ghi lại. */
  const topicPanel = useRef<HTMLElement | null>(null);
  const attachTopicList = useCallback((el: HTMLElement | null) => {
    topicPanel.current = el;
    if (el) fitTopicList(el);
  }, []);

  useEffect(() => {
    const refit = () => {
      if (topicPanel.current) fitTopicList(topicPanel.current);
    };
    window.addEventListener("resize", refit);
    return () => window.removeEventListener("resize", refit);
  }, []);
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
  /* Tiến độ của MỌI chủ đề trong cuốn sách, chỉ để đánh dấu chủ đề đã xong.
     Một lượt gọi cho cả cuốn sách, không phải một lượt cho mỗi chủ đề. */
  const [doneSlugs, setDoneSlugs] = useState<Set<string>>(new Set());

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

  /*
   * Chủ đề nào đã học hết, để gắn dấu tick.
   *
   * Cùng định nghĩa với thanh tiến độ ngay bên phải — `total - new === total`,
   * tức mọi từ đã được động tới — nên dấu tick xuất hiện đúng lúc thanh đầy.
   * Hai định nghĩa "xong" khác nhau trên cùng một màn hình là thứ người học đọc
   * ra là lỗi.
   *
   * Đọc lại theo `progressKey` y như meter: học xong từ cuối của một chủ đề thì
   * tick phải hiện ngay, không đợi tải lại trang.
   */
  useEffect(() => {
    if (!token || !itemId) return;
    let stale = false;
    apiFetch<VocabularyTopicProgress[]>(
      `${API_ROUTES.vocabularyTopicProgress}?item=${encodeURIComponent(itemId)}`,
      { token },
    )
      .then((rows) => {
        if (stale) return;
        setDoneSlugs(
          new Set(rows.filter((row) => row.total > 0 && row.new === 0).map((row) => row.slug)),
        );
      })
      .catch(() => {
        /* Không có tick thì danh sách vẫn dùng được; đừng làm hỏng cả trang. */
      });
    return () => {
      stale = true;
    };
  }, [token, itemId, progressKey]);

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
              {/*
               * Danh sách chủ đề — panel cố định chiều rộng, tự cuộn khi dài.
               *
               * Cuốn sách 14 chủ đề đã cao hơn một màn hình, và một danh sách
               * dài thì kéo cả trang dài theo trong khi cột học bên phải đứng
               * yên — người học phải cuộn qua hết danh sách mới về được chỗ
               * đang học. Nên nó tự cuộn TRONG panel, và panel dính lại dưới
               * header: một vùng cuộn trôi khỏi màn hình thì thanh cuộn của nó
               * chẳng giúp được ai.
               *
               * Chỉ từ `lg`. Dưới mức đó danh sách nằm ngang và đã có cuộn
               * ngang, còn dính lại thì lấy mất cả một dải chiều cao trên màn
               * hình vốn đã hẹp.
               */}
              {/*
               * MỘT bố cục cho mọi bề ngang: danh sách dọc, tự cuộn trong panel.
               *
               * Bản trước xếp ngang dưới `lg` và cuộn ngang. Hai chuyện hỏng vì
               * thế. Thứ nhất là dùng: mười bốn chủ đề trên một dải chỉ hở hai
               * cái rưỡi, muốn biết cuốn sách có gì thì phải vuốt hết. Thứ hai
               * là bố cục: bề ngang cộng dồn của mười bốn nút là 2 556px, và
               * `overflow-x-auto` KHÔNG ngăn nó nới vùng cuộn của cả tài liệu —
               * trang vuốt ngang được gần 300px dù không có thanh cuộn nào hiện
               * ra, tức trên điện thoại nội dung trôi đi mà không ai hiểu vì sao.
               * (`contain: paint` bịt được, nhưng đó là bịt triệu chứng.)
               *
               * Trần chiều cao thì khác nhau: dưới `lg` panel nằm TRÊN khu học
               * nên nó chỉ được lấy một khoảng cố định, còn từ `lg` nó là cột
               * riêng nên lấy hết chỗ trống đo được (xem `fitTopicList`).
               *
               * `min-w-0` vì ô lưới mặc định `min-width: auto`: một tên chủ đề
               * dài không xuống dòng được sẽ lại nới panel ra như cũ.
               */}
              <section
                ref={attachTopicList}
                aria-label="Danh sách chủ đề (topic)"
                className="flex max-h-64 min-w-0 flex-col rounded border border-rule-strong bg-panel lg:sticky lg:top-20 lg:max-h-[var(--topic-list-max,calc(100dvh-6rem))]"
              >
                <h2 className="shrink-0 border-b border-rule px-4 py-3 text-small font-semibold uppercase tracking-wide text-ink-faint">
                  Danh sách chủ đề (topic)
                </h2>
                <div className="flex min-h-0 flex-col gap-1 overflow-y-auto p-2">
                  {topics.map((topic) => {
                    const isActive = topic.slug === activeTopic.slug;
                    const isDone = doneSlugs.has(topic.slug);
                    return (
                      <button
                        key={topic.id}
                        type="button"
                        onClick={() => setActiveSlug(topic.slug)}
                        aria-current={isActive ? "true" : undefined}
                        className={cx(
                          "shrink-0 rounded border px-3 py-2 text-left transition-colors",
                          isActive
                            ? "border-action bg-action-tint"
                            : "border-transparent hover:bg-recess",
                        )}
                      >
                        <span
                          className={cx(
                            "flex items-center gap-1.5 text-small font-semibold",
                            isActive ? "text-action-ink" : "text-ink",
                          )}
                        >
                          {/* Dấu tick đứng TRƯỚC tên: chủ đề đã xong thì đọc
                              được ngay từ mép trái, không phải rà hết tên mới
                              thấy. `shrink-0` để tên dài đẩy nó đi mất. */}
                          {isDone && (
                            <Check size={14} strokeWidth={3} className="shrink-0 text-ok" />
                          )}
                          <span className="truncate">{topic.name}</span>
                        </span>
                        <span className="block font-data text-label tabular-nums text-ink-faint">
                          {topic.entry_count} từ
                          {/* Nói ra bằng CHỮ cho người đọc màn hình: một cái
                              tick là hình, và `aria-label` trên icon sẽ đọc
                              chen vào giữa tên chủ đề. */}
                          {isDone && <span className="sr-only"> — đã học xong</span>}
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
