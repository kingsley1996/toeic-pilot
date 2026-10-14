import type { ReactNode } from "react";

/*
 * Nền đơn sắc cho khu blog: một lớp đặc che lưới nền của khung.
 *
 * Lưới (`grid-backdrop`, fixed, z -10) là chữ ký của khu học — nhưng chữ bài
 * viết dài nằm trên lưới sẽ rối mắt và giảm tương phản. Lớp này (fixed,
 * z -9) nằm TRÊN lưới, DƯỚI mọi nội dung, phủ kín viewport kể cả vùng
 * footer: không đụng tới shell, không prop drilling, dark mode ăn theo token.
 */
export default function BlogLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <div aria-hidden className="fixed inset-0 bg-ground" style={{ zIndex: -9 }} />
      {children}
    </>
  );
}
