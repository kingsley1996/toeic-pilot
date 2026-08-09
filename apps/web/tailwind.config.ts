import type { Config } from "tailwindcss";

/**
 * Colours come from the CSS variables in globals.css rather than being listed
 * here, so light and dark are one definition instead of a `dark:` twin on every
 * element. `<alpha-value>` keeps opacity modifiers such as `bg-brand/10` working.
 */
function withAlpha(variable: string) {
  return `rgb(var(${variable}) / <alpha-value>)`;
}

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: withAlpha("--surface"),
        "surface-raised": withAlpha("--surface-raised"),
        "surface-sunken": withAlpha("--surface-sunken"),
        border: withAlpha("--border"),
        "border-strong": withAlpha("--border-strong"),

        text: withAlpha("--text"),
        "text-muted": withAlpha("--text-muted"),
        "text-subtle": withAlpha("--text-subtle"),

        brand: withAlpha("--brand"),
        "brand-hover": withAlpha("--brand-hover"),
        "brand-soft": withAlpha("--brand-soft"),
        "brand-text": withAlpha("--brand-text"),

        success: withAlpha("--success"),
        "success-soft": withAlpha("--success-soft"),
        warning: withAlpha("--warning"),
        "warning-soft": withAlpha("--warning-soft"),
        danger: withAlpha("--danger"),
        "danger-soft": withAlpha("--danger-soft"),
      },
      borderColor: {
        DEFAULT: withAlpha("--border"),
      },
    },
  },
  plugins: [],
} satisfies Config;
