import { AdminShell } from "@/components/admin-shell";

/**
 * Mọi thứ dưới /admin dùng khung riêng, không dùng header của khu học.
 *
 * `AppShell` ở root layout tự nhận ra đường dẫn /admin và nhường chỗ, nên hai
 * khung không chồng lên nhau.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
