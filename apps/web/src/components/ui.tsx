/**
 * The small set of pieces every page is built from.
 *
 * It exists because the first version of these screens hand-rolled the same
 * button and the same bordered box a dozen times, each slightly different — and
 * a design that is re-decided per page is not a design. Anything used on more
 * than one screen belongs here.
 */

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

// --- button ---------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white hover:bg-brand-hover shadow-sm",
  secondary: "border border-border-strong bg-surface-raised hover:bg-surface-sunken",
  ghost: "hover:bg-surface-sunken text-text-muted hover:text-text",
  danger: "bg-danger text-white hover:opacity-90 shadow-sm",
  success: "bg-success text-white hover:opacity-90 shadow-sm",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

function buttonClass(variant: Variant, size: Size, className?: string) {
  return cx(
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
    // Disabled buttons stay visible rather than vanishing: on the admin screens
    // the disabled Publish button is the message — it says the item is not ready.
    "disabled:cursor-not-allowed disabled:opacity-40",
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

// --- surfaces -------------------------------------------------------------

export function Card({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cx("rounded-xl border border-border bg-surface-raised shadow-sm", className)}
      {...props}
    />
  );
}

export function CardLink({ className, ...props }: ComponentProps<typeof Link>) {
  return (
    <Link
      className={cx(
        "block rounded-xl border border-border bg-surface-raised p-5 shadow-sm transition-all",
        "hover:-translate-y-0.5 hover:border-brand hover:shadow-md",
        className,
      )}
      {...props}
    />
  );
}

// --- labels ---------------------------------------------------------------

type Tone = "neutral" | "brand" | "success" | "warning" | "danger";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-sunken text-text-muted border-border",
  brand: "bg-brand-soft text-brand-text border-transparent",
  success: "bg-success-soft text-success border-transparent",
  warning: "bg-warning-soft text-warning border-transparent",
  danger: "bg-danger-soft text-danger border-transparent",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: ComponentProps<"span"> & { tone?: Tone }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

// --- page furniture -------------------------------------------------------

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
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-text">
            {eyebrow}
          </p>
        )}
        <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-text-muted">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </header>
  );
}

// --- states ---------------------------------------------------------------

/**
 * An empty state that says what to do next.
 *
 * "No data" tells the reader nothing they had not already worked out. Every use
 * of this takes an action or an explanation, because an empty screen in this app
 * usually means a step was missed rather than that something is broken.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Card className="flex flex-col items-center px-6 py-14 text-center">
      {icon && <div className="mb-4 text-4xl opacity-60">{icon}</div>}
      <p className="text-lg font-medium">{title}</p>
      {description && <p className="mt-2 max-w-md text-sm text-text-muted">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </Card>
  );
}

export function Alert({
  tone = "danger",
  children,
}: {
  tone?: "danger" | "warning" | "success" | "brand";
  children: ReactNode;
}) {
  const tones = {
    danger: "border-danger/30 bg-danger-soft text-danger",
    warning: "border-warning/30 bg-warning-soft text-warning",
    success: "border-success/30 bg-success-soft text-success",
    brand: "border-brand/30 bg-brand-soft text-brand-text",
  };
  return (
    <div role="alert" className={cx("rounded-lg border px-4 py-3 text-sm", tones[tone])}>
      {children}
    </div>
  );
}

/**
 * A block the shape of the content that is coming.
 *
 * Preferred over the word "Loading…" because it keeps the layout from jumping
 * when the data lands, which is most of what makes a page feel unfinished.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-md bg-surface-sunken", className)} />;
}

export function SkeletonList({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-16 w-full" />
      ))}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cx("h-4 w-4 animate-spin", className)}
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

// --- forms ----------------------------------------------------------------

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
      <span className="text-sm font-medium">{label}</span>
      {hint && <span className="mt-0.5 block text-xs text-text-muted">{hint}</span>}
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

const CONTROL =
  "w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm " +
  "placeholder:text-text-subtle disabled:opacity-60";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cx(CONTROL, "h-10", className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return <textarea className={cx(CONTROL, "resize-y", className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cx(CONTROL, "h-10", className)} {...props} />;
}
