"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { cx } from "@/components/ui";
import {
  getThemePref,
  serverThemePref,
  setThemePref,
  subscribeToTheme,
  type ThemePref,
} from "@/lib/theme";

const OPTIONS: Array<{ value: ThemePref; label: string; Icon: typeof Sun }> = [
  { value: "light", label: "Sáng", Icon: Sun },
  { value: "dark", label: "Tối", Icon: Moon },
  { value: "system", label: "Theo hệ thống", Icon: Monitor },
];

/**
 * Bộ chọn ba trạng thái, không phải công tắc hai trạng thái.
 *
 * `undefined` trong lần dựng đầu là trạng thái thứ tư — "chưa đọc được
 * localStorage". Đoán bừa ở đây sẽ làm nút nhảy sang lựa chọn khác ngay sau khi
 * hydrate, đúng kiểu lỗi mà header từng mắc với "Đăng nhập".
 */
export function ThemeToggle() {
  const pref = useSyncExternalStore(subscribeToTheme, getThemePref, serverThemePref);

  return (
    <div
      role="group"
      aria-label="Giao diện sáng tối"
      className="inline-flex rounded border border-rule p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = pref === value;
        return (
          <button
            key={value}
            type="button"
            aria-label={label}
            aria-pressed={pref === undefined ? undefined : active}
            title={label}
            onClick={() => setThemePref(value)}
            className={cx(
              "grid h-7 w-7 place-items-center rounded transition-colors",
              active
                ? "bg-recess text-ink"
                : "text-ink-faint hover:bg-recess/60 hover:text-ink-muted",
            )}
          >
            <Icon size={14} strokeWidth={2} aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
