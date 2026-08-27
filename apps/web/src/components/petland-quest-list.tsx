"use client";

import type { EncounterPublic } from "@toeic-pilot/shared";
import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { tileForGuest } from "@/components/petland-bestiary";
import { clock, secondsLeft } from "@/components/petland-countdown";
import { Creature } from "@/components/petland-creature";
import { cx } from "@/components/ui";

/**
 * Danh sách những vị khách cùng loại đang đứng trên bản đồ.
 *
 * Tồn tại vì bản đồ nhỏ và bốn người có thể đứng chen nhau: bấm trúng một sprite
 * cao mười sáu pixel là chuyện may rủi, nhất là khi con thú đi qua che mất một
 * người. Đây là đường LUÔN tới được, cùng vai trò mà cái nút ở thanh tiêu đề
 * vẫn giữ — chỉ khác là giờ nó dẫn tới một danh sách chứ không đoán hộ người
 * dùng muốn mở ai.
 *
 * **Đồng hồ đếm ngược là thứ đáng giá nhất ở đây.** Một cuộc chạm mặt sống mười
 * phút rồi biến mất không báo trước; không thấy con số ấy thì người học không có
 * cách nào biết nên làm cái nào trước, và cái họ chọn sai sẽ tan đi giữa chừng.
 */

const TASK_LABEL: Record<string, string> = {
  typing: "Gõ lại từ",
  choice: "Chọn nghĩa",
  dictation: "Nghe chép",
};

export function GuestList({
  meetings,
  kind,
  activeId,
  onPick,
  onClose,
}: {
  meetings: EncounterPublic[];
  kind: "npc" | "intruder";
  activeId: string | null;
  onPick: (id: string) => void;
  onClose: () => void;
}) {
  /*
   * Nhịp một giây, sống trong CHÍNH component này.
   *
   * Để nó ở bảng ngoài thì mỗi giây là một lần dựng lại cả bảng, kèm canvas Pixi
   * bên trong — đúng lý do vị trí bảng và bong bóng thoại đều ghi thẳng vào
   * `style` thay vì đi qua state. Ở đây thì phạm vi dựng lại chỉ là mấy dòng
   * danh sách, và chúng phải dựng lại thật vì con số trên chúng đang đổi.
   */
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(tick);
  }, []);

  const danger = kind === "intruder";
  const rows = meetings.filter((one) => one.kind === kind);

  return (
    <div className="max-h-[35vh] w-full shrink-0 overflow-y-auto border-t border-rule p-3 sm:h-[var(--pet-map-h)] sm:max-h-none sm:w-[var(--pet-egg-w)] sm:border-l sm:border-t-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className={cx("text-small font-semibold", danger ? "text-alert" : "text-warn")}>
          {danger ? "Kẻ xâm nhập" : "Người cần giúp"}
          <span className="ml-2 font-data font-normal tabular-nums text-ink-muted">
            {rows.length}
          </span>
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Đóng danh sách"
          className="grid h-6 w-6 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink"
        >
          <X size={14} strokeWidth={2} aria-hidden />
        </button>
      </div>

      {rows.length === 0 ? (
        <p className="mt-3 text-small text-ink-muted">Không còn ai. Chờ một lát nhé.</p>
      ) : (
        <ul className="mt-2 grid gap-1.5">
          {rows.map((one) => {
            const left = secondsLeft(one.expires_at, now);
            return (
              <li key={one.id}>
                <button
                  type="button"
                  onClick={() => onPick(one.id)}
                  aria-current={one.id === activeId}
                  className={cx(
                    "w-full rounded border px-2 py-1.5 text-left transition-colors",
                    one.id === activeId
                      ? "border-rule-strong bg-recess"
                      : "border-rule-strong hover:bg-recess",
                  )}
                >
                  <span className="flex items-center gap-2">
                    {/* Cùng con vật đang đứng trên bản đồ — `tileForGuest` là
                        một hàm chung, không phải hai phép tính giống nhau. Không
                        có nó thì danh sách in một con còn bản đồ vẽ một con
                        khác, và người dùng không nối được dòng này với ai. */}
                    <Creature
                      tile={tileForGuest(one.id, danger ? "intruder" : "npc")}
                      size={24}
                      className="shrink-0 rounded border border-rule"
                    />
                    <span className="flex-1 text-small text-ink">
                      {TASK_LABEL[one.task.mode] ?? "Nhiệm vụ"}
                    </span>
                    {/* Dưới một phút thì đổi màu: đó là lúc con số thôi là thông
                        tin và bắt đầu là một lời nhắc nên bỏ qua người này. */}
                    <span
                      className={cx(
                        "font-data text-label tabular-nums",
                        left <= 60 ? "text-alert" : "text-ink-faint",
                      )}
                    >
                      {clock(left)}
                    </span>
                  </span>
                  <span className="mt-0.5 flex items-center gap-2 pl-8 text-label text-ink-faint">
                    {one.steps_total > 1 && (
                      <span className="font-data tabular-nums">
                        {one.steps_done}/{one.steps_total} bước
                      </span>
                    )}
                    <span className="font-data tabular-nums">+{one.reward_ruby} ruby</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
