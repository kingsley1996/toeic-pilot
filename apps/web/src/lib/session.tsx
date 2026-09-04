"use client";

import { API_ROUTES, type UserPublic } from "@toeic-pilot/shared";
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { clearAccessToken, getAccessToken, subscribeToToken } from "@/lib/auth-storage";

export type SessionStatus = "loading" | "authenticated" | "anonymous";

type Session = {
  status: SessionStatus;
  user: UserPublic | null;
  token: string | null;
  /** editor or admin — the roles the content area is for. */
  canEdit: boolean;
  /** admin only — publishing decides what learners actually see. */
  canPublish: boolean;
  /**
   * Đọc lại `/auth/me`.
   *
   * Cần vì hồ sơ nằm TRONG phiên: sửa tên hiển thị mà không gọi lại thì header
   * vẫn hiện tên cũ cho tới lần tải trang sau, và người dùng sẽ bấm Lưu thêm
   * vài lần nữa vì tưởng chưa ăn.
   *
   * Đổi mật khẩu KHÔNG cần gọi: nó thay token, mà token là thứ effect bên dưới
   * đang theo dõi, nên vòng đọc lại tự chạy.
   */
  refresh: () => void;
  logout: () => void;
};

const SessionContext = createContext<Session | null>(null);

/** The server has no localStorage, so it can only report "not known yet". */
function serverSnapshot(): undefined {
  return undefined;
}

/**
 * Resolves who is signed in, once, for the whole app.
 *
 * Before this every page fetched /me for itself and the header could not see the
 * answer at all — which is why it offered "Log in" to people who were already
 * signed in. One fetch, one source of truth, and the shell renders from the same
 * state the pages do.
 *
 * `status` is **derived** rather than stored. Keeping it in state would mean
 * writing it from an effect, which cascades renders, and would let it drift out
 * of step with the token it is supposed to describe.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  // undefined = server render or first paint · null = no token · string = token
  const token = useSyncExternalStore(subscribeToToken, getAccessToken, serverSnapshot);
  const [user, setUser] = useState<UserPublic | null>(null);
  const [rejected, setRejected] = useState(false);
  // Bộ đếm chứ không phải cờ boolean: hai lần lưu liên tiếp phải chạy hai lượt
  // đọc, còn cờ bật-tắt sẽ nuốt mất lượt thứ hai.
  const [reloadKey, setReloadKey] = useState(0);
  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);
  /* Đếm số lần thử lại của lượt đọc bên dưới. Ref chứ không phải state: nó điều
     khiển vòng thử lại chứ không vẽ ra gì, và đặt vào state thì mỗi lần tăng là
     một lần dựng lại cả cây. */
  const tries = useRef(0);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    let again = 0;
    apiFetch<UserPublic>(API_ROUTES.me, { token })
      .then((me) => {
        if (cancelled) return;
        tries.current = 0;
        setUser(me);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        /*
         * Chỉ vứt token khi MÁY CHỦ chối nó, không phải khi request hỏng.
         *
         * Token hết hạn hay bị sửa thì từ đây trông y như không có token, và giữ
         * nó lại chỉ để thử lại ở mọi lần điều hướng. Nhưng một request HỎNG thì
         * không nói gì về token cả: mạng chập, máy chủ 503, hay — dễ gặp nhất —
         * `fetch` bị chính cú điều hướng huỷ giữa chừng. Vứt token trong những
         * ca đó là **tự đăng xuất người dùng vì một cú nhấp chuột nhanh**, và họ
         * chỉ thấy mình đột nhiên ở màn hình đăng nhập, không một lời giải thích.
         */
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearAccessToken();
          setRejected(true);
          return;
        }
        /*
         * Giữ token thôi thì chưa đủ: `status` suy ra từ `user`, nên một lượt
         * đọc hỏng mà không thử lại sẽ treo cả app ở `loading` — người dùng ngồi
         * nhìn khung xám mãi mãi, còn tệ hơn bị đá ra màn hình đăng nhập. Thử
         * lại vài lần rồi thôi: hỏng dai thì đó là chuyện của mạng, và thử mãi
         * chỉ đổi một chỗ treo lấy một vòng lặp.
         */
        if (tries.current >= 2) return;
        tries.current += 1;
        again = window.setTimeout(refresh, 700 * tries.current);
      });
    return () => {
      cancelled = true;
      window.clearTimeout(again);
    };
  }, [token, reloadKey, refresh]);

  const router = useRouter();
  const logout = useCallback(() => {
    /*
     * Báo máy chủ TRƯỚC khi xoá, vì request cần đúng token sắp bị vứt đi —
     * `apiFetch` nhận token qua tham số nên không có cuộc đua nào với
     * localStorage.
     *
     * **Không `await`.** Xoá phía client là vô điều kiện: bắt người dùng chờ
     * một vòng mạng để thoát ra, rồi giữ họ lại ở trạng thái đã đăng nhập nếu
     * vòng đó hỏng, còn tệ hơn chính cái lỗ đang được vá. Thu hồi phía máy chủ
     * là lớp thứ hai, cho những bản sao của token mà trình duyệt này không với
     * tới được.
     */
    if (token) {
      void apiFetch(API_ROUTES.logout, { method: "POST", token }).catch(() => {
        /* mạng hỏng hay Redis hỏng đều không được cản người dùng thoát ra */
      });
    }
    clearAccessToken();
    setUser(null);
    router.push("/");
  }, [router, token]);

  const status: SessionStatus =
    token === undefined
      ? "loading"
      : token === null || rejected
        ? "anonymous"
        : user
          ? "authenticated"
          : "loading";

  const value = useMemo<Session>(
    () => ({
      status,
      user: status === "authenticated" ? user : null,
      token: token ?? null,
      canEdit: user?.role === "editor" || user?.role === "admin",
      canPublish: user?.role === "admin",
      refresh,
      logout,
    }),
    [status, user, token, refresh, logout],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) {
    throw new Error("useSession must be used inside <SessionProvider>");
  }
  return session;
}

/**
 * Sends anonymous visitors to /login, and — when `canEdit` is asked for — anyone
 * without it back to /learn, the home of the learner area.
 *
 * Redirecting rather than showing a 403 is the point: someone who never had
 * access should simply not be there, not be told they were refused. The server
 * still enforces every one of these boundaries; this only decides what is worth
 * rendering.
 */
export function useRequireSession(options: { canEdit?: boolean } = {}): Session {
  const session = useSession();
  const router = useRouter();
  const needsEdit = options.canEdit ?? false;

  useEffect(() => {
    if (session.status === "anonymous") {
      router.replace("/login");
      return;
    }
    if (session.status === "authenticated" && needsEdit && !session.canEdit) {
      router.replace("/dashboard");
    }
  }, [session.status, session.canEdit, needsEdit, router]);

  return session;
}
