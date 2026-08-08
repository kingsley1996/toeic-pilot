"use client";

import { API_ROUTES, type UserPublic } from "@toeic-pilot/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { clearAccessToken, getAccessToken } from "@/lib/auth-storage";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserPublic | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    apiFetch<UserPublic>(API_ROUTES.me, { token })
      .then(setUser)
      .catch((err) => {
        clearAccessToken();
        setError(err instanceof ApiError ? err.message : "Session expired");
      });
  }, [router]);

  function logout() {
    clearAccessToken();
    router.push("/login");
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg px-4 py-12">
        <p className="text-red-600">{error}</p>
        <Link href="/login" className="mt-4 inline-block text-blue-600">
          Back to login
        </Link>
      </div>
    );
  }

  if (!user) {
    return <div className="mx-auto max-w-lg px-4 py-12 text-zinc-500">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-12">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <p className="mt-2 text-zinc-600 dark:text-zinc-400">
        Signed in as{" "}
        <span className="font-medium text-zinc-900 dark:text-zinc-100">{user.email}</span>
      </p>
      <p className="mt-4 text-sm text-zinc-500">Learning modules will appear here in Phase 2+.</p>
      <button
        type="button"
        onClick={logout}
        className="mt-6 rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
      >
        Log out
      </button>
    </div>
  );
}
