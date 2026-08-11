import { defineConfig, devices } from "@playwright/test";

/*
 * End-to-end cho khu học.
 *
 * **Chạy trên NGĂN XẾP THẬT, không dựng máy chủ riêng.** `webServer` của
 * Playwright chỉ khởi động được `next dev`, mà một luồng học còn cần API,
 * Postgres và Redis — dựng nửa ngăn xếp rồi mong nó chạy là cách nhanh nhất có
 * một bộ test đỏ vì lý do không liên quan gì tới code. Nên: `docker compose up`
 * trước, rồi chạy test.
 *
 * Cũng vì thế mà `next dev` KHÔNG được chạy trên host khi container `web` đang
 * lên — cả hai ghi cùng `apps/web/.next` và cache lẫn nhau (xem CLAUDE.md).
 *
 * Vì sao e2e chứ không phải test component: bốn lỗi giao diện của sprint này —
 * nút xoá báo thành công cho việc chưa xảy ra, media đã gắn hiện "chưa có", sáu
 * endpoint đổi hình dạng mà `tsc` im lặng, Part 1/2 không ghi vào được — đều là
 * lỗi Ở CHỖ NỐI, không lỗi nào nằm trong một component đơn lẻ. Test render một
 * component sẽ xanh với cả bốn.
 */
export default defineConfig({
  testDir: "./e2e",
  // Tuần tự: mỗi test tự đăng ký tài khoản riêng nên chúng độc lập về dữ liệu,
  // nhưng chúng dùng chung một database dev và một lượt chạy song song sẽ khiến
  // lỗi trở nên khó lần lại hơn nhiều so với thời gian tiết kiệm được.
  workers: 1,
  fullyParallel: false,
  // Không retry ở máy dev: một test xanh ở lần thử thứ hai là một test không
  // đáng tin, và ẩn nó đi thì lần sau nó hỏng lúc không ai nhìn.
  retries: process.env.CI ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    // Chỉ giữ dấu vết của lần hỏng: một trace cho mỗi lần chạy xanh là hàng
    // trăm megabyte không ai mở ra.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
