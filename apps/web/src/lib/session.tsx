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
  }, [token]);

  const router = useRouter();
  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
    router.push("/");
  }, [router]);

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
      logout,
    }),
    [status, user, token, logout],
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
      router.replace("/learn");
    }
  }, [session.status, session.canEdit, needsEdit, router]);

  return session;
}
