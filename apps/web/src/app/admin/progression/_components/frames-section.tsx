"use client";

import { API_ROUTES, type FrameTierAdmin } from "@toeic-pilot/shared";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button, Field, Input, Panel, SectionHeader, Select } from "@/components/ui";
import { type SendFn, type UploadFn, type SectionProps, ArtControl, NumberField } from "./shared";

/**
 * Mục KHUNG AVATAR.
 *
 * `tone` là tập đóng của token thiết kế, không phải ô nhập hex tự do: một mã màu
 * tự chọn là đường ngắn nhất tới một khung vô hình ở nền tối, nơi không ai kiểm
 * trước khi lưu.
 */

const TONES: FrameTierAdmin["tone"][] = ["ok", "action", "warn", "alert"];

export function FramesSection({ config, setConfig, busy, send, upload }: SectionProps) {
  const [draft, setDraft] = useState<FrameTierAdmin>({
    code: "",
    label: "",
    min_level: 40,
    tone: "action",
    ring: false,
    // Tranh gắn SAU khi tạo, không phải lúc tạo: file phải tồn tại trên kho
    // trước khi khoá được ghi, nên đính kèm ngay trong biểu mẫu tạo sẽ là hai
    // thao tác mạng cột vào một nút và một nửa thất bại không có đường lùi.
    image_storage_key: null,
    image_url: null,
  });

  return (
    <section className="mt-8">
      <SectionHeader title="Avatar frames" />
      <Panel className="p-5 sm:p-6">
        <p className="text-small text-ink-muted">
          Purely decorative. Colours are design-system tokens, never hex — every token ships a dark
          variant, so a frame cannot become invisible in one theme.
        </p>

        <ul className="mt-4 space-y-2">
          {config.frames.map((frame, index) => (
            <FrameRow
              key={frame.code}
              frame={frame}
              busy={busy}
              send={send}
              upload={upload}
              onChange={(next) => {
                const frames = [...config.frames];
                frames[index] = next;
                setConfig({ ...config, frames });
              }}
            />
          ))}
        </ul>

        <div className="mt-5 border-t border-rule pt-4">
          <p className="text-label font-semibold uppercase text-ink-faint">Add a tier</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Field label="Code" hint="Lowercase, permanent.">
              <Input
                value={draft.code}
                placeholder="diamond"
                onChange={(event) => setDraft({ ...draft, code: event.target.value })}
              />
            </Field>
            <Field label="Label">
              <Input
                value={draft.label}
                placeholder="Kim cương"
                onChange={(event) => setDraft({ ...draft, label: event.target.value })}
              />
            </Field>
            <NumberField
              label="From level"
              value={draft.min_level}
              onChange={(min_level) => setDraft({ ...draft, min_level })}
            />
            <Field label="Tone">
              <Select
                value={draft.tone}
                onChange={(event) =>
                  setDraft({ ...draft, tone: event.target.value as FrameTierAdmin["tone"] })
                }
              >
                {TONES.map((tone) => (
                  <option key={tone} value={tone}>
                    {tone}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex items-end">
              <Button
                disabled={busy || draft.code.trim() === "" || draft.label.trim() === ""}
                onClick={async () => {
                  await send(API_ROUTES.adminProgressionFrames, "POST", draft);
                  setDraft({ ...draft, code: "", label: "" });
                }}
              >
                <Plus size={16} strokeWidth={2} aria-hidden />
                Add
              </Button>
            </div>
          </div>
        </div>
      </Panel>
    </section>
  );
}

function FrameRow({
  frame,
  busy,
  send,
  upload,
  onChange,
}: {
  frame: FrameTierAdmin;
  busy: boolean;
  send: SendFn;
  upload: UploadFn;
  onChange: (next: FrameTierAdmin) => void;
}) {
  const attachArt = async (file: File) => {
    const key = await upload(file);
    if (key)
      await send(API_ROUTES.adminProgressionFrame(frame.code), "PATCH", {
        image_storage_key: key,
      });
  };
  // Hàng có KIỂM SOÁT: sự thật nằm ở bản nháp của trang, không phải ở đây.
  const form = frame;
  const setForm = onChange;

  return (
    <li className="grid items-end gap-3 rounded border border-rule-strong p-3 sm:grid-cols-2 lg:grid-cols-7">
      <Field label="Code">
        <Input value={form.code} disabled />
      </Field>
      <Field label="Label">
        <Input
          value={form.label}
          onChange={(event) => setForm({ ...form, label: event.target.value })}
        />
      </Field>
      <NumberField
        label="From level"
        value={form.min_level}
        onChange={(min_level) => setForm({ ...form, min_level })}
      />
      <Field label="Tone">
        <Select
          value={form.tone}
          onChange={(event) =>
            setForm({ ...form, tone: event.target.value as FrameTierAdmin["tone"] })
          }
        >
          {TONES.map((tone) => (
            <option key={tone} value={tone}>
              {tone}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Art">
        <ArtControl
          url={frame.image_url}
          busy={busy}
          onPick={(file) => void attachArt(file)}
          onClear={() =>
            void send(API_ROUTES.adminProgressionFrame(frame.code), "PATCH", {
              image_storage_key: null,
            })
          }
        />
      </Field>
      <Field label="Outer ring">
        <Select
          value={form.ring ? "yes" : "no"}
          onChange={(event) => setForm({ ...form, ring: event.target.value === "yes" })}
        >
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </Select>
      </Field>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          disabled={busy}
          onClick={() =>
            send(API_ROUTES.adminProgressionFrame(frame.code), "PATCH", {
              label: form.label,
              min_level: form.min_level,
              tone: form.tone,
              ring: form.ring,
            })
          }
        >
          Save
        </Button>
        <Button
          size="sm"
          variant="quiet"
          disabled={busy}
          onClick={() => send(API_ROUTES.adminProgressionFrame(frame.code), "DELETE")}
        >
          <Trash2 size={16} strokeWidth={2} aria-hidden />
        </Button>
      </div>
    </li>
  );
}
