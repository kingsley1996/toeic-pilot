import type { Metadata } from "next";
import { Archivo, Be_Vietnam_Pro, IBM_Plex_Mono } from "next/font/google";

import { AppShell } from "@/components/app-shell";
import { SessionProvider } from "@/lib/session";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

import "./globals.css";

/*
 * `subsets` PHẢI có "vietnamese" ở cả ba font. Thiếu nó thì `ế` `ộ` `ữ` rơi về
 * font hệ thống và một dòng chữ sẽ lẫn hai kiểu chữ khác nhau — rất dễ lọt vì
 * chữ tiếng Anh trông vẫn hoàn hảo. Đã xác minh cả ba có subset này.
 */
const display = Archivo({
  variable: "--font-display",
  subsets: ["latin", "vietnamese"],
  weight: ["600"],
  display: "swap",
});

const body = Be_Vietnam_Pro({
  variable: "--font-body",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  display: "swap",
});

const data = IBM_Plex_Mono({
  variable: "--font-data",
  subsets: ["latin", "vietnamese"],
  weight: ["500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "TOEIC Pilot",
  description: "Học tiếng Anh mỗi ngày và luyện thi TOEIC",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head>
        {/* Đặt data-theme trước khi trang vẽ, nếu không người chọn theme tối sẽ
            thấy một nháy trắng mỗi lần tải. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className={`${display.variable} ${body.variable} ${data.variable}`}>
        {/* Provider bọc cả shell lẫn các trang: header đọc đúng phiên mà các
            trang đọc, và đó là thứ ngăn nó mời "Đăng nhập" với người đã đăng
            nhập rồi. */}
        <SessionProvider>
          <AppShell>{children}</AppShell>
        </SessionProvider>
      </body>
    </html>
  );
}
