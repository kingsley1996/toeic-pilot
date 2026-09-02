/**
 * Sidebar đang mở rộng hay đã thu gọn thành một dải icon.
 *
 * Cùng khuôn với `theme.ts`, và vì cùng những lý do: sự kiện `storage` của
 * trình duyệt chỉ bắn ở CÁC TAB KHÁC nên phải tự phát tín hiệu trong tab vừa
 * ghi, và Safari riêng tư ném lỗi khi đọc localStorage.
 *
 * Thứ THẬT SỰ điều khiển bề rộng là `data-sidebar` trên `<html>`, không phải
 * state React — xem `SIDEBAR_INIT_SCRIPT` bên dưới. State ở đây chỉ để nút bấm
 * biết mình đang là mũi tên nào.
 */
export type SidebarState = "expanded" | "collapsed";

const KEY = "sidebar";
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

export function subscribeToSidebar(onChange: () => void): () => void {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function getSidebarState(): SidebarState {
  if (typeof window === "undefined") return "expanded";
  try {
    return localStorage.getItem(KEY) === "collapsed" ? "collapsed" : "expanded";
  } catch {
    return "expanded";
  }
}

/** Server không có localStorage, nên nó chỉ báo được "chưa biết". */
export function serverSidebarState(): undefined {
  return undefined;
}

export function setSidebarState(state: SidebarState): void {
  const root = document.documentElement;
  try {
    if (state === "collapsed") localStorage.setItem(KEY, "collapsed");
    else localStorage.removeItem(KEY);
  } catch {
    /* không lưu được thì vẫn đổi được trong phiên này */
  }
  if (state === "collapsed") root.dataset.sidebar = "collapsed";
  else delete root.dataset.sidebar;
  notify();
}

/**
 * Chạy đồng bộ trong `<head>`, TRƯỚC khi trang vẽ.
 *
 * Không có nó, người đã thu gọn sidebar sẽ thấy cột rộng 240px vẽ ra rồi co lại
 * còn 64px ở mỗi lần tải — một cú nhảy bố cục, tệ hơn hẳn cú nháy màu mà
 * `THEME_INIT_SCRIPT` tồn tại để chặn. Đây cũng là lý do trạng thái thu gọn
 * được vẽ bằng CSS bám vào thuộc tính này chứ không bằng state React: state chỉ
 * có sau khi hydrate, và cú nhảy nằm trước đó.
 */
export const SIDEBAR_INIT_SCRIPT =
  'try{if(localStorage.getItem("sidebar")==="collapsed")document.documentElement.dataset.sidebar="collapsed"}catch(e){}';
