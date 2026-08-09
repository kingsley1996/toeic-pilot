"use client";

import { Button, ButtonLink, EmptyState, Page } from "@/components/ui";

/**
 * The last line of defence.
 *
 * Without it, a render error in any page replaces the whole app with Next.js's
 * default screen — no navigation, no way back. `reset` re-renders the segment,
 * which is enough for the transient failures (a dropped fetch, a bad response)
 * that cause most of these.
 */
export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <Page className="max-w-xl">
      <EmptyState
        icon="⚠️"
        title="Có lỗi xảy ra"
        description={
          <>
            Trang này không hiển thị được.
            {error.digest && (
              <>
                {" "}
                Mã lỗi: <code className="font-mono text-xs">{error.digest}</code>
              </>
            )}
          </>
        }
        action={
          <div className="flex gap-2">
            <Button onClick={reset}>Thử lại</Button>
            <ButtonLink href="/" variant="secondary">
              Về trang chủ
            </ButtonLink>
          </div>
        }
      />
    </Page>
  );
}
