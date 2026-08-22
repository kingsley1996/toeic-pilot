import type { ReactNode } from "react";

/**
 * Khối biểu mẫu của hai trang đăng nhập và đăng ký.
 *
 * KHÔNG có chữ mô tả. Một trang đăng nhập không phải chỗ giới thiệu sản phẩm:
 * người mở nó đã quyết định rồi, họ chỉ đang muốn vào — và mỗi câu thêm vào là
 * một thứ nữa phải đọc lướt qua trước khi tới được ô nhập. Phần "nhìn" do linh
 * vật ở `app/(auth)/layout.tsx` đảm nhiệm.
 *
 * Ba ràng buộc của DESIGN-SYSTEM chi phối mọi thứ ở đây và cả ba đều hỏng lặng
 * lẽ nếu bỏ qua: KHÔNG đổ bóng (§6.3), MỘT bán kính 4px (§6.2), và ranh giới
 * component dùng `rule-strong` chứ không `rule` (§11).
 */
export function AuthLayout({
  formLabel,
  children,
}: {
  /** Nhãn mono trên đầu khối. Nói đúng việc sắp làm — đây là chữ duy nhất ngoài biểu mẫu. */
  formLabel: string;
  children: ReactNode;
}) {
  return (
    /* `lg:max-w-none` để khối này lấp đầy cột: ở `lg` nó nằm sát khối nền của
       linh vật, và một hộp hẹp căn giữa trong cột sẽ để lại đúng cái khe mà bố
       cục vừa bỏ đi. Dưới `lg` vẫn giới hạn bề ngang, vì một biểu mẫu rộng cả
       màn hình thì mắt phải quét ngang quá xa giữa nhãn và ô nhập. */
    <div className="mx-auto w-full max-w-md rounded border border-rule-strong bg-panel lg:max-w-none">
      <p className="flex items-center justify-between border-b border-rule px-5 py-3 font-data text-label uppercase tracking-[0.14em] text-ink-faint sm:px-6">
        {formLabel}
        <span aria-hidden className="h-1.5 w-1.5 rounded bg-action" />
      </p>
      <div className="p-5 sm:p-6">{children}</div>
    </div>
  );
}
