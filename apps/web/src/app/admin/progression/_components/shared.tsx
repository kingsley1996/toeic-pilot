"use client";

import { type ProgressionConfigAdmin } from "@toeic-pilot/shared";
import { Image as ImageIcon } from "lucide-react";
import { useRef } from "react";

import { Button, Field, Input } from "@/components/ui";

/** Điều khiển và kiểu dùng chung cho các mục của trang cấu hình thăng tiến. */

export type SendFn = (path: string, method: string, body?: unknown) => Promise<void>;

export type UploadFn = (file: File) => Promise<string | null>;

export type SectionProps = {
  config: ProgressionConfigAdmin;
  setConfig: (next: ProgressionConfigAdmin) => void;
  busy: boolean;
  send: SendFn;
  upload: UploadFn;
};

/**
 * Upload art for one frame or badge, then hand the key to the row's PATCH.
 *
 * The upload and the attach are two steps on purpose: the file has to exist on
 * the provider before its key can be written, because the PATCH verifies it.
 * Doing both from one button is fine — what is not fine is writing the key
 * first and hoping, which is how a broken image ends up in the database and
 * stays there until somebody happens to look at a frame.
 */
export function ArtControl({
  url,
  busy,
  onPick,
  onClear,
}: {
  url: string | null;
  busy: boolean;
  onPick: (file: File) => void;
  onClear: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center gap-2">
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt=""
          className="h-9 w-9 shrink-0 rounded border border-rule object-contain"
        />
      ) : (
        <span
          aria-hidden
          className="grid h-9 w-9 shrink-0 place-items-center rounded border border-dashed border-rule-strong text-ink-faint"
        >
          <ImageIcon size={14} strokeWidth={1.75} />
        </span>
      )}
      <input
        ref={input}
        type="file"
        accept="image/png,image/webp,image/jpeg"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onPick(file);
          // Cho phép chọn LẠI cùng một file: không xoá giá trị thì `change`
          // không bắn lần thứ hai, và nút trông như hỏng.
          event.target.value = "";
        }}
      />
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => input.current?.click()}>
        {url ? "Replace" : "Upload"}
      </Button>
      {url && (
        <Button size="sm" variant="quiet" disabled={busy} onClick={onClear}>
          Clear
        </Button>
      )}
    </div>
  );
}

/** A row of small labelled number inputs. */
export function NumberField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <Field label={label} hint={hint}>
      <Input
        type="number"
        value={String(value)}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </Field>
  );
}
