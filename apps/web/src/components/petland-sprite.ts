/**
 * Sổ đăng ký mascot. **Đây là tệp duy nhất phải sửa khi thêm hoặc đổi mascot.**
 *
 * Không có gì trong tệp này là logic — chỉ là số đo của từng bộ sprite, và bảng
 * ánh xạ từ Ý ĐỊNH sang tên clip. Phần còn lại của Petland nói bằng ý định
 * ("đứng", "đi", "nhảy lên"), không nói bằng tên tệp ảnh, nên một mascot có bộ
 * hoạt ảnh khác — tên khác, số khung khác, thiếu hẳn một hoạt ảnh — chỉ cần một
 * hàng mới ở dưới.
 *
 * **`MascotId` đến từ contract dùng chung, không khai ở đây.** Danh sách sống ở
 * `apps/api/app/schemas/profile.py::PetId` và đi qua OpenAPI ra tới TypeScript,
 * nên `Record<MascotId, Mascot>` thiếu một con là lỗi `tsc` chứ không phải một
 * `undefined` lộ ra lúc chạy. Thêm mascot thì sửa phía API trước, chạy
 * `pnpm gen:api-types`, rồi mới thêm hàng ở đây — thứ tự ngược lại không biên dịch.
 *
 * Cả hai bộ đều được SINH RA (skill `generate2dsprite`, FLUX.2-klein tại máy) và
 * đóng gói bằng `scripts/pack-pet.mjs`, thứ ĐO ra `cell`, `footY` và `anchorX`
 * rồi in chúng cho người chép vào đây. Không đoán ba số đó bằng mắt:
 * `check-petland-fit.mjs` so khớp tuyệt đối và sai vài pixel làm con thú lơ
 * lửng hoặc lún xuống đất.
 */
import type { UserProfilePublic } from "@toeic-pilot/shared";

/**
 * Ý định của con thú. Đây là từ vựng CHUNG giữa phần điều khiển, phần giao diện
 * và bộ sprite — nó phải nói về hành vi, không về nghệ thuật, vì hành vi thì
 * không đổi khi đổi mascot.
 */
export type PetIntent = "stand" | "walk" | "run" | "hop" | "sleep";

export type SpriteClip = {
  /** Tên tệp dải ảnh, không kèm đuôi. */
  name: string;
  frames: number;
  /** 0 = khung hình do thứ khác quyết định (cung nhảy), không do đồng hồ. */
  fps: number;
  loop: boolean;
};

/** Mã mascot, lấy thẳng từ contract để hai bên không trôi khỏi nhau. */
export type MascotId = NonNullable<UserProfilePublic["pet"]>;

export type Mascot = {
  /** Tên hiện cho người dùng. Tiếng Việt: đây là phần học viên nhìn thấy. */
  label: string;
  /** Ô của dải sprite. */
  cell: { w: number; h: number };
  /** Hàng mặt đất bên trong ô. */
  footY: number;
  /** Tâm ngang của tư thế đứng, cũng là điểm `scaleX(-1)` lật quanh. */
  anchorX: number;
  base: string;
  clips: Record<PetIntent, SpriteClip>;
};

export const MASCOTS: Record<MascotId, Mascot> = {
  cat: {
    label: "Mèo",
    cell: { w: 151, h: 117 },
    footY: 117,
    anchorX: 64,
    base: "/mascots/cat",
    clips: {
      stand: { name: "idle", frames: 4, fps: 5, loop: true },
      walk: { name: "walk", frames: 6, fps: 9, loop: true },
      run: { name: "run", frames: 6, fps: 13, loop: true },
      hop: { name: "jump", frames: 6, fps: 0, loop: false },
      sleep: { name: "sleep", frames: 4, fps: 5, loop: false },
    },
  },
  rex: {
    label: "Khủng long",
    cell: { w: 125, h: 117 },
    footY: 117,
    anchorX: 69,
    base: "/mascots/rex",
    clips: {
      stand: { name: "idle", frames: 4, fps: 5, loop: true },
      /*
       * Không có dải `walk` riêng: bộ này chỉ có bốn clip. Ý định "đi" phát
       * chính chu kỳ chạy ở fps thấp hơn — đúng lối thoát mà bảng ánh xạ này
       * tồn tại để cho phép, và là cách nhiều game 2D vẫn làm.
       *
       * Lý do không có: ba lần sinh `walk` cho bộ này đều hỏng theo cùng một
       * kiểu — anchor sheet giữ nguyên ảnh tham chiếu nên nó mạnh ở chuỗi đơn
       * điệu (nằm xuống, sải bước) và yếu ở chu kỳ tuần hoàn (ROADMAP §4s).
       */
      walk: { name: "run", frames: 6, fps: 7, loop: true },
      run: { name: "run", frames: 6, fps: 13, loop: true },
      hop: { name: "jump", frames: 6, fps: 0, loop: false },
      sleep: { name: "sleep", frames: 4, fps: 5, loop: false },
    },
  },
};

/*
 * Con mặc định khi hồ sơ chưa chọn. Cột `user_profile.pet` để NULL chứ không
 * điền sẵn giá trị này, nên đổi hằng số ở đây là mọi người chưa từng chọn đi
 * theo — thay vì bị ghim vào con mặc định của ngày họ đăng ký.
 */
export const DEFAULT_MASCOT: MascotId = "cat";

/** Đọc mã mascot từ hồ sơ, chịu được cả giá trị lạ của một bản cũ. */
export function mascotOf(pet: string | null | undefined): Mascot {
  return (pet && pet in MASCOTS ? MASCOTS[pet as MascotId] : MASCOTS[DEFAULT_MASCOT])!;
}

export function clipOf(mascot: Mascot, intent: PetIntent): SpriteClip {
  return mascot.clips[intent];
}

export function sheetUrl(mascot: Mascot, intent: PetIntent): string {
  return `${mascot.base}/${mascot.clips[intent].name}.png`;
}

/** Khung hình đứng đầu tiên, cho nút mở bảng và cho ô chọn mascot. */
export function posterOf(mascot: Mascot): { url: string; frames: number } {
  return { url: sheetUrl(mascot, "stand"), frames: mascot.clips.stand.frames };
}
