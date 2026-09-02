"use client";

import { useSyncExternalStore } from "react";

/**
 * Đọc MỘT LẦN phần query hoặc fragment của URL lúc trang được dựng ở trình duyệt.
 *
 * Ba ràng buộc gặp nhau ở đây, và cách làm hiển nhiên vi phạm cả ba:
 *
 *   · **Máy chủ không có `window`**, nên đọc thẳng trong thân component sẽ nổ
 *     lúc render phía máy chủ.
 *   · **`setState` trong effect bị cấm** (`react-hooks/set-state-in-effect`) —
 *     nó xếp tầng render và là luật đã có sẵn của dự án này.
 *   · **Giá trị phải ỔN ĐỊNH.** Cả hai chỗ dùng đều xoá tham số khỏi thanh địa
 *     chỉ ngay sau khi đọc, nên một hàm đọc thẳng `window.location` sẽ trả về
 *     giá trị khác ở lần render kế — `useSyncExternalStore` phát hiện ra và
 *     dựng lại, có thể thành vòng lặp.
 *
 * Nên chụp lại một lần **cho mỗi đường dẫn**: bản chụp sống qua mọi lần render
 * của trang đó, và đó chính là thứ ta muốn — URL *lúc hạ cánh*, không phải lúc
 * này. Khoá theo pathname chứ không chụp đúng một lần cho cả phiên, vì đi từ
 * `/login` sang `/register?next=…` bằng `next/link` không tải lại trang: một
 * bản chụp duy nhất sẽ trả về query của trang trước và `next` lặng lẽ rơi về
 * mặc định.
 */

type Captured = { path: string; search: string; hash: string };

const EMPTY: Captured = { path: "", search: "", hash: "" };

let captured: Captured | null = null;

function capture(): Captured {
  if (typeof window === "undefined") return EMPTY;
  if (!captured || captured.path !== window.location.pathname) {
    captured = {
      path: window.location.pathname,
      search: window.location.search,
      hash: window.location.hash,
    };
  }
  return captured;
}

function readSearch(): string {
  return capture().search;
}

function readHash(): string {
  return capture().hash;
}

/** Không đăng ký gì: URL lúc hạ cánh không đổi nữa theo nghĩa ta quan tâm. */
function subscribe(): () => void {
  return () => {};
}

const serverSnapshot = () => "";

export function useLandingSearch(): URLSearchParams {
  return new URLSearchParams(useSyncExternalStore(subscribe, readSearch, serverSnapshot));
}

export function useLandingHash(): URLSearchParams {
  return new URLSearchParams(
    useSyncExternalStore(subscribe, readHash, serverSnapshot).replace(/^#/, ""),
  );
}

/** Xoá query/fragment khỏi thanh địa chỉ mà không thêm một mục lịch sử mới. */
export function stripUrlParams(): void {
  if (typeof window === "undefined") return;
  window.history.replaceState(null, "", window.location.pathname);
}

/**
 * Chỉ nhận đường dẫn nội bộ làm chỗ quay về sau khi đăng nhập.
 *
 * `next` đến từ URL, nên một URL tuyệt đối ở đây là một open redirect dựng sẵn:
 * gửi link `/login?next=https://…` là mượn được trang đăng nhập của mình để đẩy
 * người dùng đi đâu cũng được. Cùng luật với `safe_next` ở `oauth.py` — kể cả
 * `//host`, thứ trình duyệt hiểu là giao thức tương đối.
 */
export function safeNextPath(value: string | null, fallback = "/dashboard"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return fallback;
  return value;
}
