"use client";

import { type SetAdmin, type TurnDraft, type VoiceOption } from "@toeic-pilot/shared";

import { Panel, PublishTag, cx } from "@/components/ui";
import { AudioPanel } from "./audio-panel";
import { ImageUpload } from "./image-upload";

/** Cụm Part 3/4/6/7: ngữ liệu, ảnh của ngữ liệu, và lời thoại dùng chung. */

export function SetPanel({
  stimulus,
  busy,
  onUploadImage,
  onRemoveImage,
  blocked,
  onUploadAudio,
  onSaveScript,
  voices,
  allowImages,
}: {
  stimulus: SetAdmin;
  busy: boolean;
  onUploadImage: (slot: number, file: File, alt: string | null) => Promise<string | null>;
  onRemoveImage: (slot: number) => Promise<string | null>;
  blocked: string | null;
  onUploadAudio: (file: File) => void;
  onSaveScript: (script: TurnDraft[]) => Promise<string | null>;
  voices: VoiceOption[];
  allowImages: boolean;
}) {
  // Part 6 chỉ có MỘT đoạn văn; hiện ba ô là mô tả sai format, và nó mời người
  // soạn điền vào hai ô không tồn tại trong đề thật.
  // Ba hình dạng, không phải hai. Part 7: tối đa ba ngữ liệu, chữ và ảnh. Part
  // 6: **một** đoạn văn, toàn chữ. Part 3/4: **một** hình dùng chung cho cả cụm
  // ("Look at the graphic") và không in chữ nào — nên hiện ô văn bản ở đó là mô
  // tả sai format và mời người soạn gõ vào chỗ đề thật để trống.
  const graphic = stimulus.part === 3 || stimulus.part === 4;
  const slots = allowImages ? stimulus.passages : stimulus.passages.slice(0, 1);

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-semibold">{stimulus.title ?? "Cụm không tên"}</p>
        <PublishTag status={stimulus.status} />
      </div>

      {!allowImages && stimulus.part <= 4 && (
        <AudioPanel
          script={stimulus.audio_script}
          audioUrl={stimulus.audio_url ?? null}
          stale={stimulus.audio_may_be_stale}
          attachedAt={stimulus.audio_attached_at ?? null}
          busy={busy}
          voices={voices}
          onUpload={onUploadAudio}
          onSaveScript={onSaveScript}
        />
      )}

      <div className={cx("mt-3 space-y-3", stimulus.part <= 2 && "hidden")}>
        {slots.map((passage) => (
          <div key={passage.slot} className="rounded border border-rule p-3">
            <p className="text-label font-semibold uppercase text-ink-muted">
              {graphic ? "Hình đi kèm" : `Ngữ liệu ${passage.slot}`}
            </p>

            {!graphic &&
              (passage.text ? (
                <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-small text-ink-muted">
                  {passage.text}
                </p>
              ) : (
                <p className="mt-1 text-small text-ink-faint">— không có văn bản —</p>
              ))}

            {passage.image_url && (
              <div className="mt-2 flex items-start gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={passage.image_url}
                  alt={passage.image_alt ?? ""}
                  className="h-20 w-28 rounded border border-rule object-cover"
                />
                <p className="min-w-0 flex-1 text-small text-ink-muted">{passage.image_alt}</p>
              </div>
            )}

            {(allowImages || graphic) && (
              <ImageUpload
                busy={busy}
                hasImage={passage.image_url !== null}
                // Ngược hẳn Part 1: ở đây ảnh LÀ ngữ liệu, nên thiếu chữ thay
                // ảnh là một câu người dùng máy đọc màn hình không làm được — mà
                // mô tả nó cũng không lộ gì, vì vẫn phải nghe (Part 3/4) hoặc
                // vẫn phải đọc phần còn lại (Part 7).
                needsAlt
                blocked={blocked}
                onUpload={(file, alt) => onUploadImage(passage.slot, file, alt)}
                onRemove={() => onRemoveImage(passage.slot)}
              />
            )}
          </div>
        ))}
      </div>

      {/* Nói ra ngay tại chỗ, vì đây là chỗ người ta sắp làm sai: phần lớn ngữ
          liệu KHÔNG cần ảnh, và bản văn bản thì tốt hơn thật. */}
      <p className={cx("mt-3 text-small text-ink-muted", stimulus.part <= 2 && "hidden")}>
        {graphic
          ? "Chỉ vài cụm cuối Part 3/4 có hình. Chữ thay ảnh là bắt buộc và không lộ đáp án ở đây — người học vẫn phải nghe mới trả lời được."
          : allowImages
            ? "Bảng giá, lịch trình, mẫu đơn nên viết thành văn bản — đọc được bằng máy đọc màn hình, phóng to và tìm kiếm được. Ảnh dành cho biểu đồ, sơ đồ, bản đồ."
            : "Part 6 là một đoạn văn có các chỗ trống, mỗi chỗ trống là một câu hỏi. Không có ảnh và không có bài nhiều đoạn."}
      </p>
    </Panel>
  );
}
