"use client";

import { API_ROUTES, type ReviewSession, type VocabularyProgress } from "@toeic-pilot/shared";
import { BookOpen, CalendarCheck, Headphones, Keyboard, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

import {
  ButtonLink,
  Meter,
  Page,
  PageHeader,
  Panel,
  PanelLink,
  Skeleton,
  Tag,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Nhà của khu học — gộp từ `/dashboard` và `/learn` cũ.
 *
 * Trước đây có HAI trang hub và không trang nào bao trùm trang kia: số "cần ôn
 * hôm nay" chỉ có ở `/dashboard`, lối vào "Gõ lại từ" chỉ có ở `/learn`, và
 * `/dashboard` thì không nằm trong nav nên rời khỏi nó một lần là không quay
 * lại được. Kết quả là con số đáng lẽ điều khiển hành vi mỗi ngày lại nằm ở chỗ
 * khó tới nhất.
 *
 * Trang này cố tình KHÔNG phải một cái menu. Một con số, một việc, hai cách
 * làm việc đó. Lưới chủ đề cũ đã bỏ vì `/learn/vocabulary` giờ nằm thẳng trên
 * nav và bản thân nó đã có bộ lọc chủ đề ngay đầu trang.
 */
export default function TodayPage() {
  const { status, user, token, canEdit } = useRequireSession();
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [progress, setProgress] = useState<VocabularyProgress | null>(null);

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

  return (
    <Page>
      <PageHeader
        eyebrow="Hôm nay"
        title={`Chào ${user.email.split("@")[0]}`}
        description="Ôn những từ sắp quên trước, rồi mới gặp từ mới."
        actions={<Tag tone={canEdit ? "action" : "neutral"}>{user.role}</Tag>}
      />

      <Panel className="p-5 sm:p-6">
        <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-ink-faint">
          <RotateCcw size={12} strokeWidth={2} aria-hidden />
          {session && session.due_count === 0 && session.new_count > 0
            ? "Từ mới đang chờ"
            : "Cần ôn hôm nay"}
        </p>

        {waiting === null ? (
          <Skeleton className="mt-2 h-12 w-24" />
        ) : (
          // Font data với chữ số thẳng cột, nên con số không nhảy khi cập nhật.
          <p className="mt-1.5 font-data text-readout leading-none text-ink">{waiting}</p>
        )}

        {session && (
          <p className="mt-3 font-data text-small text-ink-muted">
            {session.due_count} đến hạn · {session.new_count} từ mới
          </p>
        )}

        {/* Người mới có due_count = 0 và new_count = 20: họ KHÔNG "cần ôn", họ
            chưa học gì cả. Gọi 20 từ chưa từng gặp là "cần ôn hôm nay" là dùng
            sai từ ở đúng con số lớn nhất màn hình. */}
        {waiting === 0 ? (
          <div className="mt-5 flex items-start gap-3 border-t border-rule pt-5">
            <CalendarCheck
              size={16}
              strokeWidth={1.75}
              aria-hidden
              className="mt-0.5 shrink-0 text-ink-muted"
            />
            <p className="text-small text-ink-muted">
              Lịch ôn giãn ra theo trí nhớ của bạn, nên hôm nay trống là đúng. Trong lúc chờ, bạn có
              thể duyệt từ vựng hoặc luyện nghe bên dưới.
            </p>
          </div>
        ) : (
          <>
            {/* Hai CHẾ ĐỘ của cùng một hàng đợi, không phải hai hoạt động —
                nên chúng đứng cạnh nhau ở đây chứ không thành hai mục nav. */}
            <div className="mt-5 flex flex-wrap gap-2">
              <ButtonLink href="/learn/review" size="lg">
                <RotateCcw size={16} strokeWidth={2} aria-hidden />
                {onlyNew ? "Học từ mới" : "Ôn bằng thẻ lật"}
              </ButtonLink>
              {/* Gõ lại chỉ dùng từ đã gặp qua, nên với người chưa học gì thì
                  nút này dẫn vào một màn hình rỗng. Ẩn đi và nói lý do. */}
              {!onlyNew && (
                <ButtonLink href="/learn/typing" variant="secondary" size="lg">
                  <Keyboard size={16} strokeWidth={2} aria-hidden />
                  Ôn bằng cách gõ
                </ButtonLink>
              )}
            </div>
            <p className="mt-2.5 text-small text-ink-faint">
              {onlyNew
                ? "Thẻ lật cho bạn xem nghĩa trước — đúng thứ cần cho từ chưa gặp bao giờ. Gõ lại từ sẽ mở ra khi bạn đã làm quen với chúng."
                : "Thẻ lật hỏi Anh → Việt và bạn tự chấm; gõ lại hỏi Việt → Anh và máy chấm. Hai chế độ dùng chung một danh sách, nên làm bên này thì bên kia vơi đi."}
            </p>
          </>
        )}
      </Panel>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Panel className="flex flex-col justify-between p-5">
          <div>
            <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-ink-faint">
              <BookOpen size={12} strokeWidth={2} aria-hidden />
              Từ vựng
            </p>
            {progress && progress.total > 0 ? (
              <div className="mt-3">
                <Meter
                  value={progress.mastered}
                  max={progress.total}
                  label="Đã thuộc"
                  ticks={Math.min(progress.total, 8)}
                />
                <p className="mt-2 text-small text-ink-muted">
                  {progress.learning} đang học · {progress.new} chưa học
                </p>
              </div>
            ) : (
              <p className="mt-2 text-small text-ink-muted">
                Duyệt theo chủ đề, nghe phát âm bốn giọng.
              </p>
            )}
          </div>
          <ButtonLink href="/learn/vocabulary" variant="secondary" className="mt-5 w-fit">
            Xem từ vựng
          </ButtonLink>
        </Panel>

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
