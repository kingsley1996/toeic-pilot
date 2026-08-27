"use client";

import { API_ROUTES, type PetOwnedPublic, type PetPublic } from "@toeic-pilot/shared";
import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { Creature, TIER_LABEL, TIER_TONE } from "@/components/petland-creature";
import { cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";

/**
 * Bộ sưu tập: những con đã có, và đổi con đang nuôi (ADR-010 lát 9).
 *
 * **Đổi con giữ nguyên vị trí và nhu cầu.** `pet_state` mô tả một góc vườn chứ
 * không phải một con vật cụ thể; đặt lại chỉ số mỗi lần đổi thì mỗi lần ngắm một
 * con khác là một lần xoá tiến độ chăm sóc, và người ta sẽ thôi đổi. Luật đó
 * sống ở máy chủ; chỗ này chỉ gửi một mã loài và vẽ lại theo thứ nhận được.
 *
 * Cùng cột với màn trứng, và đó là chủ ý: mở trứng ra con gì rồi đi xem tủ là
 * một mạch, nên hai màn dùng chung một chỗ và một cái nút đóng.
 */
export function CollectionScreen({
  token,
  active,
  onSwitched,
  onClose,
}: {
  token: string;
  /** Mã loài đang nuôi — để đánh dấu và để không gửi lệnh đổi sang chính nó. */
  active: string | null;
  onSwitched: (pet: PetPublic) => void;
  onClose: () => void;
}) {
  const [owned, setOwned] = useState<PetOwnedPublic[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    apiFetch<PetOwnedPublic[]>(API_ROUTES.petCollection, { token })
      .then((rows) => {
        if (alive) setOwned(rows);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token]);

  async function pick(code: string) {
    if (busy || code === active) return;
    setBusy(code);
    setFailed(null);
    try {
      const pet = await apiFetch<PetPublic>(API_ROUTES.petSwitch, {
        method: "PATCH",
        token,
        body: JSON.stringify({ species: code }),
      });
      // Con thú trên bản đồ đổi hình NGAY từ phản hồi này, không đợi một lần đọc
      // nữa: `pet.tile` là ô do máy chủ tra, nên đây là con số đúng để vẽ.
      onSwitched(pet);
    } catch (err) {
      setFailed(err instanceof ApiError ? err.message : "Chưa đổi được.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="max-h-[35vh] w-full shrink-0 overflow-y-auto border-t border-rule p-3 sm:h-[var(--pet-map-h)] sm:max-h-none sm:w-[var(--pet-egg-w)] sm:border-l sm:border-t-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-small font-semibold text-ink">
          Bộ sưu tập
          {owned && (
            <span className="ml-2 font-data font-normal tabular-nums text-ink-muted">
              {owned.length} loài
            </span>
          )}
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Đóng bộ sưu tập"
          className="grid h-6 w-6 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink"
        >
          <X size={14} strokeWidth={2} aria-hidden />
        </button>
      </div>

      {owned && owned.length === 0 && (
        <p className="mt-2 text-small text-ink-muted">Chưa có con nào. Mở trứng để bắt đầu.</p>
      )}

      <ul className="mt-3 grid gap-1">
        {owned?.map((row) => {
          const current = row.code === active;
          return (
            <li key={row.code}>
              <button
                type="button"
                onClick={() => pick(row.code)}
                disabled={current || busy !== null}
                // Con ĐANG NUÔI không bị làm mờ như một nút hỏng: nó bật sáng và
                // nói "đang nuôi". Mờ đi thì trạng thái tốt nhất trong danh sách
                // lại trông giống trạng thái không dùng được.
                className={cx(
                  "flex w-full items-center gap-2 rounded border p-1.5 text-left text-small transition-colors",
                  current
                    ? "border-action bg-action-tint text-ink"
                    : "border-rule-strong hover:bg-recess disabled:opacity-45",
                )}
              >
                <Creature tile={row.tile} size={24} />
                {/* KHÔNG in "×2".
                    Mở trúng con đã có thì được hoàn ruby, nên bản thứ hai không
                    phải một thứ người chơi đang giữ: in ×2 bên cạnh tên là nói
                    rằng có hai con — trong khi chỉ có một — và ngụ ý con số ấy
                    dùng được vào việc gì đó. Số lần nở vẫn nằm ở `copies` như
                    lịch sử, và nó nằm trong `title` cho ai tò mò. */}
                <span
                  className="min-w-0 flex-1 truncate"
                  title={row.copies > 1 ? `Đã nở ${row.copies} lần` : undefined}
                >
                  {row.label}
                </span>
                <span className={cx("text-label", TIER_TONE[row.tier])}>
                  {TIER_LABEL[row.tier] ?? row.tier}
                </span>
                {current && <span className="text-label text-action">đang nuôi</span>}
              </button>
            </li>
          );
        })}
      </ul>

      {failed && <p className="mt-2 text-small text-warn">{failed}</p>}
    </div>
  );
}
