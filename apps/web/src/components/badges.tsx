"use client";

import { API_ROUTES, type BadgePublic, type BadgesPublic } from "@toeic-pilot/shared";
import {
  Award,
  BookOpen,
  Flame,
  Footprints,
  GraduationCap,
  Headphones,
  Library,
  Medal,
  Sparkles,
  Star,
  Target,
  Trophy,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Panel, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";

/**
 * Huy hiệu: bảng chữ và biểu tượng, cộng dòng thông báo trên trang chủ.
 *
 * **Huy hiệu là DỮ LIỆU.** Nhãn, gợi ý, ngưỡng và cả danh sách đều đến từ
 * `badge_rule`, nơi admin sửa được. Frontend chỉ giữ đúng một bảng tra: biểu
 * tượng, vì nó là hình chứ không phải chữ.
 *
 * Đánh đổi có chủ ý so với bản đầu: `code` từng là union đóng nên `tsc` bắt được
 * huy hiệu thiếu nhãn. Giờ không còn, bù lại thêm một huy hiệu không cần triển
 * khai lại. Cái được giữ là `icon` — vẫn union, vẫn lỗi biên dịch nếu thiếu.
 */

export type BadgeIcon = BadgePublic["icon"];

/**
 * Hình của mỗi biểu tượng. Đây là thứ DUY NHẤT frontend còn quyết định về huy
 * hiệu — nhãn, gợi ý, ngưỡng và cả danh sách huy hiệu đều là dữ liệu admin sửa.
 *
 * `Record<BadgeIcon, …>` với `BadgeIcon` là union từ OpenAPI: thêm một biểu
 * tượng ở backend mà quên khai ở đây là lỗi `tsc`. Đó là lý do `icon` vẫn là tập
 * đóng trong khi `code` thì không — một huy hiệu không có hình là thứ chỉ lộ ra
 * khi ai đó mở trang.
 */
const ICONS: Record<BadgeIcon, LucideIcon> = {
  footprints: Footprints,
  book: BookOpen,
  library: Library,
  graduation: GraduationCap,
  headphones: Headphones,
  target: Target,
  medal: Medal,
  trophy: Trophy,
  flame: Flame,
  star: Star,
  sparkles: Sparkles,
  award: Award,
};

/** Một ô huy hiệu. Chưa mở thì xám và in tiến độ; mở rồi thì có màu. */
export function BadgeTile({ badge, isNew }: { badge: BadgePublic; isNew: boolean }) {
  const Icon = ICONS[badge.icon];
  return (
    <li
      className={cx(
        "flex items-start gap-3 rounded border p-4",
        badge.earned ? "border-rule-strong" : "border-rule",
      )}
    >
      {/* Có tranh thì tranh thắng biểu tượng. Huy hiệu CHƯA MỞ vẫn dùng tranh
          nhưng bị làm xám (`grayscale opacity-40`) chứ không rơi về icon: đổi
          hẳn hình khi mở được sẽ khiến người ta không nhận ra thứ mình vừa nhận
          chính là thứ đã nhìn thấy suốt. */}
      {badge.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={badge.image_url}
          alt=""
          aria-hidden
          className={cx(
            "h-10 w-10 shrink-0 rounded object-contain",
            !badge.earned && "opacity-40 grayscale",
          )}
        />
      ) : (
        <span
          aria-hidden
          className={cx(
            "grid h-10 w-10 shrink-0 place-items-center rounded",
            badge.earned ? "bg-action-tint text-action-ink" : "bg-recess text-ink-faint",
          )}
        >
          <Icon size={18} strokeWidth={1.75} />
        </span>
      )}
      <span className="min-w-0">
        <span className="flex flex-wrap items-center gap-2">
          <span className={cx("font-semibold", !badge.earned && "text-ink-muted")}>
            {badge.label}
          </span>
          {/* "MỚI" chỉ nói về việc ĐÃ XEM hay chưa, nên nó biến mất ở lần mở
              trang sau — không phải một huy hiệu hạng khác. */}
          {isNew && (
            <span className="rounded border border-transparent bg-ok-tint px-1.5 py-0.5 text-label font-semibold uppercase text-ok">
              Mới
            </span>
          )}
        </span>
        <span className="mt-0.5 block text-small text-ink-muted">{badge.hint}</span>
        {/* Đã mở rồi thì KHÔNG in "300/300": con số tiến độ tồn tại để nói còn
            bao xa, và với thứ đã đạt thì nó không còn nói gì. */}
        {!badge.earned && (
          <span className="mt-1.5 block font-data text-small tabular-nums text-ink-faint">
            {badge.progress}/{badge.target}
          </span>
        )}
      </span>
    </li>
  );
}

/**
 * Một dòng trên trang chủ khi có huy hiệu vừa mở mà chưa xem.
 *
 * MỘT thông báo cho tất cả, không phải một dòng mỗi cái: tài khoản có sẵn lịch
 * sử mở một loạt cùng lúc ở lần đọc đầu tiên sau khi tính năng ra mắt — mười
 * thông báo liên tiếp đọc như hệ thống hỏng, chứ không như một phần thưởng.
 *
 * Không tự gọi `POST .../seen`: chấm đỏ tắt khi người dùng MỞ TRANG huy hiệu,
 * chứ không khi họ lướt qua trang chủ. Tắt ở đây nghĩa là ai không kịp đọc dòng
 * này sẽ không bao giờ biết mình vừa mở được gì.
 */
export function BadgeNotice({ token }: { token: string | null }) {
  const [data, setData] = useState<BadgesPublic | null>(null);

  useEffect(() => {
    if (!token) return;
    let alive = true;
    apiFetch<BadgesPublic>(API_ROUTES.badges, { token })
      .then((value) => {
        if (alive) setData(value);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token]);

  if (!data || data.unseen_count === 0) return null;

  return (
    <Panel className="mb-4 border-ok p-4">
      <Link href="/profile/badges" className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="flex items-center gap-1.5 text-label font-semibold uppercase text-ok">
          <Trophy size={12} strokeWidth={2} aria-hidden />
          Huy hiệu mới
        </span>
        <span className="text-ink">
          Bạn vừa mở {data.unseen_count} huy hiệu. Xem có gì trong đó.
        </span>
        <span className="ml-auto text-small font-semibold text-action-ink">Xem huy hiệu</span>
      </Link>
    </Panel>
  );
}
