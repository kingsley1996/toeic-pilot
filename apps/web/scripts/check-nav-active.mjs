/**
 * Kiểm luật "mục nào đang mở" trên đúng những đường dẫn thật của ứng dụng —
 * chạy bằng `node --experimental-strip-types apps/web/scripts/check-nav-active.mjs`.
 *
 * Ở đây vì đây là chỗ đã sai HAI lần và cả hai lần đều im lặng: trang vẫn đúng,
 * chỉ thanh điều hướng tắt đèn hoặc sáng nhầm chỗ, và không ai gọi đó là lỗi —
 * họ chỉ mất dấu mình đang ở đâu. `tsc` và eslint không thấy gì, còn e2e thì
 * không với tới khu quản trị được (`register` cố ý không cấp vai trò nào).
 */

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const base = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "components");
const { activeHref, isBranchOpen } = await import(join(base, "nav-active.ts"));

let bad = 0;
const fail = (msg) => {
  bad += 1;
  console.log("SAI:", msg);
};

/** Bộ mục quản trị, chép đúng hình dạng thật (nhãn và icon không liên quan). */
const ADMIN = [
  { href: "/admin" },
  { href: "/admin/vocabulary", children: [{ href: "/admin/vocabulary/tree" }] },
  { href: "/admin/dictation", children: [{ href: "/admin/dictation/tree" }] },
  { href: "/admin/tests" },
  { href: "/admin/appearance" },
  { href: "/admin/progression", children: [{ href: "/admin/progression/preview" }] },
  {
    href: "/admin/pet",
    children: [{ href: "/admin/petland" }, { href: "/admin/ruby" }],
  },
  {
    href: "/admin/ai",
    children: [{ href: "/admin/ai/skill-tags" }, { href: "/admin/ai/providers" }],
  },
];

/** Bộ mục khu học, gồm cả `covers` — món nợ cũ đã phải vá một lần. */
const LEARN = [
  { href: "/dashboard", covers: ["/learn/review", "/learn/typing", "/learn/attempts"] },
  { href: "/learn/vocabulary" },
  { href: "/learn/dictation" },
  { href: "/learn/tests" },
];

const flatten = (items) => items.flatMap((i) => [i, ...(i.children ?? [])]);

/** Mọi trang thật của khu quản trị, và mục đáng lẽ phải sáng ở đó. */
const CASES = [
  ["/admin", "/admin"],
  ["/admin/vocabulary", "/admin/vocabulary"],
  ["/admin/vocabulary/tree", "/admin/vocabulary/tree"],
  ["/admin/dictation", "/admin/dictation"],
  ["/admin/dictation/tree", "/admin/dictation/tree"],
  ["/admin/tests", "/admin/tests"],
  ["/admin/tests/toeic-2024-form-a", "/admin/tests"],
  ["/admin/appearance", "/admin/appearance"],
  ["/admin/progression", "/admin/progression"],
  ["/admin/progression/preview", "/admin/progression/preview"],
  ["/admin/pet", "/admin/pet"],
  // Hai ca này là lý do tệp kiểm này tồn tại: đường dẫn của chúng KHÔNG nằm
  // dưới `/admin/pet`, nên mọi luật suy từ tiền tố đều trượt.
  ["/admin/petland", "/admin/petland"],
  ["/admin/ruby", "/admin/ruby"],
  ["/admin/ai", "/admin/ai"],
  ["/admin/ai/skill-tags", "/admin/ai/skill-tags"],
  ["/admin/ai/providers", "/admin/ai/providers"],
];

for (const [pathname, want] of CASES) {
  const got = activeHref(flatten(ADMIN), pathname);
  if (got !== want) fail(`${pathname}: mục sáng là ${got}, đáng lẽ ${want}`);
}
console.log(`mục sáng: ${CASES.length} trang quản trị đều đúng`);

// Nhánh con phải MỞ ở trang cha và ở mọi trang con của nó, không mở ở chỗ khác.
for (const [pathname] of CASES) {
  const active = activeHref(flatten(ADMIN), pathname);
  for (const item of ADMIN) {
    const belongs = item.href === active || (item.children ?? []).some((c) => c.href === active);
    const open = isBranchOpen(item, active);
    if (open !== belongs) {
      fail(
        `${pathname}: nhánh ${item.href} ${open ? "mở" : "đóng"}, đáng lẽ ${belongs ? "mở" : "đóng"}`,
      );
    }
  }
}
console.log("nhánh con: mở đúng ở trang cha và mọi trang con, không mở ở đâu khác");

// Khu học: `covers` phải kéo được ba chế độ không nằm dưới `/dashboard`.
for (const [pathname, want] of [
  ["/dashboard", "/dashboard"],
  ["/learn/review", "/dashboard"],
  ["/learn/typing", "/dashboard"],
  ["/learn/attempts", "/dashboard"],
  ["/learn/vocabulary", "/learn/vocabulary"],
  ["/learn/vocabulary/office-1", "/learn/vocabulary"],
  ["/learn/dictation", "/learn/dictation"],
]) {
  const got = activeHref(LEARN, pathname);
  if (got !== want) fail(`${pathname}: mục sáng là ${got}, đáng lẽ ${want}`);
}
console.log("khu học: `covers` kéo đúng ba chế độ mở ra từ trang chủ");

console.log(bad === 0 ? "\nTẤT CẢ ĐỀU ĐÚNG" : `\n${bad} chỗ SAI`);
process.exit(bad === 0 ? 0 : 1);
