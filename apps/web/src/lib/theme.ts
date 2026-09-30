/**
 * Lựa chọn theme của người dùng, và chỗ nó được lưu.
 *
 * Ba trạng thái chứ không phải hai, và mặc định là `dark` (người dùng
 * 2026-09-30), KHÔNG phải `system`: khách mới chưa chọn gì vào là thấy nền
 * tối ngay. `system` vẫn giữ cho ai muốn đi theo hệ điều hành — vì thế nó được
 * ghi EXPLICIT vào localStorage, chứ không còn là "không có khoá" như trước:
 * "không có khoá" giờ nghĩa là chưa chọn, tức là dark.
 *
 * Cùng khuôn với `auth-storage.ts` và vì cùng một lý do: sự kiện `storage` của
 * trình duyệt chỉ bắn ở CÁC TAB KHÁC, nên ghi rồi mong React tự nhận ra sẽ âm
 * thầm không bao giờ chạy trong chính tab vừa ghi.
 */
export type ThemePref = "system" | "light" | "dark";

const KEY = "theme";
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

export function subscribeToTheme(onChange: () => void): () => void {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function getThemePref(): ThemePref {
  if (typeof window === "undefined") return "system";
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
    // Không có khoá = chưa chọn bao giờ = dark (mặc định dự án).
    return "dark";
  } catch {
    // Safari ở chế độ riêng tư ném lỗi khi đọc localStorage.
    return "dark";
  }
}

/** Server không có localStorage, nên nó chỉ báo được "chưa biết". */
export function serverThemePref(): undefined {
  return undefined;
}

export function setThemePref(pref: ThemePref): void {
  try {
    if (pref === "system") {
      // Ghi explicit, không xoá: "không có khoá" đã mang nghĩa dark.
      localStorage.setItem(KEY, pref);
      delete document.documentElement.dataset.theme;
    } else {
      localStorage.setItem(KEY, pref);
      document.documentElement.dataset.theme = pref;
    }
  } catch {
    /* không lưu được thì vẫn đổi được trong phiên này */
    if (pref === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = pref;
  }
  notify();
}

/**
 * Chạy đồng bộ trong `<head>`, TRƯỚC khi trang vẽ.
 *
 * Không có nó, khách mới (mặc định dark) sẽ thấy một nháy sáng mỗi lần tải —
 * React chưa kịp chạy thì HTML đã được sơn. `try/catch` là bắt buộc: Safari
 * riêng tư ném lỗi khi đọc localStorage, và một lỗi ở đây sẽ làm hỏng cả lần
 * dựng đầu.
 */
export const THEME_INIT_SCRIPT =
  'try{var t=localStorage.getItem("theme");if(t==="light")document.documentElement.dataset.theme=t;else if(t!=="system")document.documentElement.dataset.theme="dark"}catch(e){}';
