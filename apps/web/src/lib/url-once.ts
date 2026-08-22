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
 * Nên chụp lại đúng một lần vào biến ở phạm vi module: nó sống qua mọi lần
 * render, và bản chụp là thứ ta muốn — nội dung URL *lúc hạ cánh*, không phải
 * lúc này.
 */

let capturedSearch: string | null = null;
let capturedHash: string | null = null;

function readSearch(): string {
  if (capturedSearch === null) {
    capturedSearch = typeof window === "undefined" ? "" : window.location.search;
  }
  return capturedSearch;
}

function readHash(): string {
  if (capturedHash === null) {
    capturedHash = typeof window === "undefined" ? "" : window.location.hash;
  }
  return capturedHash;
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
