"use client";

import { TriangleAlert } from "lucide-react";

import { Button, ButtonLink, EmptyState, Page } from "@/components/ui";

/**
 * Tuyến phòng thủ cuối.
 *
 * Không có nó, một lỗi render ở bất kỳ trang nào sẽ thay cả app bằng màn hình
 * mặc định của Next.js — không điều hướng, không đường quay lại. `reset` dựng
 * lại segment, đủ cho những lỗi tạm thời (fetch rớt, response hỏng) vốn gây ra
 * phần lớn các trường hợp này.
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
        icon={TriangleAlert}
        title="Có lỗi xảy ra"
        description={
          <>
            Trang này không hiển thị được.
            {error.digest && (
              <>
                {" "}
                Mã lỗi: <code className="font-data text-ink">{error.digest}</code>
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
