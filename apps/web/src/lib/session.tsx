"use client";

import { API_ROUTES, type UserPublic } from "@toeic-pilot/shared";
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { apiFetch } from "@/lib/api";
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

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    apiFetch<UserPublic>(API_ROUTES.me, { token })
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (cancelled) return;
        // An expired or tampered token looks the same as none at all from here,
        // and leaving it in storage would retry on every navigation.
        clearAccessToken();
        setRejected(true);
      });
    return () => {
      cancelled = true;
    };
  }, [token, reloadKey]);

  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);

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
