"use client";

import { API_ROUTES, type PetPublic } from "@toeic-pilot/shared";
import { useCallback, useEffect, useState } from "react";

import { PetIdle } from "@/components/petland-creature";
import { conditionOf } from "@/components/petland-pet";
import { PetlandToast } from "@/components/petland-toast";
import { PixelIcon, type PixelIconName } from "@/components/pixel-icon";
import { Skeleton } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { subscribeToPetNotices } from "@/lib/pet-notice";
import { requestPetOpen } from "@/lib/pet-open";
import { subscribeToPetState } from "@/lib/pet-state";
import { useSession } from "@/lib/session";

/**
 * Thẻ thú cưng thu nhỏ trong sidebar.
 *
 * Con thú cần một chỗ ở CỐ ĐỊNH, và trước đây nó không có: chỉ có một bảng nổi
 * đè lên nội dung, nên nó vừa dễ vướng vừa dễ quên mất là có. Ở trong sidebar
 * thì nó không đè lên gì, luôn nhìn thấy được, và — quan trọng nhất — nó cho
 * phép ẩn hẳn bảng nổi lúc người ta đang học mà không làm con thú biến mất khỏi
 * sản phẩm.
 *
 * **Cả thẻ là một cái nút, và nó chỉ làm đúng một việc: mở bảng.** Cho ăn, chọc,
 * đi dạo đều ở trong bảng. Một thẻ rộng chưa tới 200px mà nhét bốn nút hành động
 * sẽ thành một bảng thứ hai, và khi hai chỗ cùng làm được một việc thì có ngày
 * chúng nói hai điều khác nhau.
 *
 * **Nằm dưới nav, trên khối tài khoản**: nav thì cuộn, thẻ này thì không được
 * cuộn mất.
 *
 * Thẻ cũng là NƠI HẠ CÁNH của toast góc thú cưng — xem `PetlandToast`. Vì thế
 * lúc chưa tải xong nó dựng một khung xám thay vì không dựng gì: một cái toast
 * bay ra rồi mất tiêu vì thẻ chưa kịp có là thứ không ai dò lại được.
 */

/**
 * Ba chỉ số, mỗi cái một biểu tượng.
 *
 * Xương là cái ăn được (cùng hình mà nút "Cho ăn" đeo), trái tim là sức, mặt
 * cười là tinh thần. Ở bề rộng này thanh chỉ số tám ô đọc không ra: ba cái thanh
 * cùng khoẻ là ba vạch xanh giống hệt nhau, còn `72%` thì nói ngay được điều nó
 * định nói. Tên đầy đủ nằm ở `title` cho lần đầu nhìn thấy.
 */
const STATS: { key: "fullness" | "energy" | "mood"; icon: PixelIconName; name: string }[] = [
  { key: "fullness", icon: "bone", name: "Độ no" },
  { key: "energy", icon: "heart", name: "Sức" },
  { key: "mood", icon: "smile", name: "Tinh thần" },
];

/* Màu là TÍN HIỆU: con số chỉ đổi màu khi có điều đáng báo, còn lúc mọi thứ ổn
   thì ba con số xanh lè chỉ là ba chỗ kéo mắt. */
function toneFor(value: number): string {
  if (value < 0.2) return "text-alert";
  if (value < 0.45) return "text-warn";
  return "text-ink-muted";
}

export function PetlandCard() {
  const { token, status } = useSession();
  const [pet, setPet] = useState<PetPublic | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    apiFetch<PetPublic>(API_ROUTES.pet, { token })
      .then(setPet)
      .catch(() => {
        /* Góc thú cưng hỏng thì sidebar vẫn phải dùng được. */
      });
  }, [token]);

  useEffect(load, [load]);

  /* Cho ăn, chọc, đi dạo, đổi con — bảng đã có sẵn `PetPublic` mới từ phản hồi,
     nên nhận thẳng thay vì đọc lại: đọc lại vừa thừa một vòng mạng vừa để lọt
     một khoảng thẻ và bảng nói hai con số khác nhau. */
  useEffect(() => subscribeToPetState(setPet), []);

  /* Phần thưởng từ một lượt học thì KHÔNG kèm con thú mới, nên chỗ này vẫn phải
     đọc lại — cùng kênh mà toast dùng, nên hai bên không lệch nhau. */
  useEffect(() => subscribeToPetNotices(load), [load]);

  if (status !== "authenticated") return null;

  const condition = pet === null ? undefined : conditionOf(pet.needs);
  return (
    <div className="relative shrink-0 border-t border-rule px-2 py-2">
      <PetlandToast condition={condition} />
      {pet === null ? <Skeleton className="h-12 w-full" /> : <PetCard pet={pet} />}
    </div>
  );
}

function PetCard({ pet }: { pet: PetPublic }) {
  const needs = pet.needs;
  return (
    <button
      type="button"
      onClick={requestPetOpen}
      title="Mở góc thú cưng"
      /* Lề chuyển CÙNG NHỊP với bề rộng sidebar (`duration-enter`, đúng token mà
         `<aside>` dùng). Lật ngay thì con thú nhảy 8px sang trái ở mili giây đầu
         trong khi cái cột còn đang trượt — đó chính là cú giật. */
      className="flex w-full items-center gap-2 rounded border border-rule bg-recess px-2 py-1.5 text-left transition-[padding] duration-enter hover:border-action motion-reduce:transition-none rail:px-0"
    >
      {/*
       * MỘT cỡ cho cả hai trạng thái sidebar, và đó là cách sửa chỗ giật.
       *
       * Bản trước dựng hai cỡ rồi chọn bằng `rail:`. Nhưng bề rộng sidebar thì
       * CHUYỂN DẦN (`transition-[width]`) còn biến thể `rail:` thì lật ngay ở
       * mili giây đầu — nên suốt quãng chuyển ấy con thú đã đổi cỡ trong khi cái
       * cột vẫn đang trượt, và mắt đọc ra là một cú nảy.
       *
       * Cỡ 24 là cỡ lớn nhất còn lọt dải 64px: vòng sáng rộng 1.8× con thú, tức
       * 43px, và bỏ lề ngang của nút khi thu gọn thì còn đúng 46px lọt. Con thú
       * không đổi gì khi toggle, nên không còn gì để giật.
       */}
      <PetIdle tile={pet.tile} tier={pet.tier} condition={conditionOf(needs)} size={24} />

      {/* Ở dải thu gọn chỉ còn con thú: tên và ba con số không đọc được ở bề
          rộng đó. Mờ dần rồi bị cột hẹp lại cắt đi, chứ không `hidden` — biến
          mất ngay ở khung hình đầu là một cú chớp giữa lúc mọi thứ đang trượt. */}
      <span className="min-w-0 flex-1 overflow-hidden transition-opacity duration-enter motion-reduce:transition-none rail:opacity-0">
        <span className="flex items-baseline gap-1.5">
          <span className="truncate text-small font-semibold">{pet.nickname ?? pet.label}</span>
          <span className="shrink-0 font-data text-label tabular-nums text-ink-faint">
            Lv {pet.level}
          </span>
        </span>
        <span className="mt-1 flex items-center gap-2 font-data text-label tabular-nums">
          {STATS.map(({ key, icon, name }) => (
            <span key={key} className="flex items-center gap-1" title={name}>
              <PixelIcon name={icon} scale={1} />
              <span className={toneFor(needs[key])}>
                <span className="sr-only">{name} </span>
                {Math.round(needs[key] * 100)}%
              </span>
            </span>
          ))}
        </span>
      </span>
    </button>
  );
}
