"use client";

import {
  API_ROUTES,
  type AttemptPage,
  type AttemptSummary,
  type LearningStats,
  type ReviewSession,
  type TopicSessionSummary,
  type VocabularyProgress,
} from "@toeic-pilot/shared";
import {
  BookOpen,
  CalendarCheck,
  Clock,
  FileText,
  Flame,
  Headphones,
  Keyboard,
  Layers,
  Play,
  RotateCcw,
  TrendingUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ButtonLink, Page, PageHeader, Panel, PanelLink, Skeleton, Tag, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { clock } from "@/lib/attempt";
import { useRequireSession } from "@/lib/session";

/**
 * Nhà của khu học.
 *
 * Trang này từng ở `/learn`, và trước đó nữa nó là HAI trang — `/dashboard` và
 * `/learn` — mà không trang nào bao trùm trang kia: số "cần ôn hôm nay" chỉ có ở
 * `/dashboard`, lối vào "Gõ lại từ" chỉ có ở `/learn`, và `/dashboard` thì không
 * nằm trong nav nên rời khỏi nó một lần là không quay lại được. Hai trang gộp
 * làm một ở `/learn`, rồi chuyển về `/dashboard` — tên này nói đúng nó là gì
 * (một bảng điều khiển) trong khi `/learn` nghe như một chỗ chứa nội dung, mà
 * chỗ chứa nội dung thật thì nằm ở `/learn/vocabulary`, `/learn/dictation`…
 *
 * `/learn` GIỮ LẠI làm redirect chứ không xoá — nó là địa chỉ đăng nhập đẩy tới
 * suốt nhiều sprint, nên nằm trong lịch sử và bookmark của người đang dùng.
 *
 * Trang này cố tình KHÔNG phải một cái menu. Một con số, một việc, hai cách
 * làm việc đó. Lưới chủ đề cũ đã bỏ vì `/learn/vocabulary` giờ nằm thẳng trên
 * nav và bản thân nó đã có bộ lọc chủ đề ngay đầu trang.
 *
 * Khối từ vựng dựng theo ảnh mẫu ở `planning/improve-ui/`: bên trái là số liệu
 * cộng lối vào ôn tập, bên phải là phân bố trạng thái của cả kho từ. HAI phần
 * của ảnh mẫu cố ý KHÔNG dựng, và lý do khác nhau:
 *
 *   · **Đấu trường từ vựng** — tính năng chưa tồn tại, không phải chuyện giao
 *     diện.
 *   · **Độ chính xác (93%)** — dữ liệu không có. `vocabulary_review_log` có ghi
 *     `grade`, nên tỉ lệ nhớ được là TÍNH ĐƯỢC, nhưng không endpoint nào trả nó
 *     về. Dựng ô đó bằng một con số suy từ thứ khác sẽ cho một tỉ lệ trông như
 *     đo được mà không đo gì cả. Ô thứ tư dùng **chuỗi ngày** — số liệu thật,
 *     đã có sẵn trong `LearningStats`. Muốn có ô độ chính xác thì thêm
 *     `reviews_correct` vào `gather_stats`, một thay đổi backend nhỏ.
 *
 * "Tiếp tục học" thì CÓ dựng, sau khi thêm `GET /vocabulary-topic-sessions`.
 * Nó chỉ hiện khi thật sự có một ván đang dở — không có thì cả khối biến mất,
 * chứ không rơi về "tuyển tập đầu tiên": một nút "Tiếp tục" trỏ vào chỗ chưa
 * từng mở là nói dối, và tệ hơn cả việc không có nút nào.
 */

/**
 * Ván học dở gần nhất, hoặc `null` nếu không có ván nào.
 *
 * Danh sách đã được máy chủ sắp theo `updated_at` giảm dần, nên "gần nhất" là
 * phần tử đầu tiên còn dở — không sắp lại ở client, vì `updated_at` không nằm
 * trong payload (và không nên nằm: client không cần biết mốc thời gian, chỉ cần
 * thứ tự).
 */
function latestUnfinished(sessions: TopicSessionSummary[] | null): TopicSessionSummary | null {
  return sessions?.find((row) => !row.done) ?? null;
}

/**
 * Đường dẫn học tiếp cho một ván.
 *
 * Ưu tiên trang cuốn sách kèm `?topic=` — đó là nơi có cả ba module. Chủ đề
 * chưa xếp vào cuốn sách nào (`collection_item_id` NULL, hợp lệ vì cột đó
 * nullable) rơi về trang danh sách từ của chính chủ đề đó.
 */
function resumeHref(row: TopicSessionSummary): string {
  return row.collection_item_id
    ? `/learn/vocabulary/collection-items/${row.collection_item_id}?topic=${encodeURIComponent(row.topic_slug)}`
    : `/learn/vocabulary/${row.topic_slug}`;
}

/** Một ô số liệu: nhãn nhỏ, số to bằng font data để chữ số thẳng cột. */
function StatTile({
  Icon,
  tint,
  label,
  value,
  unit,
  tone,
}: {
  Icon: LucideIcon;
  /** Nền + màu chữ của huy hiệu icon. */
  tint: string;
  label: string;
  value: number | null;
  unit?: string;
  /** Màu của CON SỐ, chỉ đặt khi con số đó mang tín hiệu (§6.3). */
  tone?: string;
}) {
  return (
    <div className="flex items-start gap-3">
      {/* Huy hiệu VUÔNG bo 4px, không phải tròn như ảnh mẫu: bán kính 4px là
          ngôn ngữ của cả hệ (DESIGN-SYSTEM §6), và thang Tailwind đã bị thay nên
          `rounded-full` ở đây sẽ là ngoại lệ duy nhất trong toàn bộ giao diện. */}
      <span aria-hidden className={cx("grid h-9 w-9 shrink-0 place-items-center rounded", tint)}>
        <Icon size={16} strokeWidth={1.75} />
      </span>
      <span className="min-w-0">
        <span className="block text-label font-semibold uppercase tracking-wide text-ink-faint">
          {label}
        </span>
        {value === null ? (
          <Skeleton className="mt-1.5 h-6 w-12" />
        ) : (
          <span
            className={cx(
              "mt-0.5 block font-data text-[1.4rem] font-semibold leading-tight tabular-nums",
              tone ?? "text-ink",
            )}
          >
            {value}
            {unit && <span className="ml-1 text-small font-normal text-ink-faint">{unit}</span>}
          </span>
        )}
      </span>
    </div>
  );
}

/**
 * Phân bố ba trạng thái của cả kho từ, dưới dạng một thanh xếp chồng.
 *
 * Ba phần cộng lại đúng bằng `total` (`srs.mastery()` phân loại mỗi từ vào đúng
 * một mức), nên thanh này luôn đầy và tỉ lệ đọc được trực tiếp. Ô thứ tư là
 * TỔNG chứ không phải một trạng thái thứ tư — nó đứng riêng sau một đường kẻ,
 * vì gộp vào cùng hàng với ba mức kia sẽ đọc như thể bốn số phải cộng lại.
 */
function StatusBreakdown({ progress }: { progress: VocabularyProgress }) {
  const parts = [
    { label: "Chưa học", count: progress.new, bar: "bg-rule-strong", text: "text-ink-muted" },
    { label: "Đang học", count: progress.learning, bar: "bg-action", text: "text-action-ink" },
    { label: "Đã thuộc", count: progress.mastered, bar: "bg-ok", text: "text-ok" },
  ];

  return (
    <>
      {/* `minWidth` cho phần khác 0: với kho 303 từ, 2 từ đã thuộc là 0.66% —
          làm tròn xuống thành KHÔNG PIXEL NÀO, nên thanh nói "chưa thuộc gì
          cả" trong khi con số ngay dưới nói 2. Ba pixel không đọc được tỉ lệ,
          nhưng nó đúng ở chỗ quan trọng hơn: có hay không có. */}
      <div className="mt-5 flex h-2.5 w-full overflow-hidden rounded bg-recess">
        {parts.map((part) => (
          <div
            key={part.label}
            className={part.bar}
            style={{
              width: `${(part.count / progress.total) * 100}%`,
              minWidth: part.count > 0 ? "3px" : undefined,
            }}
          />
        ))}
      </div>

      <dl className="mt-5 grid grid-cols-3 gap-3">
        {parts.map((part) => (
          <div key={part.label}>
            {/* Số 0 KHÔNG tô màu. Màu ở đây là tín hiệu "có bao nhiêu đó ở mức
                này"; một số 0 màu xanh lá đọc như thể có gì đó đã xong. */}
            <dd
              className={cx(
                "font-data text-[1.4rem] font-semibold tabular-nums",
                part.count > 0 ? part.text : "text-ink-faint",
              )}
            >
              {part.count}
            </dd>
            <dt className="mt-0.5 text-small text-ink-muted">{part.label}</dt>
          </div>
        ))}
      </dl>

      <div className="mt-4 flex items-baseline justify-between border-t border-rule pt-4">
        <span className="text-small text-ink-muted">Tổng số thẻ</span>
        <span className="font-data text-body font-semibold tabular-nums">{progress.total}</span>
      </div>
    </>
  );
}

export default function TodayPage() {
  const { status, user, token, canEdit } = useRequireSession();
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [progress, setProgress] = useState<VocabularyProgress | null>(null);
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [sessions, setSessions] = useState<TopicSessionSummary[] | null>(null);
  // Bài thi đang dở. Đứng trên trang chủ chứ không nằm sau hai cú bấm: đồng hồ
  // của nó chạy ở MÁY CHỦ, nên đóng tab không dừng bài — chỉ làm mất đường quay
  // lại. Không nhắc ở đây thì bài tự hết giờ rồi bị chấm với phần lớn câu bỏ trống.
  const [unfinished, setUnfinished] = useState<AttemptSummary[]>([]);

  useEffect(() => {
    if (!token) return;
    // Một bộ đếm hỏng không được kéo cả trang xuống theo: phần còn lại vẫn dùng
    // được, nên nó xuống cấp thành "không có số" chứ không thành màn lỗi.
    apiFetch<ReviewSession>(API_ROUTES.reviewSession, { token })
      .then(setSession)
      .catch(() => {});
    apiFetch<VocabularyProgress>(API_ROUTES.vocabularyProgress, { token })
      .then(setProgress)
      .catch(() => {});
    apiFetch<AttemptPage>(API_ROUTES.attempts, { token })
      .then((page) => setUnfinished(page.items.filter((row) => row.status === "in_progress")))
      .catch(() => {});
    apiFetch<LearningStats>(API_ROUTES.profileStats, { token })
      .then(setStats)
      .catch(() => {});
    apiFetch<TopicSessionSummary[]>(API_ROUTES.vocabularyTopicSessions, { token })
      .then(setSessions)
      .catch(() => {});
  }, [token]);

  if (status !== "authenticated" || !user) {
    return (
      <Page>
        <Skeleton className="h-9 w-64" />
        <Skeleton className="mt-8 h-52" />
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      </Page>
    );
  }

  const waiting = session ? session.due_count + session.new_count : null;
  // Chưa gặp từ nào ⇒ chế độ gõ không có gì để hỏi.
  const onlyNew = session !== null && session.due_count === 0 && session.new_count > 0;
  const resume = latestUnfinished(sessions);

  return (
    <Page>
      <PageHeader
        eyebrow="Hôm nay"
        /* Tên hiển thị nếu có. Phần đầu email chỉ là phương án chót — người
           đã đặt tên rồi mà vẫn bị chào bằng "profile-e2e-1786347396" thì lời
           chào đó phản tác dụng. */
        title={`Chào ${user.profile.display_name ?? user.email.split("@")[0]}`}
        description="Ôn những từ sắp quên trước, rồi mới gặp từ mới."
        actions={<Tag tone={canEdit ? "action" : "neutral"}>{user.role}</Tag>}
      />

      {unfinished.length > 0 && (
        <Panel className="mb-4 border-warn p-4">
          <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-warn">
            <Clock size={12} strokeWidth={2} aria-hidden />
            Đang làm dở
          </p>
          <div className="mt-2 space-y-1.5">
            {unfinished.slice(0, 3).map((row) => (
              <div key={row.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="font-semibold">{row.test_title}</span>
                <span className="font-data text-small tabular-nums text-ink-muted">
                  {row.answered_count}/{row.question_count} câu
                </span>
                <span className="text-small text-ink-muted">
                  {row.remaining_seconds === null
                    ? "không giới hạn giờ"
                    : row.remaining_seconds === 0
                      ? "đã quá giờ"
                      : `còn ${clock(row.remaining_seconds)}`}
                </span>
                <ButtonLink href={`/learn/attempts/${row.id}`} size="sm" className="ml-auto">
                  Làm tiếp
                </ButtonLink>
              </div>
            ))}
          </div>
          {unfinished.length > 3 && (
            <Link
              href="/learn/attempts"
              className="mt-2 inline-block text-small font-semibold text-action-ink"
            >
              Xem cả {unfinished.length} bài đang dở
            </Link>
          )}
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel className="flex flex-col p-5 sm:p-6">
          <h2 className="text-subtitle">Thống kê học tập</h2>

          <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5">
            <StatTile
              Icon={Layers}
              tint="bg-recess text-ink-muted"
              label="Tổng số thẻ"
              value={progress?.total ?? stats?.vocabulary_total ?? null}
            />
            {/* Số duy nhất ở đây ĐÒI hành động, nên nó là số duy nhất được tô
                màu khi khác 0 — màu là tín hiệu, không phải trang trí (§6.3). */}
            <StatTile
              Icon={TrendingUp}
              tint="bg-warn-tint text-warn"
              label="Đến hạn"
              value={session?.due_count ?? progress?.due ?? null}
              tone={session && session.due_count > 0 ? "text-warn" : undefined}
            />
            <StatTile
              Icon={BookOpen}
              tint="bg-recess text-ink-muted"
              label="Tổng lượt ôn"
              value={stats?.reviews_total ?? null}
            />
            <StatTile
              Icon={Flame}
              tint="bg-ok-tint text-ok"
              label="Chuỗi ngày"
              value={stats?.current_streak ?? null}
              unit="ngày"
              tone={stats && stats.current_streak > 0 ? "text-ok" : undefined}
            />
          </div>

          {/* Người mới có due_count = 0 và new_count = 20: họ KHÔNG "cần ôn", họ
              chưa học gì cả. Gọi 20 từ chưa từng gặp là "cần ôn hôm nay" là dùng
              sai từ ở đúng con số lớn nhất màn hình. */}
          {waiting === 0 ? (
            <div className="mt-6 flex items-start gap-3 border-t border-rule pt-5">
              <CalendarCheck
                size={16}
                strokeWidth={1.75}
                aria-hidden
                className="mt-0.5 shrink-0 text-ink-muted"
              />
              <p className="text-small text-ink-muted">
                Lịch ôn giãn ra theo trí nhớ của bạn, nên hôm nay trống là đúng. Trong lúc chờ, bạn
                có thể duyệt từ vựng hoặc luyện nghe bên dưới.
              </p>
            </div>
          ) : (
            /* Hai CHẾ ĐỘ của cùng một hàng đợi, không phải hai hoạt động — nên
               chúng đứng cạnh nhau ở đây chứ không thành hai mục nav. Nút chính
               chiếm cả chiều ngang như ảnh mẫu: trên một bảng điều khiển đầy số,
               việc cần làm phải to hơn thứ đang mô tả tình hình. */
            <div className="mt-6 flex flex-col gap-2 border-t border-rule pt-5">
              <ButtonLink href="/learn/review" size="lg" className="w-full justify-center">
                <RotateCcw size={16} strokeWidth={2} aria-hidden />
                {onlyNew ? "Học từ mới" : "Ôn tập ngay"}
                {waiting !== null && (
                  <span className="font-data tabular-nums opacity-80">{waiting}</span>
                )}
              </ButtonLink>
              {/* Gõ lại chỉ dùng từ đã gặp qua, nên với người chưa học gì thì
                  nút này dẫn vào một màn hình rỗng. Ẩn đi và nói lý do. */}
              {!onlyNew && (
                <ButtonLink
                  href="/learn/typing"
                  variant="secondary"
                  size="lg"
                  className="w-full justify-center"
                >
                  <Keyboard size={16} strokeWidth={2} aria-hidden />
                  Ôn bằng cách gõ
                </ButtonLink>
              )}
              <p className="mt-1 text-small text-ink-faint">
                {onlyNew
                  ? "Thẻ lật cho bạn xem nghĩa trước — đúng thứ cần cho từ chưa gặp bao giờ. Gõ lại từ sẽ mở ra khi bạn đã làm quen với chúng."
                  : "Thẻ lật hỏi Anh → Việt và bạn tự chấm; gõ lại hỏi Việt → Anh và máy chấm. Hai chế độ dùng chung một danh sách, nên làm bên này thì bên kia vơi đi."}
              </p>
            </div>
          )}

          {/* Ôn tập và học tiếp là HAI việc khác nhau: ở trên là hàng đợi SM-2
              trải khắp mọi chủ đề, ở đây là một chủ đề cụ thể đang dở dang. Khối
              này chỉ hiện khi thật sự có ván dở — không có thì biến mất hẳn,
              chứ không rơi về "tuyển tập đầu tiên". */}
          {resume && (
            <div className="mt-5 rounded border border-rule-strong p-4">
              <p className="text-label font-semibold uppercase tracking-wide text-ink-faint">
                Tiếp tục học
              </p>
              <p className="mt-1.5 font-semibold">
                {resume.collection_item_name ?? resume.topic_name}
              </p>
              <p className="mt-0.5 font-data text-small tabular-nums text-ink-muted">
                {resume.topic_name} · {resume.position}/{resume.total} từ
              </p>
              <ButtonLink href={resumeHref(resume)} className="mt-3 w-full justify-center">
                <Play size={16} strokeWidth={2} aria-hidden />
                Học tiếp
              </ButtonLink>
            </div>
          )}
        </Panel>

        <Panel className="flex flex-col p-5 sm:p-6">
          <h2 className="text-subtitle">Trạng thái từ vựng</h2>

          {progress === null ? (
            <Skeleton className="mt-5 h-40" />
          ) : progress.total === 0 ? (
            <p className="mt-3 text-small text-ink-muted">
              Chưa có từ nào được xuất bản. Khi có, chỗ này hiện bao nhiêu từ bạn chưa học, đang học
              và đã thuộc.
            </p>
          ) : (
            <StatusBreakdown progress={progress} />
          )}

          {/* `mt-auto`: cột trái cao hơn vì có thêm khối "Tiếp tục học", nên nút
              này neo xuống đáy panel thay vì lơ lửng giữa một khoảng trống. */}
          {/* `mt-auto` trên KHUNG chứ không trên nút: cột trái cao hơn vì có thêm
              khối "Tiếp tục học", nên nút này neo xuống đáy panel thay vì lơ lửng
              giữa một khoảng trống. `pt-6` giữ khoảng cách tối thiểu cho trường
              hợp ngược lại, khi nội dung vừa đủ cao và `mt-auto` không còn chỗ. */}
          <div className="mt-auto pt-6">
            <ButtonLink href="/learn/vocabulary" variant="secondary">
              Xem từ vựng
            </ButtonLink>
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Panel className="flex flex-col justify-between p-5">
          <div>
            <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-ink-faint">
              <Headphones size={12} strokeWidth={2} aria-hidden />
              Dictation
            </p>
            <p className="mt-2 text-ink">Nghe một câu, gõ lại, và xem chính xác từ nào bị sót.</p>
          </div>
          <ButtonLink href="/learn/dictation" variant="secondary" className="mt-5 w-fit">
            Vào dictation
          </ButtonLink>
        </Panel>

        <Panel className="flex flex-col justify-between p-5">
          <div>
            <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-ink-faint">
              <FileText size={12} strokeWidth={2} aria-hidden />
              Luyện thi
            </p>
            <p className="mt-2 text-ink">Làm một đề đầy đủ, tính giờ, rồi xem lại từng câu.</p>
          </div>
          <ButtonLink href="/learn/tests" variant="secondary" className="mt-5 w-fit">
            Xem bộ đề
          </ButtonLink>
        </Panel>
      </div>

      {/* Chỉ dựng cho editor và admin. Học viên không được chỉ vào một cánh cửa
          họ không mở được. */}
      {canEdit && (
        <div className="mt-4">
          <PanelLink href="/admin">
            <h2 className="text-subtitle">Quản lý nội dung</h2>
            <p className="mt-1 text-small text-ink-muted">Nhập từ vựng, câu nghe, và xuất bản.</p>
          </PanelLink>
        </div>
      )}
    </Page>
  );
}
