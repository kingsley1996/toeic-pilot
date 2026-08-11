"use client";

import {
  API_ROUTES,
  type DictationDetail,
  type DictationPage,
  type DictationSummary,
} from "@toeic-pilot/shared";
import { Headphones } from "lucide-react";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { DictationExercise } from "@/components/dictation-exercise";
import {
  Alert,
  EmptyState,
  Page,
  PageHeader,
  Pager,
  Panel,
  SkeletonList,
  Tag,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Các câu chưa thuộc bài nào.
 *
 * Tồn tại vì cây topic→section→story ra đời sau: câu nhập trước đó có
 * `story_id` rỗng và sẽ biến mất khỏi luồng duyệt theo cây. Trang này giữ chúng
 * ở trong tầm với cho tới khi admin gán vào bài — và tự biến mất khi không còn
 * câu nào lẻ, nên nó không trở thành một lối đi thứ hai phải bảo trì mãi.
 */
// Khớp `DEFAULT_LIMIT` ở `app/schemas/common.py`.
const PAGE_SIZE = 50;

export default function StandaloneDictationPage() {
  const { status } = useRequireSession();
  const [items, setItems] = useState<DictationSummary[] | null>(null);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [active, setActive] = useState<DictationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DictationPage>(`${API_ROUTES.dictation}?standalone=true&offset=${offset}`)
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
      })
      .catch(() => setError("Không tải được danh sách câu."));
  }, [offset]);

  if (status !== "authenticated") {
    return (
      <Page className="max-w-2xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page className="max-w-2xl">
      <Breadcrumbs trail={[{ href: "/learn/dictation", label: "Dictation" }]} />
      <PageHeader
        eyebrow="Câu lẻ"
        title="Câu chưa thuộc bài nào"
        description="Mỗi câu đứng riêng, không theo thứ tự nào."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!items && <SkeletonList rows={4} />}

      {items?.length === 0 && (
        <EmptyState
          icon={Headphones}
          title="Không còn câu lẻ nào"
          description="Mọi câu đã được xếp vào bài. Vào Dictation để duyệt theo chủ đề."
        />
      )}

      {active ? (
        <>
          <p className="mb-2 text-small text-ink-muted">
            {active.word_count} từ · nghe lại bao nhiêu lần cũng được
          </p>
          <DictationExercise
            key={active.id}
            item={active}
            onNext={() => setActive(null)}
            nextLabel="Câu khác"
          />
        </>
      ) : (
        <div className="space-y-2">
          {items?.map((item, position) => (
            <Panel key={item.id} className="overflow-hidden">
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  apiFetch<DictationDetail>(API_ROUTES.dictationDetail(item.id))
                    .then(setActive)
                    .catch(() => setError("Không tải được câu này."));
                }}
                className="flex w-full items-center gap-4 px-4 py-3.5 text-left transition-colors hover:bg-recess"
              >
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded border border-rule bg-recess font-data text-small text-ink-muted">
                  {position + 1}
                </span>
                <span className="flex-1 text-small text-ink-muted">{item.word_count} từ</span>
                <Tag
                  tone={item.difficulty <= 2 ? "ok" : item.difficulty >= 4 ? "alert" : "neutral"}
                >
                  độ khó {item.difficulty}
                </Tag>
              </button>
            </Panel>
          ))}
          <Pager total={total} limit={PAGE_SIZE} offset={offset} onOffset={setOffset} />
        </div>
      )}
    </Page>
  );
}
