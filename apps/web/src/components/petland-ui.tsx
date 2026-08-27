"use client";

import { PixelIcon, type PixelIconName } from "@/components/pixel-icon";
import { whyUnavailable, type PetAction, type PetNeeds } from "@/components/petland-pet";
import { cx } from "@/components/ui";

/*
 * Giao diện tương tác với con thú.
 *
 * Tệp này cố ý KHÔNG biết con thú trông thế nào, đứng ở đâu, hay khung cảnh là
 * gì — nó chỉ nhận ba chỉ số và gửi lại một hành động. Đổi mascot hay đổi bối
 * cảnh không chạm vào đây; đó là lý do nó là một tệp riêng chứ không phải vài
 * dòng JSX nằm trong `petland.tsx`.
 *
 * Đồ hoạ theo phong cách pixel: biểu tượng vẽ từ lưới ký tự
 * (`pixel-icon.tsx`), và thanh chỉ số là các Ô RỜI chứ không phải một vạch liền
 * — một thanh bo tròn chạy mượt sẽ cãi nhau với chính phong cách đó.
 */

/*
 * Phím tắt nằm trong `title` của chính cái nút, không nằm ở một hàng gợi ý riêng.
 * Hàng gợi ý là thứ chiếm chỗ ngang bằng cả một cái nút để nói về những cái nút
 * bên cạnh nó, và ở bề rộng này nó đẩy cả hàng xuống dòng.
 */
const ACTIONS: Array<{ action: PetAction; icon: PixelIconName; label: string; key?: string }> = [
  { action: "feed", icon: "bone", label: "Cho ăn", key: "F" },
  { action: "poke", icon: "hand", label: "Chọc", key: "Space" },
  { action: "walk", icon: "paw", label: "Đi dạo" },
  { action: "sleep", icon: "zzz", label: "Ngủ" },
];

const NEEDS: Array<{ key: keyof PetNeeds; label: string; short: string }> = [
  { key: "fullness", label: "Độ no", short: "No" },
  { key: "energy", label: "Sức", short: "Sức" },
  { key: "mood", label: "Vui", short: "Vui" },
];

const SEGMENTS = 8;

/**
 * Thanh chỉ số kiểu pixel: tám ô rời.
 *
 * Làm tròn LÊN cho mọi giá trị khác 0, cùng lý do với thanh tiến độ từ vựng ở
 * dashboard: 1/8 là 12.5%, nên một chỉ số còn 4% sẽ làm tròn xuống thành rỗng và
 * nói sai rằng con thú đã kiệt — trong khi số bên cạnh vẫn báo là còn.
 */
function NeedBar({ value, tone }: { value: number; tone: string }) {
  const filled = value <= 0 ? 0 : Math.max(1, Math.ceil(value * SEGMENTS));
  return (
    <span className="flex gap-px" aria-hidden>
      {Array.from({ length: SEGMENTS }, (_, i) => (
        <span
          key={i}
          className={cx("h-2 w-1.5", i < filled ? tone : "bg-rule")}
          style={{ borderRadius: 0 }}
        />
      ))}
    </span>
  );
}

/* Màu là TÍN HIỆU, nên nó chỉ đổi khi có điều đáng báo. Ba mức chứ không phải
   một dải liên tục: "sắp hết" là một trạng thái, không phải một sắc độ. */
function toneFor(value: number): string {
  if (value < 0.2) return "bg-alert";
  if (value < 0.45) return "bg-warn";
  return "bg-ok";
}

