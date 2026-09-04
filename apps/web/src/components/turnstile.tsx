"use client";

import { API_ROUTES, type TurnstilePublic } from "@toeic-pilot/shared";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { apiFetch } from "@/lib/api";
import { getThemePref, serverThemePref, subscribeToTheme } from "@/lib/theme";

/**
 * Ô kiểm chống bot của Cloudflare Turnstile (ADR-015).
 *
 * Nó vá đúng cái lỗ mà bộ rate limit theo IP **tự nhận là không vá được**: một
 * botnet xoay địa chỉ đi qua nó như không có gì. Turnstile không đếm request —
 * nó bắt mỗi lần gửi form phải trả một cái giá tính toán ở trình duyệt, nên đổi
 * IP không giúp gì, còn người dùng thật thì không bị tính chung hạn mức với
 * người ngồi cùng đường mạng.
 *
 * **Site key lấy từ MÁY CHỦ, không từ biến môi trường của web.** Hai bên đọc hai
 * biến riêng thì sẽ có ngày trang vẽ ô kiểm mà máy chủ không kiểm gì — trông như
 * được bảo vệ, và không gì báo. Đổi lại, bật Turnstile lên không cần build lại
 * bản web.
 *
 * **Token dùng ĐÚNG MỘT LẦN và sống 5 phút**, và đó là thứ định hình cả API ở
 * dưới. Trang đăng ký gọi liền `register` rồi `login`, tức hai lần gửi cho một
 * lần người dùng bấm nút; gõ sai mật khẩu rồi gửi lại cũng là một lần nữa. Nên
 * chỗ này không phát ra "cái token", nó phát ra `take()` — mỗi lần gọi là một
 * token còn dùng được, tự làm mới khi cái cũ đã tiêu.
 */

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

/** Tên header Cloudflare dùng trong mọi ví dụ của họ; máy chủ đọc đúng tên này. */
export const TURNSTILE_HEADER = "cf-turnstile-response";

/* Bỏ cuộc sau chừng này. Ô kiểm bình thường xong trong một hai giây; treo lâu
   hơn nghĩa là script không tải được, và lúc đó bắt người dùng đợi mãi tệ hơn
   là để họ gửi form rồi nhận một lời từ chối đọc được. */
const SOLVE_TIMEOUT_MS = 20_000;

