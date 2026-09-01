"use client";

import { type TurnDraft, type VoiceOption } from "@toeic-pilot/shared";
import { Pencil, Plus, Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { Button, FieldError, Select, Textarea } from "@/components/ui";

/**
 * Lời thoại và bản thu của một câu hay một cụm.
 *
 * Nút sinh audio chỉ BẤM CHUÔNG chứ không sinh audio: API không tổng hợp được
 * (PHASE2-AUDIO §A4.1), nên nó trả 202 và worker ngoài luồng làm việc. Bấm mười
 * lần không tạo ra mười việc — hàng đợi vẫn là câu hỏi "cái gì còn thiếu audio".
 */

/**
 * Lời thoại và bản thu của một câu (Part 1, 2) hoặc một cụm (Part 3, 4).
 *
 * Lời thoại hiện ra ngay cạnh nút tải lên, vì đó là thứ người soạn phải đối
 * chiếu: `media_state` KHÔNG xác minh được audio tải lên — hash của nó băm một
 * id ngẫu nhiên nên không suy ngược ra text — nên mắt người là lớp kiểm duy
 * nhất còn lại (ADR-007 §2.7).
 *
 * Và nó phải SỬA được ngay tại đây. Không có ô sửa thì sai một chữ chỉ còn cách
 * xoá cả cụm rồi dán lại — kéo theo mất số câu đã cấp và bản thu đã gắn.
 */
export function AudioPanel({
  script,
  audioUrl,
  stale,
  attachedAt,
  busy,
  voices,
  onUpload,
  onSaveScript,
}: {
  script: TurnDraft[];
  audioUrl: string | null;
  stale: boolean;
  attachedAt: string | null;
  busy: boolean;
  voices: VoiceOption[];
  onUpload: (file: File) => void;
  onSaveScript: (script: TurnDraft[]) => Promise<string | null>;
}) {
  // `null` nghĩa là không sửa. Một cờ boolean riêng cạnh bản nháp sẽ có hai
  // nguồn sự thật cho cùng một câu hỏi, và chúng lệch nhau được.
  const [draft, setDraft] = useState<TurnDraft[] | null>(null);
  // Lời từ chối của lần lưu gần nhất, in ngay dưới nút Lưu. Băng lỗi chung ở
  // đầu trang vẫn hiện, nhưng nó cách chỗ này cả màn hình.
  const [refusal, setRefusal] = useState<string | null>(null);
  const fallbackVoice = voices[0]?.name ?? "us_female_1";

  const patch = (index: number, turn: Partial<TurnDraft>) =>
    setDraft((current) =>
      (current ?? []).map((item, at) => (at === index ? { ...item, ...turn } : item)),
    );

  async function save() {
    if (!draft) return;
    // Đóng CHỈ khi server đã nhận. Giọng sai hay lượt rỗng đều bị từ chối ở
    // server, và lời từ chối đó vô dụng nếu ô nhập đã biến mất cùng nội dung.
    const problem = await onSaveScript(draft);
    setRefusal(problem);
    if (problem === null) setDraft(null);
  }

  return (
    <div className="mt-3 rounded border border-rule p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-label font-semibold uppercase text-ink-muted">Lời thoại</p>
        {draft === null && (
          <Button
            size="sm"
            variant="quiet"
            onClick={() => {
              setRefusal(null);
              setDraft(script.map((t) => ({ ...t })));
            }}
          >
            <Pencil size={14} strokeWidth={1.75} aria-hidden />
            Sửa
          </Button>
        )}
      </div>

      {draft === null ? (
        script.length === 0 ? (
          <p className="mt-1 text-small text-ink-faint">— chưa có lời thoại —</p>
        ) : (
          <ul className="mt-1.5 space-y-1">
            {script.map((turn, index) => (
              <li key={index} className="text-small">
                <span className="font-data text-label text-ink-faint">{turn.voice}</span>{" "}
                {turn.text}
              </li>
            ))}
          </ul>
        )
      ) : (
        <div className="mt-2 space-y-2">
          {draft.map((turn, index) => (
            <div key={index} className="flex items-start gap-2">
              {/* Bề rộng đặt ở lớp bọc, không đặt lên chính control: `CONTROL`
                  đã có `w-full`, và hai lớp width cùng tồn tại thì thứ tự trong
                  file CSS quyết định chứ không phải thứ tự viết ở đây — nên
                  `w-40` trên `<Select>` thua im lặng và ô nhập bị bóp còn vài
                  pixel. */}
              <div className="w-44 shrink-0">
                <Select
                  value={turn.voice}
                  aria-label={`Giọng của lượt ${index + 1}`}
                  onChange={(event) => patch(index, { voice: event.target.value })}
                >
                  {/* Giọng hiện tại luôn có mặt, kể cả khi nó đã bị gỡ khỏi danh
                    sách: một option biến mất sẽ lặng lẽ đổi giọng của lượt này
                    sang giọng đầu bảng khi người ta lưu. */}
                  {!voices.some((voice) => voice.name === turn.voice) && (
                    <option value={turn.voice}>{turn.voice}</option>
                  )}
                  {/* Dấu ★ đánh dấu bốn giọng của dàn narrator đề thật. Bốn
                    giọng còn lại vẫn dùng được — chúng chỉ là những cặp quốc
                    tịch–giới tính bài thi không có, và cái tên không nói ra
                    điều đó. */}
                  {voices.map((voice) => (
                    <option key={voice.name} value={voice.name}>
                      {voice.narrator ? "★ " : ""}
                      {voice.name} · {voice.accent}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="min-w-0 flex-1">
                <Textarea
                  rows={2}
                  value={turn.text}
                  aria-label={`Lời của lượt ${index + 1}`}
                  onChange={(event) => patch(index, { text: event.target.value })}
                />
              </div>
              <Button
                size="sm"
                variant="quiet"
                aria-label={`Xoá lượt ${index + 1}`}
                onClick={() => setDraft(draft.filter((_, at) => at !== index))}
              >
                <Trash2 size={14} strokeWidth={1.75} aria-hidden />
              </Button>
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="quiet"
              onClick={() => setDraft([...draft, { text: "", voice: fallbackVoice }])}
            >
              <Plus size={14} strokeWidth={1.75} aria-hidden />
              Thêm lượt
            </Button>
            <Button size="sm" onClick={() => void save()} disabled={busy}>
              Lưu lời thoại
            </Button>
            <Button
              size="sm"
              variant="quiet"
              onClick={() => {
                setRefusal(null);
                setDraft(null);
              }}
              disabled={busy}
            >
              Huỷ
            </Button>
          </div>
          {refusal ? (
            <FieldError>{refusal}</FieldError>
          ) : (
            <p className="text-small text-ink-faint">
              Lưu xong, nội dung quay về nháp — bản thu đang gắn ứng với lời thoại cũ.
            </p>
          )}
        </div>
      )}

      {audioUrl ? (
        <audio src={audioUrl} controls preload="metadata" className="mt-3 w-full" />
      ) : (
        <p className="mt-3 text-small text-warn">Chưa có bản thu — chưa xuất bản được.</p>
      )}

      {/* Cảnh báo chứ không chặn. Hash của file tải lên không suy ngược ra lời
          thoại, nên không có cách nào biết CHẮC là nó lệch — chỉ biết lời thoại
          đã đổi kể từ lúc gắn, và nói ra điều đó vẫn hơn im lặng. */}
      {stale && (
        <p className="mt-2 text-small text-warn">
          Lời thoại đã đổi sau khi gắn bản thu
          {attachedAt && ` (gắn lúc ${new Date(attachedAt).toLocaleString("vi-VN")})`} — nghe lại
          hoặc thu lại cho khớp.
        </p>
      )}

      <label className="mt-3 inline-flex cursor-pointer items-center gap-2 text-small font-semibold text-action-ink">
        <Upload size={14} strokeWidth={2} aria-hidden />
        {audioUrl ? "Thay bản thu" : "Tải bản thu lên"}
        <input
          type="file"
          accept="audio/mpeg,audio/mp4,audio/wav,.mp3,.m4a,.wav"
          disabled={busy}
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Xoá giá trị để chọn LẠI cùng một file vẫn kích hoạt onChange —
            // thứ người ta làm ngay sau khi một lần tải lên thất bại.
            event.target.value = "";
            if (file) onUpload(file);
          }}
        />
      </label>
    </div>
  );
}
