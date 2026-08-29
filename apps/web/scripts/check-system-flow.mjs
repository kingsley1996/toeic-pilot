/**
 * Mọi cạnh của sơ đồ /admin/system phải nối vào một handle CÓ THẬT.
 *
 * React Flow chỉ vẽ một cạnh khi tìm được cả handle nguồn lẫn handle đích của
 * nó; không tìm thấy thì nó bỏ qua, im lặng, không cảnh báo. Bản đầu tiên khai
 * cả bốn handle là `type="source"`, nên không cạnh nào nối được và sơ đồ thành
 * chín cái ô rời — trong khi tsc, eslint và prettier đều xanh.
 */
import { readFileSync } from "node:fs";

const flow = readFileSync(new URL("../src/components/system-flow.tsx", import.meta.url), "utf8");
const page = readFileSync(new URL("../src/app/admin/system/page.tsx", import.meta.url), "utf8");

const sides = [...flow.matchAll(/\["(left|right|top|bottom)",\s*Position\.\w+\]/g)].map(
  (m) => m[1],
);
const sources = new Set();
const targets = new Set();
for (const side of sides) {
  if (flow.includes("`s-${id}`")) sources.add(`s-${side}`);
  if (flow.includes("`t-${id}`")) targets.add(`t-${side}`);
}

const problems = [];
if (sides.length === 0) problems.push("không tìm thấy khai báo cạnh nào trong system-flow.tsx");
if (targets.size === 0) problems.push("node KHÔNG có handle target nào — mọi cạnh sẽ bị bỏ vẽ");

const used = { source: new Set(), target: new Set() };
for (const [, kind, id] of page.matchAll(/(source|target)Handle:\s*"([^"]+)"/g)) {
  used[kind].add(id);
}
if (used.source.size === 0) problems.push("page.tsx không khai sourceHandle nào");
for (const id of used.source) {
  if (!sources.has(id)) problems.push(`sourceHandle "${id}" không được node dựng ra`);
}
for (const id of used.target) {
  if (!targets.has(id)) problems.push(`targetHandle "${id}" không được node dựng ra`);
}

// Mỗi cạnh phải khai đủ cả hai đầu; thiếu một đầu thì React Flow tự chọn và
// đường đi sẽ khác hẳn ý định, một cách khó thấy.
const edgeCalls = [...page.matchAll(/edge\(\s*"e-[^"]+"[\s\S]*?\n\s*\}\)|edge\("e-[^)]*\)/g)];
for (const [call] of edgeCalls) {
  const hasSource = /sourceHandle:/.test(call);
  const hasTarget = /targetHandle:/.test(call);
  if (!hasSource || !hasTarget) {
    const id = call.match(/"(e-[^"]+)"/)?.[1] ?? "?";
    problems.push(`cạnh ${id} thiếu ${!hasSource ? "sourceHandle" : "targetHandle"}`);
  }
}

if (problems.length) {
  console.error("check-system-flow: sơ đồ sẽ mất cạnh\n");
  for (const p of problems) console.error("  · " + p);
  process.exit(1);
}
console.log(
  `check-system-flow: ok — ${sources.size} cổng nguồn, ${targets.size} cổng đích, ` +
    `${used.source.size + used.target.size} tham chiếu đều khớp`,
);
