/**
 * Mục điều hướng nào đang mở — luật thuần, tách khỏi `nav.tsx`.
 *
 * Ở một tệp `.ts` riêng vì đây là chỗ đã sai hai lần và cả hai lần đều IM LẶNG:
 * trang vẫn đúng, chỉ có thanh điều hướng tắt đèn hoặc sáng nhầm chỗ, và không
 * ai gọi đó là lỗi — họ chỉ mất dấu mình đang ở đâu. `tsc` và eslint không thấy
 * gì, còn e2e thì không với tới được khu quản trị (tạo tài khoản admin không
 * làm được qua `register`). Ở đây thì
 * `node --experimental-strip-types scripts/check-nav-active.mjs` chạy thẳng.
 */

export type NavTarget = {
  href: string;
  /** Đường dẫn khác cũng thuộc về mục này, khi chúng KHÔNG nằm dưới `href`. */
  covers?: string[];
  children?: NavTarget[];
};

/**
 * Mục nào đang mở, theo tiền tố — khớp SÂU NHẤT thắng, để `/learn/vocabulary`
 * không đồng thời làm sáng một mục cha.
 *
 * So khớp trên `href` cùng với `covers`, nhưng trả về `href`: `covers` chỉ nói
 * "đường dẫn này thuộc về mục kia", không phải một đích đến thứ hai.
 */
export function activeHref(items: NavTarget[], pathname: string): string | undefined {
  const matches = items.flatMap((item) =>
    [item.href, ...(item.covers ?? [])]
      .filter((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
      .map((prefix) => ({ href: item.href, depth: prefix.length })),
  );
  return matches.sort((a, b) => b.depth - a.depth)[0]?.href;
}

/**
 * Nhánh con của một mục có đang mở không.
 *
 * Hỏi theo QUAN HỆ CHA-CON, không theo tiền tố đường dẫn. Bản trước hỏi
 * `active === item.href || active.startsWith(item.href + "/")`, và nó đúng chừng
 * nào mọi mục con còn nằm dưới đường dẫn của cha. `Ruby rates` thì không:
 * `/admin/ruby` là con của `/admin/pet` vì hai trang ấy là hai nửa của một quyết
 * định vận hành, chứ không vì đường dẫn. Hệ quả là đứng ở `/admin/ruby` thì cả
 * nhánh Petland biến mất và không mục nào sáng — người dùng đang ở một trang mà
 * thanh bên nói rằng họ không ở đâu cả.
 *
 * Cùng loại lỗi mà `NavItem.covers` sinh ra để vá ở tầng mục gốc, và cùng cách
 * chữa: đừng suy quan hệ từ chuỗi đường dẫn khi đã có quan hệ thật trong dữ liệu.
 */
export function isBranchOpen(item: NavTarget, active: string | undefined): boolean {
  if (active === undefined) return false;
  if (item.href === active) return true;
  return (item.children ?? []).some((child) => child.href === active);
}
