/**
 * Bộ phận nhỏ mà mọi trang được dựng từ đó.
 *
 * Nó tồn tại vì bản đầu của các màn hình này tự viết lại cùng một cái nút và
 * cùng một cái hộp có viền cả chục lần, mỗi lần khác nhau một chút — và một
 * thiết kế được quyết định lại ở từng trang thì không phải là thiết kế.
 *
 * Quy tắc hình thức nằm ở planning/DESIGN-SYSTEM.md. Ba điều dễ phá nhất:
 *   §6.3  KHÔNG đổ bóng. Độ nổi là viền + bậc nền.
 *   §6.2  MỘT bán kính (4px). `rounded-lg`/`rounded-xl` không còn sinh ra CSS.
 *   §11   Ranh giới component dùng `rule-strong`, không phải `rule`.
 */

import {
  CircleAlert,
  CircleCheck,
  CircleDashed,
  CircleSlash,
  Info,
  OctagonAlert,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

// --- nút ------------------------------------------------------------------

type Variant = "primary" | "secondary" | "quiet" | "destructive";
type Size = "sm" | "md" | "lg";

/*
 * Bỏ biến thể `success` của hệ cũ có chủ ý: nút không phải là chỗ báo trạng
 * thái, nó là chỗ ra lệnh. Nút Publish màu xanh lá nói rằng nó đã thành công
 * trước cả khi được bấm.
 */
const VARIANTS: Record<Variant, string> = {
  primary: "bg-action text-on-action hover:bg-action-hover",
  secondary: "border border-rule-strong bg-panel text-ink hover:bg-recess",
  quiet: "text-ink-muted hover:bg-recess hover:text-ink",
  destructive: "bg-alert text-white hover:opacity-90",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-2.5 text-small gap-1.5",
  md: "h-9 px-3.5 text-body gap-2",
  lg: "h-11 px-5 text-body gap-2",
};

function buttonClass(variant: Variant, size: Size, className?: string) {
  return cx(
    "inline-flex shrink-0 items-center justify-center rounded font-semibold transition-colors",
    // Nút vô hiệu hoá vẫn hiện rõ chứ không biến mất: ở màn admin, nút Publish
    // bị mờ CHÍNH LÀ thông báo — nó nói nội dung chưa sẵn sàng.
    "disabled:cursor-not-allowed disabled:opacity-45",
    VARIANTS[variant],
    SIZES[size],
    className,
  );
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: Variant; size?: Size }) {
  return <button className={buttonClass(variant, size, className)} {...props} />;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant; size?: Size }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

/**
 * Nút chỉ có icon.
 *
 * `aria-label` là bắt buộc trong kiểu, không phải tuỳ chọn — icon không bao giờ
 * được mang nghĩa một mình. Pseudo-element nới vùng chạm lên 44px mà không làm
 * phồng phần nhìn thấy.
 */
export function IconButton({
  icon: Icon,
  "aria-label": label,
  className,
  ...props
}: ComponentProps<"button"> & { icon: LucideIcon; "aria-label": string }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={cx(
        "relative grid h-9 w-9 place-items-center rounded text-ink-muted transition-colors",
        "hover:bg-recess hover:text-ink disabled:cursor-not-allowed disabled:opacity-45",
        "before:absolute before:-inset-1 before:content-['']",
        className,
      )}
      {...props}
    >
      <Icon size={16} strokeWidth={1.75} aria-hidden />
    </button>
  );
}

// --- bề mặt ---------------------------------------------------------------

/** Bề mặt nổi. Viền + bậc nền, không bóng. */
export function Panel({ className, ...props }: ComponentProps<"div">) {
  return <div className={cx("rounded border border-rule bg-panel", className)} {...props} />;
}

/**
 * Panel bấm được.
 *
 * Hover đổi viền và nền — KHÔNG nhấc lên. Card nhấc lên khi rê chuột
 * (`hover:-translate-y-*`) là một trong những dấu hiệu rõ nhất của giao diện
 * sinh tự động, và nó cũng làm layout rung khi dùng bàn phím.
 */
export function PanelLink({ className, ...props }: ComponentProps<typeof Link>) {
  return (
    <Link
      className={cx(
        "block rounded border border-rule bg-panel p-5 transition-colors",
        "hover:border-rule-strong hover:bg-recess",
        className,
      )}
      {...props}
    />
  );
}

// --- nhãn -----------------------------------------------------------------