export function PetHud({
  needs,
  busy,
  asleep,
  onAction,
  leading,
}: {
  needs: PetNeeds;
  /**
   * Con thú đang ngủ.
   *
   * Lúc ngủ, ba nút kia MỜ ĐI kèm lý do chứ không tự đánh thức: một cú bấm nhầm
   * mà xoá mất hai tiếng hồi sức là thứ người dùng không lường trước và cũng
   * không hoàn lại được. Nút "Ngủ" thì đổi thành "Đánh thức" — cùng một chỗ trên
   * màn hình, nên không phải đi tìm.
   */
  asleep: boolean;
  /** Có hành động đang gửi đi — khoá nút trong lúc đó. */
  busy: boolean;
  onAction: (action: PetAction) => void;
  /*
   * Hai chỗ cắm cho những điều khiển KHÔNG thuộc về con thú: nút đi trái/phải
   * lái nó trong khung cảnh, và gợi ý phím tắt. Chúng nhận vào dưới dạng nút chứ
   * không được vẽ ở đây, vì cả hai đều nói về khung cảnh — thứ sẽ đổi — trong
   * khi tệp này thì không được biết khung cảnh là gì.
   */
  leading?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 px-3 py-2">
      <div className="flex items-center gap-3">
        {NEEDS.map(({ key, label, short }) => (
          <span key={key} className="flex items-center gap-1.5" title={label}>
            <span className="font-data text-label uppercase tracking-wide text-ink-faint">
              {short}
            </span>
            <NeedBar value={needs[key]} tone={toneFor(needs[key])} />
            {/* Số phần trăm cố ý KHÔNG hiện: nó gợi ra một độ chính xác không có
                thật, và không giúp quyết định gì hơn tám cái ô. */}
            <span className="sr-only">{Math.round(needs[key] * 100)}%</span>
          </span>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {leading}
        {ACTIONS.map(({ action, icon, label, key }) => {
          const sleepButton = action === "sleep";
          const shown = sleepButton && asleep ? "Đánh thức" : label;
          const sent = sleepButton && asleep ? "wake" : action;
          // Đang ngủ thì mọi nút trừ nút đánh thức đều mờ, và lý do nói đúng
          // chuyện đang xảy ra chứ không phải chuyện chỉ số.
          const why = asleep
            ? sleepButton
              ? null
              : "Nó đang ngủ, để nó ngủ đã."
            : whyUnavailable(needs, action);
          const blocked = busy || why !== null;
          return (
            <button
              key={action}
              type="button"
              disabled={blocked}
              onClick={() => onAction(sent)}
              // Lý do bị chặn nằm ở `title` chứ không chỉ ở việc nút mờ đi: một
              // cái nút mờ mà không nói vì sao chỉ để lại người dùng đoán.
              title={why ?? (key ? `${shown} (${key})` : shown)}
              aria-label={why ? `${shown} — ${why}` : shown}
              className={cx(
                "inline-flex h-8 items-center gap-1.5 rounded border border-rule-strong px-2 text-small text-ink transition-colors",
                blocked ? "opacity-45" : "hover:bg-recess",
              )}
            >
              <PixelIcon name={icon} scale={2} />
              <span className="hidden sm:inline">{shown}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export type Bit = {
  id: number;
  x: number;
  y: number;
  icon: PixelIconName;
  drift: number;
  /*
   * Cỡ được CHỐT lúc mẩu sinh ra, không đọc theo con thú lúc vẽ. Một mẩu bay ra
   * ở giữa cầu (phối cảnh 0.57) mà lấy cỡ theo chỗ con thú đang đứng sẽ phình
   * to dần trong lúc con thú đi về phía trước — nó đã rời khỏi con thú rồi.
   */
  scale: number;
};

/**
 * Những mẩu bay lên khi con thú được cho ăn hoặc bị chọc.
 *
 * Chúng là phần tử DOM chứ không vẽ lên canvas hiệu ứng của khung cảnh, và đó là
 * chủ ý: canvas kia thuộc về BỐI CẢNH (mặt nước, đống lửa, sao) và sẽ bị thay
 * cùng bức tranh. Phản hồi khi tương tác thì thuộc về con thú, nên nó phải sống
 * ở lớp không bị thay.
 */
export function PixelBits({ bits }: { bits: Bit[] }) {
  return (
    <>
      {bits.map((b) => (
        <span
          key={b.id}
          aria-hidden
          className="pet-bit pointer-events-none absolute"
          style={{
            left: b.x,
            top: b.y,
            // `--bit-drift` để mỗi mẩu bay lệch một hướng: cả nắm bay thẳng đứng
            // song song nhau đọc ra là một hiệu ứng, không phải nhiều mẩu.
            ["--bit-drift" as string]: `${b.drift}px`,
            transform: `scale(${b.scale})`,
            transformOrigin: "center bottom",
          }}
        >
          <PixelIcon name={b.icon} scale={2} />
        </span>
      ))}
    </>
  );
}
