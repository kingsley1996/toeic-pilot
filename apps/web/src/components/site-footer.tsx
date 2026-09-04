"use client";

import Link from "next/link";

import { BrandMark } from "@/components/brand";
import { type NavItem } from "@/components/nav";
import { landing } from "@/content/landing";
import { useSession } from "@/lib/session";

/**
 * Chân trang của ba trang NGOÀI ứng dụng — `/`, `/login`, `/register`.
 *
 * Nó không dùng bảng màu riêng của trang giới thiệu (`.l-*`). Hai lý do: các
 * biến ấy chỉ sống bên trong `<div className="landing">` của `app/page.tsx`, nên
 * ở đây chúng không tồn tại; và chúng vốn chỉ là bí danh trỏ vào token của design
 * system, nên dùng thẳng token cho ra đúng màu ấy mà chạy được ở cả ba trang.
 *
 * **Ba mục nội dung nhận qua props, không tự khai.** Chúng là chính
 * `CONTENT_LINKS` mà thanh trên đang dùng. Chép một bản thứ hai vào đây thì đổi
 * tên một mục ở nav xong chân trang vẫn gọi nó bằng tên cũ — hai chỗ nói hai
 * điều về cùng một trang, và không có gì báo.
 */
export function SiteFooter({ links }: { links: readonly NavItem[] }) {
  const { status } = useSession();

  /*
   * Ba trạng thái, không hai — cùng cái bẫy `session.status` đã ghi lại.
   *
   * Lúc `loading` thì KHÔNG dựng cột tài khoản. Đoán sai ở đây nghĩa là người
   * đã đăng nhập nhìn thấy "Đăng nhập / Tạo tài khoản" nháy lên rồi biến mất ở
   * mỗi lần tải trang — đúng cái lỗi mà header cũ mắc phải.
   */
  const account =
    status === "authenticated"
      ? [{ href: "/dashboard", label: landing.footer.dashboard }]
      : status === "anonymous"
        ? [
            { href: "/login", label: landing.footer.signIn },
            { href: "/register", label: landing.footer.signUp },
          ]
        : [];

  return (
    <footer className="border-t border-rule">
      {/* Cột link ÔM lấy chữ (`auto`) và khối thương hiệu ăn hết phần dư
            (`1fr`). Chia đều ba cột cho ra hai cột rộng 290px chứa ba chữ, và
            khoảng trống ấy đọc ra là ba khối rời nhau chứ không phải một chân
            trang. */}
      <div className="mx-auto grid max-w-5xl gap-8 px-4 py-12 sm:grid-cols-[1fr_auto_auto] sm:gap-16">
        <div>
          <div className="flex items-center gap-2">
            <BrandMark />
            <span className="font-semibold">TOEIC Pilot</span>
          </div>
          <p className="mt-3 max-w-xs text-small leading-relaxed text-ink-muted">
            {landing.footer.tagline}
          </p>
          <p className="mt-3 text-small font-semibold text-action-ink">{landing.footer.free}</p>
        </div>

        <FooterColumn title={landing.footer.learnLabel} items={links} />
        {/* Cột rỗng lúc phiên chưa phân giải: chừa chỗ chứ không dựng gì, để
            phần còn lại của chân trang không nhảy khi nó hiện ra. */}
        <FooterColumn title={landing.footer.accountLabel} items={account} />
      </div>

      <div className="border-t border-rule">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-5 text-small text-ink-faint">
          {/* Năm tính lúc DỰNG, không ghi cứng: một con số ghi cứng thành sai
              vào đúng ngày 1 tháng 1, và đó là ngày không ai đọc chân trang. */}
          <span>© {new Date().getFullYear()} TOEIC Pilot</span>
          <span>{landing.footer.made}</span>
        </div>
      </div>
    </footer>
  );
}

function FooterColumn({
  title,
  items,
}: {
  title: string;
  items: readonly { href: string; label: string }[];
}) {
  return (
    <div>
      <div className="text-label font-semibold uppercase tracking-wide text-ink-faint">{title}</div>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="text-small text-ink-muted underline-offset-4 hover:text-ink hover:underline"
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
