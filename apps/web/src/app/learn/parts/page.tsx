"use client";

import { API_ROUTES, type PartSummary } from "@toeic-pilot/shared";
import { ArrowRight, Clock, Lock } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";

import { LoginModal } from "@/components/login-modal";
import { Page, PageHeader, Panel, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import { PART_META } from "@/lib/parts";

/**
 * Tầng 1 của khu "Luyện theo part". Số câu là dữ liệu server đo từ kho thật;
 * nhãn KHÔNG hiện ở đây — phân loại theo nhãn là việc của màn drill, chỗ người
 * ta đang chọn sẽ luyện gì.
 *
 * Danh sách CÔNG KHAI (khuôn khu luyện thi): khách xem được có gì. Hai nút mang
 * icon khoá cho khách, và một lần bấm mở hộp đăng nhập ngay tại chỗ thay vì đá
 * sang `/login` — API chặn tactics/sessions 401 là chốt cuối.
 */
export default function PartsHubPage() {
  const router = useRouter();
  const { status } = useSession();
  const [parts, setParts] = useState<PartSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Part khách vừa bấm — quyết định hộp đăng nhập có mở hay không, cùng khuôn
  // `gated` của trang bộ đề.
  const [gated, setGated] = useState<number | null>(null);

  useEffect(() => {
    apiFetch<PartSummary[]>(API_ROUTES.practiceParts)
      .then(setParts)
      .catch(() => setError("Không tải được danh sách phần."));
  }, []);

  // Chặn ở lần bấm như nút "Xem chi tiết" của khu luyện thi: vẫn là `Link`
  // thật, giữ được chuột giữa và menu chuột phải; phiên còn `loading` thì cứ
  // đi, trang đích tự chặn.
  function gatedHref(part: number): string {
    if (status !== "anonymous") return `/learn/parts/${part}`;
    return "#";
  }

  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Luyện thi"
        title="Luyện theo phần"
        description="Thi thật có bảy phần, mỗi phần một kỹ năng riêng. Luyện rời từng phần, kèm chiến thuật làm phần đó."
      />

      {error && <p className="mb-4 text-small text-alert">{error}</p>}
      {!parts && !error && <SkeletonList rows={5} />}

      <div className="space-y-3">
        {parts &&
          PART_META.map((m) => {
            const summary = parts.find((p) => p.part === m.part);
            return (
              <Panel
                key={m.part}
                className="flex flex-col gap-3 p-4 sm:flex-row sm:flex-wrap sm:items-center sm:gap-4"
              >
                {/* Icon + chữ là một hàng ở MỌI cỡ; chỉ hàng nút mới rơi xuống
                    dòng dưới mobile. `flex-1` nhường cho chữ ở sm trở lên — trên
                    mobile nhường là ép đoạn văn co thành dọc một-từ-một-dòng. */}
                <span className="flex min-w-0 items-center gap-3 sm:flex-1">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded bg-recess text-ink-muted">
                    <m.Icon size={18} strokeWidth={1.75} aria-hidden />
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-baseline gap-2">
                      <span className="font-semibold">
                        Part {m.part} · {m.title}
                      </span>
                      {summary && (
                        <span className="font-data text-small tabular-nums text-ink-faint">
                          {summary.question_count} câu
                        </span>
                      )}
                    </span>
                    <span className="block text-small text-ink-muted">{m.short}</span>
                    <span className="mt-0.5 flex items-center gap-1 text-small text-ink-faint">
                      <Clock size={11} strokeWidth={2} aria-hidden />
                      {m.minutes}
                    </span>
                  </span>
                </span>
                <span className="flex gap-2 max-sm:[&>a]:flex-1">
                  <Link
                    href={gatedHref(m.part)}
                    onClick={(e) => {
                      if (status === "anonymous") {
                        e.preventDefault();
                        setGated(m.part);
                      }
                    }}
                    className="inline-flex items-center justify-center gap-1.5 rounded border border-rule-strong px-3 py-1.5 text-small font-semibold hover:bg-recess"
                  >
                    {status === "anonymous" && <Lock size={13} strokeWidth={2} aria-hidden />}
                    Chiến thuật
                  </Link>
                  <Link
                    href={gatedHref(m.part)}
                    onClick={(e) => {
                      if (status === "anonymous") {
                        e.preventDefault();
                        setGated(m.part);
                      }
                    }}
                    className="inline-flex items-center justify-center gap-1.5 rounded border border-action bg-action px-3 py-1.5 text-small font-semibold text-on-action hover:bg-action-hover"
                  >
                    {status === "anonymous" && <Lock size={13} strokeWidth={2} aria-hidden />}
                    Luyện ngay
                    <ArrowRight size={13} strokeWidth={2} aria-hidden />
                  </Link>
                </span>
              </Panel>
            );
          })}
      </div>

      <p className="mt-6 flex flex-wrap gap-x-4 text-small text-ink-faint">
        <span>
          Ngữ pháp cho Part 5–6 có giáo trình riêng:{" "}
          <Link href="/learn/grammar" className="font-semibold text-ink underline">
            Mô-đun Ngữ pháp
          </Link>
        </span>
        <Link href="/learn/parts/sessions" className="font-semibold text-ink underline">
          Phiên đã luyện
        </Link>
      </p>

      {gated !== null && (
        <LoginModal
          open
          onClose={() => setGated(null)}
          onSuccess={() => router.push(`/learn/parts/${gated}`)}
          next={`/learn/parts/${gated}`}
          title="Đăng nhập để luyện"
          description={
            <>
              Luyện theo part <strong className="font-semibold text-ink">miễn phí</strong>. Đăng
              nhập để lưu tiến độ và có trải nghiệm học tập tốt hơn.
            </>
          }
        />
      )}
    </Page>
  );
}
