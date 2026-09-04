"use client";

import { API_ROUTES, type PetPublic } from "@toeic-pilot/shared";
import { useCallback, useEffect, useState } from "react";

import { PetIdle } from "@/components/petland-creature";
import { CONDITION_LABEL, conditionOf } from "@/components/petland-pet";
import { PetlandToast } from "@/components/petland-toast";
import { PixelIcon, type PixelIconName } from "@/components/pixel-icon";
import { Skeleton, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { subscribeToCheer } from "@/lib/pet-cheer";
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
  /*
   * Ba trạng thái, không hai — cùng cái bẫy mà `session.status` đã ghi lại.
   *
   * `undefined` là CHƯA ĐỌC XONG, `null` là ĐỌC RỒI VÀ CHƯA CÓ THÚ (máy chủ trả
   * 204 vì người dùng chưa mở quả trứng đầu tiên). Gộp hai thứ ấy làm một thì
   * lời mời "nhận thú cưng" nháy lên ở mỗi lần tải trang của người ĐÃ có thú.
   */
  const [pet, setPet] = useState<PetPublic | null | undefined>(undefined);

  const load = useCallback(() => {
    if (!token) return;
    // 204 làm `apiFetch` trả về `undefined`; ở đây nó nghĩa là "chưa có thú".
    apiFetch<PetPublic | undefined>(API_ROUTES.pet, { token })
      .then((body) => setPet(body ?? null))
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

  /* Trả lời đúng một câu thì con thú ở đây loé sáng y như con trong bảng —
     cùng kênh, nên hai chỗ không bao giờ reo lệch nhau. Đếm tăng dần chứ không
     bật/tắt: xem `cheerKey` ở `PetIdle`. */
  const [cheers, setCheers] = useState(0);
  useEffect(() => subscribeToCheer(() => setCheers((n) => n + 1)), []);

  if (status !== "authenticated") return null;

  const condition = pet ? conditionOf(pet.needs) : undefined;
  return (
    <div className="relative shrink-0 border-t border-rule px-2 py-2">
      <PetlandToast condition={condition} />
      {pet === undefined ? (
        <Skeleton className="h-14 w-full" />
      ) : pet === null ? (
        <EggCard />
      ) : (
        <PetCard pet={pet} cheers={cheers} />
      )}
    </div>
  );
}

/**
 * Chưa có thú: một quả trứng và một lời mời.
 *
 * Cùng khuôn thẻ thật — cùng bề cao, cùng viền, cùng chỗ bấm — nên lúc con thú
 * nở ra, chỗ ấy không nhảy và người dùng không phải đi tìm lại. Đó cũng là lý do
 * nó là một cái NÚT chứ không phải một dòng chữ: thao tác duy nhất ở đây là mở
 * bảng ra, y hệt thẻ thật.
 */
function EggCard() {
  return (
    <button
      type="button"
      onClick={requestPetOpen}
      title="Mở quả trứng đầu tiên"
      className="flex w-full items-center gap-2 rounded border border-action bg-action-tint px-2 py-1.5 text-left transition-[padding] duration-enter hover:border-action motion-reduce:transition-none rail:px-0"
    >
      {/* Trứng lắc nhẹ: nó là thứ DUY NHẤT trên thẻ này có việc để làm, nên nó
          được phép xin một cái liếc. Ở dải thu gọn thì chỉ còn nó. */}
      <span className="egg-wait block shrink-0 px-2">
        <PixelIcon name="egg" scale={3} />
      </span>
      <span className="min-w-0 flex-1 overflow-hidden transition-opacity duration-enter motion-reduce:transition-none rail:opacity-0">
        <span className="block truncate text-small font-semibold text-action-ink">
          Bạn có một quả trứng
        </span>
        <span className="mt-0.5 block truncate text-label text-ink-muted">
          Mở ra xem được con gì
        </span>
      </span>
    </button>
  );
}

/** Còn ngủ tới lúc nào; `null` hoặc mốc đã qua đều là đang thức. */
function isAsleep(pet: PetPublic): boolean {
  return pet.sleep_until !== null && new Date(pet.sleep_until).getTime() > Date.now();
}

function PetCard({ pet, cheers }: { pet: PetPublic; cheers: number }) {
  const needs = pet.needs;
  const asleep = isAsleep(pet);
  const condition = conditionOf(needs);
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
      <PetIdle
        tile={pet.tile}
        tier={pet.tier}
        condition={condition}
        sleeping={asleep}
        cheerKey={cheers}
        size={24}
      />

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

        {/*
         * Tình trạng bằng CHỮ, ngay dưới tên.
         *
         * Ba con số nói con thú đang thế nào, nhưng chúng bắt người đọc tự dịch:
         * "no 18%" phải so với một ngưỡng nằm trong đầu ai đó mới thành "đang
         * đói". Câu chữ nói thẳng, và nó dùng đúng `CONDITION_LABEL` mà bảng
         * dùng — một bảng nhãn thứ hai ở đây là hai chỗ gọi cùng một trạng thái
         * bằng hai cái tên.
         *
         * Ngủ đè lên tình trạng chứ không xếp cạnh: lúc ngủ thì đói hay mệt đều
         * không phải thứ người dùng làm gì được, còn "đang ngủ" thì giải thích
         * luôn vì sao mấy cái nút đang từ chối.
         */}
        <span
          className={cx(
            "mt-0.5 block truncate text-label",
            asleep
              ? "text-ink-faint"
              : condition === "exhausted" || condition === "hungry"
                ? "text-warn"
                : "text-ink-muted",
          )}
        >
          {asleep ? "Đang ngủ" : CONDITION_LABEL[condition]}
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
