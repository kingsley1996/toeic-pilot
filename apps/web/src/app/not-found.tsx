import { ButtonLink, EmptyState, Page } from "@/components/ui";

export default function NotFound() {
  return (
    <Page className="max-w-xl">
      <EmptyState
        icon="🧭"
        title="Không tìm thấy trang này"
        description="Đường dẫn có thể đã cũ, hoặc nội dung chưa được xuất bản."
        action={<ButtonLink href="/">Về trang chủ</ButtonLink>}
      />
    </Page>
  );
}