type Tone = "neutral" | "action" | "ok" | "warn" | "alert";

const TONES: Record<Tone, string> = {
  neutral: "border-rule bg-recess text-ink-muted",
  action: "border-transparent bg-action-tint text-action-ink",
  ok: "border-transparent bg-ok-tint text-ok",
  warn: "border-transparent bg-warn-tint text-warn",
  alert: "border-transparent bg-alert-tint text-alert",
};

/** Nhãn trơn: từ loại, vai trò, độ khó. Không mang trạng thái quy trình. */
export function Tag({
  tone = "neutral",
  className,
  ...props
}: ComponentProps<"span"> & { tone?: Tone }) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-label font-semibold uppercase",
        TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

/**
 * Nhãn trạng thái — LUÔN có icon (§9.4).
 *
 * Trạng thái là thông tin, và thông tin không bao giờ chỉ nằm ở màu: người mù
 * màu đỏ-lục không phân biệt được "đã publish" với "audio thiếu" nếu chỉ có màu.
 */
export function StatusTag({
  tone,
  icon: Icon,
  children,
}: {
  tone: Tone;
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <Tag tone={tone}>
      <Icon size={12} strokeWidth={2} aria-hidden />
      {children}
    </Tag>
  );
}

/** Trạng thái xuất bản, khớp với `PublishableMixin` ở backend. */
export function PublishTag({ status }: { status: string }) {
  return status === "published" ? (
    <StatusTag tone="ok" icon={CircleCheck}>
      đã xuất bản
    </StatusTag>
  ) : (
    <StatusTag tone="neutral" icon={CircleDashed}>
      nháp
    </StatusTag>
  );
}

/**
 * Trạng thái audio, khớp một-một với `AudioState` ở
 * `app/services/media_state.py`. Thêm trạng thái ở backend thì thêm ở đây.
 *
 * `stale` là cái đáng hiểu: clip có tồn tại nhưng được sinh từ một phiên bản cũ
 * của text, nên nó đọc sai từ. Với dictation thì nặng gấp đôi, vì transcript
 * đồng thời là đáp án chấm bài — học viên sẽ bị chấm theo một câu chưa từng
 * được nghe.
 */
export function AudioTag({ state }: { state: string }) {
  if (state === "current")
    return (
      <StatusTag tone="ok" icon={CircleCheck}>
        audio khớp
      </StatusTag>
    );
  if (state === "stale")
    return (
      <StatusTag tone="warn" icon={TriangleAlert}>
        audio đã cũ
      </StatusTag>
    );
  return (
    <StatusTag tone="alert" icon={CircleSlash}>
      chưa có audio
    </StatusTag>
  );
}

// --- khung trang ----------------------------------------------------------

