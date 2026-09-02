"use client";

import { API_ROUTES, type CollectionDetail, type TestSummary } from "@toeic-pilot/shared";
import { ArrowLeft, Clock, FileText, Lock, Users } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LoginModal } from "@/components/login-modal";
import { ButtonLink, EmptyState, Page, Panel, SectionHeader, Skeleton, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function CollectionPage() {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const slug = params.slug;
  const { status } = useSession();
  const [collection, setCollection] = useState<CollectionDetail | null>(null);
  const [missing, setMissing] = useState(false);
  /*
   * Đề mà khách vãng lai vừa bấm vào, và cũng là thứ quyết định hộp thoại đăng
   * nhập có mở hay không — một state chứ không phải hai, nên không có trạng thái
   * "đang mở nhưng không biết mở cho đề nào".
   *
   * Bộ đề và danh sách đề vẫn mở cho mọi người: phải xem được có những đề gì
   * rồi mới quyết định lập tài khoản. Ranh giới nằm ở trang chi tiết, chỗ bắt
   * đầu có bài làm để mà lưu.
   */
  const [gated, setGated] = useState<TestSummary | null>(null);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    apiFetch<CollectionDetail>(API_ROUTES.testCollection(slug))
      .then((data) => {
        if (!cancelled) setCollection(data);
      })
      .catch(() => {
        if (!cancelled) setMissing(true);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (missing) {
    return (
      <Page>
        <EmptyState
          icon={FileText}
          title="Không có bộ đề này"
          description="Có thể nó đã được gỡ, hoặc đường dẫn bị gõ sai."
          action={<ButtonLink href="/learn/tests">Về danh sách bộ đề</ButtonLink>}
        />
      </Page>
    );
  }

  if (collection === null) {
    return (
      <Page>
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-6 h-28 w-full" />
        <Skeleton className="mt-4 h-64 w-full" />
      </Page>
    );
  }

  return (
    <Page>
      <Link
        href="/learn/tests"
        className="inline-flex items-center gap-1.5 text-small font-semibold text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={14} strokeWidth={2} aria-hidden />
        Bộ đề thi
      </Link>

      {/* Bậc nền chìm, không phải card nổi có gradient như bản tham khảo:
          §6.3 nói độ nổi là viền + bậc nền, và một dải màu chuyển sắc là đúng
          thứ hệ này đã bỏ đi có chủ ý. */}
      <section className="mt-4 rounded border border-rule bg-recess p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2">
          {collection.source_tag && <Tag>{collection.source_tag}</Tag>}
          {collection.year !== null && <Tag>{collection.year}</Tag>}
        </div>
        <h1 className="mt-2">{collection.title}</h1>
        {collection.description && (
          <p className="mt-2 max-w-2xl text-ink-muted">{collection.description}</p>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-small text-ink-muted">
          <span>
            <span className="font-data tabular-nums text-ink">{collection.test_count}</span> đề
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Users size={14} strokeWidth={1.75} aria-hidden />
            <span className="font-data tabular-nums text-ink">{collection.attempt_count}</span> lượt
            làm
          </span>
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader title="Danh sách đề" />
        {collection.tests.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Bộ đề này chưa có đề nào"
            description="Đề sẽ xuất hiện ở đây khi được xuất bản."
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {collection.tests.map((test) => (
              <Panel key={test.id} className="flex flex-wrap items-center gap-4 p-4">
                <div className="min-w-[12rem] flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <p className="font-semibold">{test.title}</p>
                    {/* Mọi đề hiện đều miễn phí — không có trường nào trong
                        `practice_test` phân biệt trả phí, nên đây là nhãn tĩnh.
                        Ngày có đề trả phí thì phải thêm cột rồi đọc từ đó, chứ
                        không được để nhãn này nói dối. */}
                    <Tag tone="ok">Miễn phí</Tag>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-ink-muted">
                    <span className="inline-flex items-center gap-1.5">
                      <FileText size={13} strokeWidth={1.75} aria-hidden />
                      <span className="font-data tabular-nums">{test.question_count}</span> câu
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Users size={13} strokeWidth={1.75} aria-hidden />
                      <span className="font-data tabular-nums">{test.attempt_count}</span> lượt
                    </span>
                    {test.time_limit_seconds !== null && (
                      <span className="inline-flex items-center gap-1.5">
                        <Clock size={13} strokeWidth={1.75} aria-hidden />
                        <span className="font-data tabular-nums">
                          {Math.round(test.time_limit_seconds / 60)}
                        </span>{" "}
                        phút
                      </span>
                    )}
                  </div>
                </div>
                <ButtonLink
                  href={`/learn/tests/${slug}/${test.slug}`}
                  variant="secondary"
                  size="sm"
                  /* Vẫn là thẻ `a` thật, chỉ chặn ở lần bấm: giữ được chuột
                     giữa, menu chuột phải, và cả trường hợp phiên còn `loading`
                     — lúc đó chưa biết là ai nên cứ để đi, trang đích tự chặn. */
                  onClick={(event) => {
                    if (status !== "anonymous") return;
                    event.preventDefault();
                    setGated(test);
                  }}
                >
                  {status === "anonymous" && <Lock size={13} strokeWidth={2} aria-hidden />}
                  Xem chi tiết
                </ButtonLink>
              </Panel>
            ))}
          </div>
        )}
      </section>

      {gated && (
        <LoginModal
          open
          onClose={() => setGated(null)}
          onSuccess={() => router.push(`/learn/tests/${slug}/${gated.slug}`)}
          next={`/learn/tests/${slug}/${gated.slug}`}
          title="Đăng nhập để xem đề"
          description={`“${gated.title}” miễn phí, nhưng cần tài khoản để lưu bài làm và điểm số.`}
        />
      )}
    </Page>
  );
}
