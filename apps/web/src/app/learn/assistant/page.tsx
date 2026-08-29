"use client";

import { AssistantChat } from "@/components/assistant-chat";
import { Page, PageHeader } from "@/components/ui";
import { useRequireSession } from "@/lib/session";

export default function AssistantPage() {
  const { status, token } = useRequireSession();

  return (
    <Page>
      <PageHeader
        title="Trợ lý AI"
        description="Hỏi về cách dùng TOEIC Pilot và tiến độ của bạn."
      />
      {status === "authenticated" && token ? (
        <AssistantChat token={token} />
      ) : (
        <p className="text-small text-ink-faint">Đang tải…</p>
      )}
    </Page>
  );
}