type TurnstileApi = {
  render: (el: HTMLElement, options: Record<string, unknown>) => string;
  reset: (id: string) => void;
  remove: (id: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

/* Script tải MỘT lần cho cả trang, kể cả khi có hai ô kiểm: nhúng hai lần thì
   `window.turnstile` bị dựng lại dưới chân widget đã render. */
let scriptLoad: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  scriptLoad ??= new Promise<void>((resolve, reject) => {
    const tag = document.createElement("script");
    tag.src = SCRIPT_SRC;
    tag.async = true;
    tag.onload = () => resolve();
    tag.onerror = () => {
      // Cho phép thử lại: mạng chập một lần không được biến thành một trang
      // vĩnh viễn không đăng nhập được cho tới khi F5.
      scriptLoad = null;
      reject(new Error("turnstile script failed to load"));
    };
    document.head.append(tag);
  });
  return scriptLoad;
}

/**
 * Không lấy được token — script không tải được, hoặc ô kiểm treo.
 *
 * Có kiểu riêng để form nói được câu ĐÚNG. Rơi vào "Không đăng nhập được" thì
 * người dùng đi kiểm tra lại mật khẩu, tức là đi sai hướng hoàn toàn; còn "tải
 * lại trang" là thứ họ làm được ngay.
 */
export class TurnstileUnavailable extends Error {
  constructor() {
    super("Chưa xác minh được trình duyệt. Tải lại trang rồi thử lại.");
    this.name = "TurnstileUnavailable";
  }
}

export type TurnstileGate = {
  /** Gắn vào form. `null` khi Turnstile chưa bật — không chừa chỗ trống. */
  widget: React.ReactNode;
  /**
   * Một token còn dùng được cho lần gửi tới, hoặc `null` khi Turnstile tắt.
   *
   * Ném lỗi khi không lấy được token — chỗ gọi hiện lời từ chối thay vì gửi đi
   * một request chắc chắn bị 403.
   */
  take: () => Promise<string | null>;
};

export function useTurnstile(): TurnstileGate {
  /* `undefined` chưa hỏi xong · `null` tắt · chuỗi là đang bật. Ba trạng thái
     chứ không hai, cùng cái bẫy mà `session.status` đã ghi lại: gộp "chưa biết"
     với "tắt" thì ô kiểm nháy vào rồi biến mất ở mỗi lần tải trang. */
  const [siteKey, setSiteKey] = useState<string | null | undefined>(undefined);
  const host = useRef<HTMLDivElement | null>(null);
  const widgetId = useRef<string | null>(null);
  /* Token đang cầm, và người đang đợi token kế tiếp. Ref chứ không state: chúng
     điều khiển luồng gửi form, không vẽ ra gì, và mỗi lần đổi mà dựng lại cây
     thì ô kiểm bị tháo ra lắp lại giữa chừng. */
  const held = useRef<string | null>(null);
  const waiting = useRef<((token: string | null) => void) | null>(null);

  const theme = useSyncExternalStore(subscribeToTheme, getThemePref, serverThemePref);

  useEffect(() => {
    let alive = true;
    // 204 ⇒ `apiFetch` trả `undefined`; ở đây nghĩa là "Turnstile chưa bật".
    apiFetch<TurnstilePublic | undefined>(API_ROUTES.turnstile)
      .then((body) => {
        if (alive) setSiteKey(body?.site_key ?? null);
      })
      .catch(() => {
        /* Không hỏi được thì coi như tắt. Máy chủ mới là bên quyết định có đòi
           token hay không, nên đoán sai ở đây cùng lắm là một lời từ chối đọc
           được, chứ không phải một trang chết. */
        if (alive) setSiteKey(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!siteKey || !host.current) return;
    let alive = true;
    const box = host.current;

    void loadScript()
      .then(() => {
        if (!alive || !window.turnstile) return;
        widgetId.current = window.turnstile.render(box, {
          sitekey: siteKey,
          /* Theo đúng chế độ sáng/tối của app, không của hệ điều hành: ô kiểm là
             một iframe của Cloudflare nên không có cách nào tô lại nó bằng CSS
             của mình. Chọn sai thì nó là ô sáng chói duy nhất trên một trang
             tối. `"system"` của app khớp với `"auto"` của Cloudflare. */
          theme: theme === "system" ? "auto" : theme,
          callback: (token: string) => {
            held.current = token;
            waiting.current?.(token);
            waiting.current = null;
          },
          /* Hết hạn và lỗi đều làm token đang cầm thành vô giá trị. Không xoá
             thì `take()` trả về một chuỗi mà máy chủ chắc chắn từ chối, và người
             dùng đọc được "hết hạn" ở chỗ họ vừa gõ đúng mật khẩu. */
          "expired-callback": () => {
            held.current = null;
          },
          "error-callback": () => {
            held.current = null;
            waiting.current?.(null);
            waiting.current = null;
          },
        });
      })
      .catch(() => {
        /* Script không tải được. Máy chủ sẽ từ chối, và lời từ chối ấy đọc
           được — im lặng ở đây tốt hơn là một thông báo lỗi kỹ thuật. */
      });

    return () => {
      alive = false;
      if (widgetId.current && window.turnstile) {
        window.turnstile.remove(widgetId.current);
        widgetId.current = null;
      }
      held.current = null;
    };
  }, [siteKey, theme]);

  const take = useCallback(async (): Promise<string | null> => {
    if (siteKey === null) return null;
    /* Còn cầm token thì tiêu nó và đi tiếp. Xoá NGAY khi đưa ra, vì Cloudflare
       chỉ nhận mỗi token một lần: giữ lại là để dành sẵn một cái 403 cho lần
       gửi sau. */
    if (held.current) {
      const token = held.current;
      held.current = null;
      return token;
    }
    if (!widgetId.current || !window.turnstile) {
      throw new TurnstileUnavailable();
    }
    window.turnstile.reset(widgetId.current);
    const token = await new Promise<string | null>((resolve) => {
      waiting.current = resolve;
      window.setTimeout(() => {
        if (waiting.current === resolve) {
          waiting.current = null;
          resolve(null);
        }
      }, SOLVE_TIMEOUT_MS);
    });
    if (!token) throw new TurnstileUnavailable();
    return token;
  }, [siteKey]);

  return {
    // Không chừa chỗ khi tắt: một khoảng trống cao 65px giữa form trông như một
    // thứ đang tải mãi không xong.
    widget: siteKey ? <div ref={host} className="flex justify-center" /> : null,
    take,
  };
}

/** Header gửi kèm, hoặc không có gì khi Turnstile tắt. */
export function turnstileHeader(token: string | null): Record<string, string> {
  return token ? { [TURNSTILE_HEADER]: token } : {};
}
