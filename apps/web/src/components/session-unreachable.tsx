"use client";

import { useSession } from "@/lib/session";
import { Alert, Button } from "@/components/ui";

/**
 * Dải "mất kết nối" sống ngoài AppShell (xem layout gốc): `fixed` nên sống sót
 * qua cả ba khung, kể cả nhánh trần của khu quản trị và màn làm bài — đúng chỗ
 * treo khung xám vĩnh viễn trước đây.
 */
export function SessionUnreachable() {
  const { failed, refresh } = useSession();
  if (!failed) return null;
  return (
    <div className="fixed inset-x-0 bottom-4 z-50 mx-auto w-fit max-w-[calc(100vw-2rem)]">
      <Alert tone="warn">
        <span>Mất kết nối tới máy chủ.</span>
        <Button type="button" size="sm" variant="secondary" onClick={refresh}>
          Thử lại
        </Button>
      </Alert>
    </div>
  );
}