export function Page({ className, ...props }: ComponentProps<"div">) {
  return (
    <div className={cx("mx-auto w-full max-w-5xl px-4 py-8 sm:py-12", className)} {...props} />
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-6">
      <div className="min-w-0">
        {eyebrow && <p className="text-label font-semibold uppercase text-action-ink">{eyebrow}</p>}
        <h1 className="mt-1.5">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Tiêu đề mục trong trang. Kẻ chỉ thay cho khoảng trống để phân đoạn. */
export function SectionHeader({ title, aside }: { title: string; aside?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-4 border-b border-rule pb-2">
      <h2 className="text-subtitle">{title}</h2>
      {aside}
    </div>
  );
}

// --- trạng thái -----------------------------------------------------------

/**
 * Trạng thái rỗng nói ra bước tiếp theo.
 *
 * "Không có dữ liệu" không nói gì mà người đọc chưa tự suy ra. Ở app này một
 * màn hình trống thường có nghĩa là một bước đã bị bỏ qua, chứ không phải có gì
 * hỏng — nên mỗi lần dùng đều kèm một hành động hoặc một lời giải thích.
 *
 * Căn TRÁI. Khối căn giữa trong hộp viền là mẫu hình dễ nhận ra nhất của giao
 * diện dựng sẵn, và nó cũng khó đọc hơn khi mô tả dài hơn một dòng.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Panel className="px-6 py-10">
      {Icon && <Icon size={20} strokeWidth={1.75} className="mb-3 text-ink-muted" aria-hidden />}
      <p className="text-subtitle font-semibold">{title}</p>
      {description && <p className="mt-1.5 max-w-lg text-small text-ink-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </Panel>
  );
}

const ALERT_TONES: Record<string, { className: string; Icon: LucideIcon }> = {
  alert: { className: "border-alert/40 bg-alert-tint text-alert", Icon: OctagonAlert },
  warn: { className: "border-warn/40 bg-warn-tint text-warn", Icon: TriangleAlert },
  ok: { className: "border-ok/40 bg-ok-tint text-ok", Icon: CircleCheck },
  info: { className: "border-rule-strong bg-recess text-ink-muted", Icon: Info },
};

/** Thông báo LUÔN có icon — màu một mình không đủ để phân biệt lỗi với xác nhận. */
export function Alert({
  tone = "alert",
  children,
}: {
  tone?: "alert" | "warn" | "ok" | "info";
  children: ReactNode;
}) {
  const { className, Icon } = ALERT_TONES[tone];
  return (
    <div
      role="alert"
      className={cx("flex gap-2.5 rounded border px-3.5 py-3 text-small", className)}
    >
      <Icon size={16} strokeWidth={1.75} className="mt-0.5 shrink-0" aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** Lỗi ngay dưới một ô nhập. Không bao giờ chỉ đổi màu viền (§9.5). */
export function FieldError({ children }: { children: ReactNode }) {
  return (
    <p className="mt-1.5 flex items-center gap-1.5 text-small text-alert">
      <CircleAlert size={14} strokeWidth={2} className="shrink-0" aria-hidden />
      {children}
    </p>
  );
}

/**
 * Khối có đúng hình dạng của nội dung sắp tới.
 *
 * Dùng thay cho chữ "Đang tải…" vì nó giữ layout khỏi nhảy khi dữ liệu về —
 * và layout nhảy là phần lớn cái làm một trang trông chưa xong.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded bg-recess", className)} />;
}

export function SkeletonList({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-16 w-full" />
      ))}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cx("h-4 w-4 shrink-0 animate-spin", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * Thang có vạch chia — ngôn ngữ hình thức của §10, thu nhỏ.
 *
 * Không phải thanh tiến trình bo tròn. Vạch chia đứng yên còn chỉ báo chạy trên
 * chúng, nên người đọc thấy được mình đang ở đâu TRÊN MỘT THANG chứ chỉ là một
 * dải màu dài ra. Bo góc 0 là chủ ý: vạch chia của thiết bị đo không bo tròn.
 */
export function Meter({
  value,
  max,
  label,
  ticks = 4,
}: {
  value: number;
  max: number;
  label?: string;
  ticks?: number;
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div>
      {label && (
        <div className="mb-1.5 flex items-baseline justify-between text-small text-ink-muted">
          <span>{label}</span>
          <span className="font-data text-ink">
            {value}
            <span className="text-ink-faint">/{max}</span>
          </span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        className="relative h-2 w-full rounded-none bg-recess"
      >
        <div
          className="h-full rounded-none bg-action transition-all"
          style={{ width: `${pct}%` }}
        />
        <div className="pointer-events-none absolute inset-0 flex justify-between">
          {Array.from({ length: ticks + 1 }, (_, index) => (
            <span key={index} className="w-px bg-panel/70" />
          ))}
        </div>
      </div>
    </div>
  );
}

// --- form -----------------------------------------------------------------

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-small font-semibold">{label}</span>
      {hint && <span className="mt-0.5 block text-small text-ink-muted">{hint}</span>}
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

/*
 * Viền dùng `rule-strong`, không phải `rule`.
 *
 * Đây là ranh giới của một component, nên WCAG 1.4.11 đòi tương phản 3:1. Hệ cũ
 * dùng `border-strong` = #D4D4D8 trên nền trắng = 1.48 — ranh giới ô nhập gần
 * như vô hình với người thị lực kém. Hai token này KHÔNG hoán đổi được cho nhau.
 */
const CONTROL =
  "w-full rounded border border-rule-strong bg-panel px-3 py-2 text-body text-ink " +
  "placeholder:text-ink-faint disabled:cursor-not-allowed disabled:bg-recess disabled:opacity-70";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cx(CONTROL, "h-9", className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return <textarea className={cx(CONTROL, "resize-y", className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cx(CONTROL, "h-9", className)} {...props} />;
}

/** Phím tắt hiển thị trong giao diện. */
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-rule-strong px-1.5 py-px font-data text-[0.625rem] text-ink-muted">
      {children}
    </kbd>
  );
}
