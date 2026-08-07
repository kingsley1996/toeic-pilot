import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <section className="space-y-6">
        <p className="text-sm font-medium uppercase tracking-wider text-blue-600">
          Phase 1 — Scaffolding
        </p>
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          Learn English daily. Prepare for TOEIC with AI coaching.
        </h1>
        <p className="max-w-xl text-lg text-zinc-600 dark:text-zinc-400">
          Monorepo stack: Next.js, FastAPI, PostgreSQL + pgvector, Redis. Auth and shared
          packages are wired; product modules ship in later epics.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            href="/register"
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Create account
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-semibold hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Dashboard
          </Link>
        </div>
      </section>
    </div>
  );
}
