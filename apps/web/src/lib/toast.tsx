"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { ToastViewport } from "@/components/toast";
import { playSound, type SoundName } from "@/lib/sound";

/**
 * Hàng thông báo tạm của cả ứng dụng.
 *
 * Trước khối này, mỗi tin vui tự dựng lấy chỗ đứng của nó: huy hiệu mới là một
 * `Panel` trên `/dashboard`, việc hôm nay là một dòng trong khối việc hôm nay,
 * và lên level thì không có gì cả. Nghĩa là **chỉ ai đang đứng ở trang chủ mới
 * biết**, còn người vừa ôn xong một chồng từ ở `/learn/review` thì không.
 *
 * Chia tầng có chủ ý: file này giữ *trạng thái*, `components/toast.tsx` giữ
 * *pixel*. Cùng lý do như bộ Petland — thứ quyết định "khi nào nói" và thứ
 * quyết định "trông thế nào" đổi theo hai nhịp khác nhau, và trộn chúng lại thì
 * đổi thiết kế cái thẻ sẽ phải đọc lại luật báo tin.
 *
 * Toast là lớp thứ HAI, không phải lớp duy nhất. Nó tự biến mất, nên không được
 * là nơi duy nhất một thông tin tồn tại: dòng huy hiệu mới trên trang chủ và
 * chấm đỏ ở hồ sơ vẫn ở nguyên đó. Ai vừa rời bàn phím lúc con toast hiện ra thì
 * vẫn còn đường tìm lại.
 */

export type ToastTone = "ok" | "info" | "warn" | "alert";

export type ToastInput = {
  title: string;
  description?: string;
  tone?: ToastTone;
  /** Cả thẻ thành một đường dẫn. Không có thì thẻ chỉ để đọc. */
  href?: string;
  linkLabel?: string;
  /** Tranh của huy hiệu/khung. Có tranh thì tranh thay cho icon. */
  imageUrl?: string | null;
  /** `null` = ở lại tới khi người đọc tự đóng. */
  durationMs?: number | null;
  /**
   * Tiếng báo đi kèm, và nó chỉ nên xin ở những thông báo đi NGAY SAU một cú
   * bấm.
   *
   * Trình duyệt chặn phát tiếng cho tới khi người dùng đã tương tác với trang,
   * nên một thông báo bắn ra từ lần `fetch` lúc mở trang — huy hiệu, việc hôm
   * nay, lên level — sẽ im lặng dù có xin. Xin một thứ biết chắc không được cấp
   * làm code nói dối về hành vi thật của nó, nên chúng để trống trường này.
   * Câu dictation thì khác: nó xảy ra đúng lúc người học vừa bấm Enter.
   */
  sound?: SoundName;

  /**
   * Khoá chống trùng, và nó gánh nhiều hơn vẻ ngoài của nó.
   *
   * Phần lớn thông báo ở đây bắn ra từ một `useEffect` sau khi một lần `fetch`
   * trả về, mà effect thì chạy **hai lần** dưới StrictMode của bản dev. Không có
   * khoá thì mỗi tin vui hiện thành hai thẻ chồng nhau — chỉ ở bản dev, nên nó
   * sống sót qua mọi lần xem lại trên máy người viết và chỉ lộ ra khi có người
   * quay video.
   *
   * Trùng khoá thì **thay tại chỗ**, không đẩy xuống cuối hàng: một thẻ nhảy chỗ
   * ngay dưới con trỏ là cách chắc chắn nhất để người ta bấm nhầm.
   */
  dedupeKey?: string;
};

export type Toast = ToastInput & {
  id: string;
  tone: ToastTone;
  durationMs: number | null;
  leaving: boolean;
};

type ToastApi = {
  show: (input: ToastInput) => string;
  dismiss: (id: string) => void;
};

const DEFAULT_MS = 6000;

/*
 * Ba thẻ là trần, và cái bị đẩy đi là cái CŨ NHẤT.
 *
 * Một tài khoản có sẵn lịch sử học mở một loạt huy hiệu ngay lần đọc đầu tiên
 * sau khi tính năng ra mắt; không có trần thì góc màn hình phủ kín và đọc như hệ
 * thống hỏng chứ không như phần thưởng. Giữ cái mới nhất vì nó là cái vừa xảy
 * ra — cái cũ đã có mấy giây để được đọc rồi.
 */
const MAX_VISIBLE = 3;

/** Đủ cho hiệu ứng mờ dần 120ms của §7 chạy hết trước khi phần tử bị gỡ. */
const LEAVE_MS = 140;

const ToastContext = createContext<ToastApi | null>(null);

let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, LEAVE_MS);
  }, []);

  const show = useCallback((input: ToastInput) => {
    // Phát trước khi dựng: tiếng và hình phải đến cùng lúc, và `playSound` tự
    // im khi người dùng đã tắt hoặc khi trình duyệt chặn.
    if (input.sound) playSound(input.sound);
    counter += 1;
    const id = `toast-${counter}`;
    const toast: Toast = {
      ...input,
      id,
      tone: input.tone ?? "info",
      durationMs: input.durationMs === undefined ? DEFAULT_MS : input.durationMs,
      leaving: false,
    };
    setToasts((prev) => {
      const at = input.dedupeKey
        ? prev.findIndex((t) => t.dedupeKey === input.dedupeKey && !t.leaving)
        : -1;
      if (at >= 0) {
        const next = [...prev];
        next[at] = toast;
        return next;
      }
      // Mới nhất đứng đầu mảng và đứng trên cùng màn hình. Thứ tự trong DOM khớp
      // thứ tự trên màn, nên trình đọc màn hình đi đúng thứ tự người ta nhìn.
      return [toast, ...prev].slice(0, MAX_VISIBLE);
    });
    return id;
  }, []);

  const api = useMemo(() => ({ show, dismiss }), [show, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) {
    throw new Error("useToast must be used inside <ToastProvider>");
  }
  return api;
}

/**
 * "Chuyện này đã báo trong phiên trình duyệt này chưa?"
 *
 * Ba chỗ dùng toast đều đọc dữ liệu **trạng thái** chứ không phải dữ liệu **sự
 * kiện**: `/progression/badges` nói "có 3 cái chưa xem", không nói "vừa mở được
 * 3 cái". Nên nếu cứ thấy là báo, thì mỗi lần chuyển trang lại báo lại, cho tới
 * khi người ta chịu mở trang huy hiệu — một phần thưởng biến thành một thứ đeo
 * bám.
 *
 * `signature` là nội dung, không phải chỉ cái khoá: mở thêm một huy hiệu nữa thì
 * chữ ký đổi và tin mới được báo, ngay trong cùng phiên.
 *
 * `sessionStorage` chứ không phải `localStorage`: quên sau khi đóng tab là đúng
 * ý. Đây là chống lặp trong một buổi, không phải một lời hứa lâu dài — và nếu
 * trình duyệt cấm lưu (cửa sổ ẩn danh, chặn site data) thì `catch` cho qua và
 * cùng lắm là báo lại một lần nữa. Im lặng nuốt mất tin vui thì tệ hơn.
 */
export function announceOnce(key: string, signature: string): boolean {
  try {
    const at = `toast:${key}`;
    if (window.sessionStorage.getItem(at) === signature) return false;
    window.sessionStorage.setItem(at, signature);
    return true;
  } catch {
    return true;
  }
}
