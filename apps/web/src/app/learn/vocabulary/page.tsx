"use client";

import {
  API_ROUTES,
  type TopicPublic,
  type VocabularyDetail,
  type VocabularyPage as VocabularyListPage,
  type VocabularyProgress,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import { ChevronDown, Circle, CircleCheck, CircleDot, Library } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AccentRow } from "@/components/audio-button";
import {
  Alert,
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
 * Không dùng `warn`/`alert` cho "đang học": nó là tiến trình bình thường, không
 * phải chuyện cần cảnh báo, và tiêu màu cảnh báo vào đây thì lúc có lỗi thật
 * sẽ không còn gì để nói.
 */
const MASTERY = {
  new: { tone: "neutral", icon: Circle, label: "chưa học" },
  learning: { tone: "action", icon: CircleDot, label: "đang học" },
  mastered: { tone: "ok", icon: CircleCheck, label: "đã thuộc" },
} as const;

type MasteryLevel = keyof typeof MASTERY;

function VocabularyBrowser() {
  const router = useRouter();
  const params = useSearchParams();
  const topicSlug = params.get("topic");
  // `offset` ở URL chứ không ở state, cùng lý do `topic` ở đó: đổi chủ đề là
  // một lần điều hướng, và link chủ đề không mang `offset` — nên chuyển chủ đề
  // TỰ về trang đầu. Giữ ở state thì đang ở trang 3 của "Business" mà bấm sang
  // một chủ đề chỉ có 5 từ sẽ ra danh sách rỗng, trông y như chủ đề đó không
  // có từ nào. Nút Back và F5 cũng đúng theo.
  const offset = Math.max(0, Number(params.get("offset") ?? 0) || 0);
  const { canEdit, token } = useSession();
  const [topics, setTopics] = useState<TopicPublic[]>([]);
  // Đóng dấu chủ đề mà nó thuộc về, nên đổi chủ đề là danh sách cũ tự trở nên
  // lỗi thời theo suy diễn. Xoá nó từ trong effect sẽ là một setState đồng bộ
  // trong thân effect — một lượt render dây chuyền, và một khoảnh khắc mà từ
  // của chủ đề cũ hiện dưới tiêu đề của chủ đề mới.
  const [total, setTotal] = useState(0);
  const [loaded, setLoaded] = useState<{
    topic: string | null;
    offset: number;
    words: VocabularySummary[];
  } | null>(null);
  // Đóng dấu chủ đề y như `loaded`, và vì đúng lý do đó: nếu không, đổi chủ đề
  // sẽ hiện tiến độ của chủ đề cũ dưới tiêu đề chủ đề mới — một con số sai mà
  // trông hoàn toàn hợp lý.
  const [progressState, setProgressState] = useState<{
    topic: string | null;
    data: VocabularyProgress;
  } | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<VocabularyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then(setTopics)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const parts = [topicSlug ? `topic=${encodeURIComponent(topicSlug)}` : "", `offset=${offset}`];
    const query = `?${parts.filter(Boolean).join("&")}`;
    apiFetch<VocabularyListPage>(`${API_ROUTES.vocabulary}${query}`)
      .then((page) => {
        setLoaded({ topic: topicSlug, offset, words: page.items });
        setTotal(page.total);
      })
      .catch(() => setError("Không tải được danh sách từ."));
  }, [topicSlug, offset]);

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
  // `token &&` chứ không xoá state trong effect: đăng xuất phải làm tiến độ biến
  // mất, nhưng một `setState` đồng bộ trong thân effect là một lượt render dây
  // chuyền và bị `react-hooks/set-state-in-effect` chặn thẳng. Suy diễn thì
  // không bao giờ lệch pha với thứ nó mô tả.
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

  const activeTopic = topics.find((topic) => topic.slug === topicSlug);

  return (
    <Page>
      <PageHeader
        eyebrow="Từ vựng"
        title={activeTopic ? activeTopic.name : "Tất cả từ vựng"}
        description={
          activeTopic?.description ?? "Bấm vào một từ để xem nghĩa, ví dụ và phát âm bốn giọng."
        }
      />

      {/* Bộ lọc nằm trên trang chứ không chỉ ở URL: đến đây từ một bookmark thì
          trước đây không còn cách nào đổi chủ đề hay quay về danh sách đầy đủ. */}
      {topics.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          <ButtonLink
            href="/learn/vocabulary"
            size="sm"
            variant={topicSlug ? "secondary" : "primary"}
          >
            Tất cả
          </ButtonLink>
          {topics.map((topic) => (
            <ButtonLink
              key={topic.id}
              href={`/learn/vocabulary?topic=${topic.slug}`}
              size="sm"
              variant={topic.slug === topicSlug ? "primary" : "secondary"}
            >
              {topic.name}
            </ButtonLink>
          ))}
        </div>
      )}

      {/* Trước đây trang này chỉ là một cuốn từ điển: mở ra xem nghĩa rồi thôi,
          không cho biết mình đã học tới đâu và cũng không có lối nào để bắt đầu
          học. Hai thứ đó nằm ở đây. */}
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

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!words && <SkeletonList rows={5} />}

      {words?.length === 0 && (
        <EmptyState
          icon={Library}
          title={activeTopic ? `Chủ đề ${activeTopic.name} chưa có từ nào` : "Chưa có từ nào"}
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
          router.push(query ? `/learn/vocabulary?${query}` : "/learn/vocabulary");
        }}
      />
    </Page>
  );
}

// Khớp `DEFAULT_LIMIT` ở `app/schemas/common.py`; máy chủ vẫn là nơi quyết định.
const PAGE_SIZE = 50;

export default function VocabularyPage() {
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
      <VocabularyBrowser />
    </Suspense>
  );
}
