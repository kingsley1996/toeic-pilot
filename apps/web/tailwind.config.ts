import type { Config } from "tailwindcss";

/**
 * Màu đến từ CSS variable trong globals.css chứ không liệt kê ở đây, nên sáng và
 * tối là MỘT định nghĩa thay vì một bản sao `dark:` trên mỗi element.
 * `<alpha-value>` giữ cho các modifier độ mờ như `bg-action/10` vẫn hoạt động.
 */
const c = (variable: string) => `rgb(var(${variable}) / <alpha-value>)`;

export default {
  content: ["./src/components/**/*.{ts,tsx}", "./src/app/**/*.{ts,tsx}"],
  theme: {
    /*
     * MỘT bán kính (§6.2). Đặt ngoài `extend` là có chủ ý: nó thay thế toàn bộ
     * thang mặc định, nên `rounded-lg` / `rounded-xl` / `rounded-full` không còn
     * sinh ra CSS nào. Đó chính là hàng rào — bo góc cũ sẽ lộ ra ngay chứ không
     * âm thầm sống sót.
     */
    borderRadius: {
      none: "0",
      DEFAULT: "4px",
      pill: "9999px",
    },
    /* Đổ bóng bị bỏ có chủ ý (§6.3): độ nổi là viền + bậc nền. Lớp phủ dùng
       utility `.shadow-overlay`. */
    boxShadow: {
      none: "none",
    },
    extend: {
      colors: {
        ground: c("--ground"),
        panel: c("--panel"),
        recess: c("--recess"),
        rule: c("--rule"),
        "rule-strong": c("--rule-strong"),

        ink: c("--ink"),
        "ink-muted": c("--ink-muted"),
        "ink-faint": c("--ink-faint"),

        action: c("--action"),
        "action-hover": c("--action-hover"),
        "action-ink": c("--action-ink"),
        "action-tint": c("--action-tint"),
        "on-action": c("--on-action"),

        ok: c("--ok"),
        "ok-tint": c("--ok-tint"),
        warn: c("--warn"),
        "warn-tint": c("--warn-tint"),
        alert: c("--alert"),
        "alert-tint": c("--alert-tint"),
        myth: c("--myth"),
        "myth-tint": c("--myth-tint"),

        "accent-us": c("--accent-us"),
        "accent-uk": c("--accent-uk"),
        "accent-au": c("--accent-au"),
        "accent-ca": c("--accent-ca"),
      },
      borderColor: {
        DEFAULT: c("--rule"),
      },
      fontFamily: {
        display: ["var(--font-display)", "ui-sans-serif", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "ui-sans-serif", "system-ui", "sans-serif"],
        data: ["var(--font-data)", "ui-monospace", "monospace"],
      },
      fontSize: {
        label: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.08em" }],
        small: ["0.8125rem", { lineHeight: "1.3125rem" }],
        body: ["0.9375rem", { lineHeight: "1.5625rem" }],
        subtitle: ["1.0625rem", { lineHeight: "1.625rem" }],
        title: ["1.375rem", { lineHeight: "1.875rem", letterSpacing: "-0.01em" }],
        display: ["1.875rem", { lineHeight: "2.375rem", letterSpacing: "-0.015em" }],
        readout: ["3rem", { lineHeight: "3.5rem", letterSpacing: "-0.02em" }],
        "readout-lg": ["4rem", { lineHeight: "4.5rem", letterSpacing: "-0.02em" }],
      },
      transitionTimingFunction: {
        DEFAULT: "cubic-bezier(0.2, 0, 0, 1)",
      },
      transitionDuration: {
        DEFAULT: "120ms",
        enter: "200ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
