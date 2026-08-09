/**
 * Lựa chọn theme của người dùng, và chỗ nó được lưu.
 *
 * Ba trạng thái chứ không phải hai: `system` là mặc định và có nghĩa "đi theo hệ
 * điều hành", khác hẳn với việc chọn `light`. Nếu gộp `system` vào `light` thì
 * người dùng máy đang để chế độ tối sẽ bị ép sáng ngay lần đầu vào app.
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
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    // Safari ở chế độ riêng tư ném lỗi khi đọc localStorage.
    return "system";
  }
}

/** Server không có localStorage, nên nó chỉ báo được "chưa biết". */
export function serverThemePref(): undefined {
  return undefined;
}

export function setThemePref(pref: ThemePref): void {
  try {
    if (pref === "system") {
      localStorage.removeItem(KEY);
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
 * Không có nó, người chọn theme tối sẽ thấy một nháy trắng mỗi lần tải — React
 * chưa kịp chạy thì HTML đã được sơn. `try/catch` là bắt buộc: Safari riêng tư
 * ném lỗi khi đọc localStorage, và một lỗi ở đây sẽ làm hỏng cả lần dựng đầu.
 */
export const THEME_INIT_SCRIPT =
  'try{var t=localStorage.getItem("theme");if(t==="dark"||t==="light")document.documentElement.dataset.theme=t}catch(e){}';
