"use client";

import { ArrowLeft, ArrowRight, Maximize2, Minimize2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PixelIcon } from "@/components/pixel-icon";
import { createFx } from "@/components/petland-fx";
import {
  type PetAction,
  type PetNeeds,
  applyAction,
  decayNeeds,
  freshNeeds,
  refuse,
} from "@/components/petland-pet";
import {
  FIRE,
  LANDMARKS,
  PATH_LENGTH,
  WORLD_H,
  WORLD_W,
  pointAt,
} from "@/components/petland-scene";
import {
  DEFAULT_MASCOT,
  MASCOTS,
  type Mascot,
  type MascotId,
  type PetIntent,
  clipOf,
  mascotOf,
  posterOf,
  sheetUrl,
} from "@/components/petland-sprite";
import { type Bit, PetHud, PixelBits } from "@/components/petland-ui";
import { cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import { API_ROUTES, type UserProfilePublic } from "@toeic-pilot/shared";

/*
 * Petland — một con thú nhỏ sống trong một khung cảnh, ở góc dưới bên trái.
 *
 * Tệp này chỉ NỐI các mảnh lại; ba trong bốn mảnh có thể thay mà không đụng tới
 * nhau, và đó là điểm chính của cách chia này:
 *
 *   petland-sprite.ts  con mascot        — đổi mascot thì sửa ĐÚNG tệp này
 *   petland-scene.ts   bối cảnh          — đổi tranh thì sửa tệp này (+ fx)
 *   petland-fx.ts      hạt của bối cảnh  — đi theo bức tranh
 *   petland-pet.ts     nhu cầu & hành động — không biết gì về ảnh, không đổi
 *   petland-ui.tsx     giao diện tương tác — không biết gì về ảnh, không đổi
 *
 * Cầu nối giữa hai nửa là `PetIntent`: phần điều khiển nói "đứng", "đi", "nhảy
 * lên", còn bảng trong `petland-sprite.ts` dịch sang tên clip. Nói bằng tên tệp
 * ảnh thì mọi nơi trong tệp này đều dính vào con dino hiện tại.
 *
 * Chưa gọi API. Các chỉ số sống trong bộ nhớ trang — chúng đi theo người dùng
 * qua các lần chuyển trang vì `AppShell` không bị tháo, nhưng mất khi tải lại.
 */

/*
 * Ống nhòm chứ không phải cả bức tranh.
 *
 * Tỉ lệ trong tranh là thật: đống lửa cao ~110px, cửa gỗ ~90px. Một con thú
 * "thuộc về" cảnh đó phải cao 60–80px, tức đúng cỡ tự nhiên của bộ sprite. Nên
 * không thể thu nhỏ bức tranh cho vừa một khung góc màn hình — thu nhỏ 2x thì
 * con thú cũng nhỏ 2x và thành một vệt 40px. Khung là một CỬA SỔ trượt theo con
 * thú, đúng cách một game 2D làm với bản đồ lớn hơn màn hình.
 */
/* 460 chứ không phải 420: hàng nút cần bấy nhiêu để không xuống dòng, và một
   hàng xuống dòng thì `ml-auto` của nút Ngủ đẩy nó ra giữa dòng thứ hai. */
const VIEW_W = 460;
const VIEW_H = 250;
/* Toàn cảnh: đúng một nửa, nên cả bức tranh vừa khít và không phải kẹp camera. */
const FULL_ZOOM = 0.5;

const WALK_SPEED = 46; // px dọc đường đi, mỗi giây
const RUN_SPEED = 104;
const JUMP_MS = 700;
const JUMP_H = 46;

/*
 * Cung nhảy là parabol theo THỜI GIAN chứ không phải tích phân của trọng lực.
 * Tích phân thì thời gian bay phụ thuộc bước thời gian, nên khung hình cuối của
 * bộ nhảy rơi vào lúc nào là tuỳ máy.
 */
const arc = (t: number) => 4 * JUMP_H * t * (1 - t);

/*
 * Ánh sáng: con thú được vẽ dưới ánh sáng ban ngày, còn khu trại là cảnh ĐÊM chỉ
 * có trăng và một đống lửa. Không chỉnh gì thì nó nổi lên như một hình dán.
 *
 * Một bộ lọc CỐ ĐỊNH không giải quyết được: mức đủ tối cho khúc cầu dưới trăng
 * làm con thú cạnh đống lửa trông như trong bóng râm, còn mức hợp với đống lửa
 * thì ra ngoài cầu lại chói. `hue-rotate` đổi dấu làm việc nặng nhất — dương đẩy
 * sắc xanh lá về vàng (lửa), âm đẩy về xanh lục lam (trăng).
 *
 * Nguồn sáng lấy từ BỐI CẢNH chứ không viết lại ở đây: nó là thuộc tính của bức
 * tranh, và một bản sao thứ hai sẽ trôi khỏi bản gốc lúc đổi tranh.
 */
const FIRE_REACH = 340;

function lightingAt(x: number, y: number): string {
  const warm = Math.max(0, 1 - Math.hypot(x - FIRE.x, y - FIRE.y) / FIRE_REACH);
  return (
    `brightness(${(0.74 + 0.26 * warm).toFixed(2)}) ` +
    `saturate(${(0.84 + 0.16 * warm).toFixed(2)}) ` +
    `hue-rotate(${(-7 + 13 * warm).toFixed(1)}deg)`
  );
}

const IDLE_BEFORE_WANDER_MS = 3500;
const IDLE_BEFORE_SLEEP_MS = 30000;
const EAT_MS = 1600;
/** Khoảng cách coi như "đã tới nơi", dọc đường đi. */
const REACHED = 6;

/* Camera bám mềm chứ không dính cứng: một cửa sổ dán chặt vào con thú biến bức
   tranh thành thứ đang trôi, và mắt mất điểm tựa. */
const CAM_LERP = 5;

const MOODS: Record<PetIntent, string> = {
  stand: "đang đứng chơi",
  walk: "đi dạo",
  run: "chạy",
  hop: "nhảy",
  sleep: "ngủ rồi — bấm vào để đánh thức",
};

/** Việc đang làm dở, khác với ý định hoạt ảnh. `null` = rảnh. */
type Task = "toFood" | "eating";

/** Trạng thái đổi mỗi khung hình. Để ngoài React: 60 lần/giây thì `setState`
 *  chỉ tạo ra công việc dựng lại giao diện chứ không tạo ra gì khác. */
type Pet = {
  /** Quãng đường đã đi dọc `PATH`, tính bằng px. Đây là TOÀN BỘ vị trí. */
  d: number;
  dir: 1 | -1;
  intent: PetIntent;
  frame: number;
  frameAcc: number;
  jumpStart: number | null;
  input: -1 | 0 | 1;
  running: boolean;
  lastInput: number;
  /** Đích của chuyến đi tự động, `null` khi không đi đâu. */
  goTo: number | null;
  task: Task | null;
  taskUntil: number;
  /** Chỗ đặt miếng ăn, dọc đường đi. */
  treatAt: number | null;
  camX: number;
  camY: number;
};

export function PetLand() {
  const [open, setOpen] = useState(false);
  /*
   * Chỉ số sống ở ĐÂY chứ không trong bảng, nên đóng bảng rồi mở lại không đặt
   * con thú về mặc định — "đóng cửa sổ" không phải là một sự kiện trong đời con
   * thú. Là `ref` chứ không phải state vì vòng lặp cập nhật nó 60 lần/giây.
   */
  const needsRef = useRef<PetNeeds>(freshNeeds());

  /*
   * Petland gọi API, và đây là chỗ DUY NHẤT nó gọi. ROADMAP §4m từng ghi
   * "Petland KHÔNG gọi API" — đúng ở thời điểm đó, vì không có gì thuộc về tài
   * khoản. Con mascot thì có: "pet của tôi" phải đi theo tài khoản qua mọi thiết
   * bị và sống sót qua việc xoá cache, nên nó nằm ở `user_profile.pet` chứ không
   * ở localStorage như chủ đề sáng/tối — cái đó là sở thích theo THIẾT BỊ.
   *
   * Hỏng thì im lặng rơi về con mặc định: một góc thú cưng không mở được vì
   * mạng chập là cái giá quá đắt cho một tuỳ chọn trang trí.
   */
  const { token, status } = useSession();
  const [pet, setPet] = useState<MascotId | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !token) return;
    let alive = true;
    apiFetch<UserProfilePublic>(API_ROUTES.profile, { token })
      .then((p) => {
        if (alive && p.pet) setPet(p.pet);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token, status]);

  const mascot = mascotOf(pet);

  /*
   * Ghi lạc quan: đổi ngay trên màn hình rồi mới gửi đi. Chờ máy chủ trả lời mới
   * đổi con thú làm nút bấm có vẻ hỏng trên mạng chậm, mà thứ đang đổi chỉ là
   * hình con vật — không có gì để mất nếu lần ghi trượt.
   */
  const pick = useCallback(
    (id: MascotId) => {
      setPet(id);
      if (!token) return;
      void apiFetch<UserProfilePublic>(API_ROUTES.profile, {
        method: "PATCH",
        token,
        body: JSON.stringify({ pet: id }),
      }).catch(() => {});
    },
    [token],
  );

  return (
    <div className="fixed bottom-5 left-5 z-40 max-sm:origin-bottom-left max-sm:scale-[0.7] lg:left-[16.25rem]">
      {open ? (
        <PetPanel
          needsRef={needsRef}
          mascot={mascot}
          picked={pet ?? DEFAULT_MASCOT}
          onPick={pick}
          onClose={() => setOpen(false)}
        />
      ) : (
        <PetLauncher mascot={mascot} onOpen={() => setOpen(true)} />
      )}
    </div>
  );
}

function PetLauncher({ mascot, onOpen }: { mascot: Mascot; onOpen: () => void }) {
  const poster = posterOf(mascot);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="inline-flex items-center gap-2 rounded border border-rule-strong bg-panel py-1.5 pl-1.5 pr-3 text-small font-semibold text-ink transition-colors hover:bg-recess"
    >
      {/* Khung hình đứng đầu tiên. `background-size` phải nhân theo TOÀN dải chứ
          không theo một ô, nếu không nó co cả bộ khung vào 40px. */}
      <span
        aria-hidden
        className="block h-10 w-12 shrink-0 bg-no-repeat"
        style={{
          backgroundImage: `url(${poster.url})`,
          backgroundSize: `${mascot.cell.w * poster.frames * 0.34}px ${mascot.cell.h * 0.34}px`,
          backgroundPosition: "-2px 0",
        }}
      />
      Thú cưng
    </button>
  );
}

/**
 * Chọn mascot. Một nhóm nút bấm, không phải `<select>`.
 *
 * Cái đang chọn là một HÌNH, nên danh sách phải cho thấy hình đó — một menu chữ
 * bắt người dùng nhớ "Mèo" trông thế nào rồi mới bấm được. Với hai con thì cả
 * hai hiện cùng lúc; nếu sau này nhiều hơn khoảng sáu con thì đây là chỗ đổi
 * sang lưới có thể cuộn, chứ đừng đổi sang menu chữ.
 *
 * `role="radiogroup"` chứ không phải nhóm nút thường: đây là chọn MỘT trong
 * nhiều, và `aria-checked` là thứ nói cho người dùng trình đọc màn hình biết
 * con nào đang được chọn. Một `aria-pressed` trên từng nút sẽ đọc thành "đã
 * bấm", không thành "đang chọn".
 */
/*
 * Hệ số thu nhỏ cho ảnh trong nút, tính từ số đo của CHÍNH mascot đó chứ không
 * phải một hằng số chung: hai con có ô rộng khác nhau (151 và 125), nên một hệ
 * số chung làm con này tràn nút còn con kia lọt thỏm.
 */
const THUMB_W = 30;
const THUMB_H = 26;
function thumb(m: Mascot): number {
  return Math.min(THUMB_W / m.cell.w, THUMB_H / m.cell.h);
}

function MascotPicker({ picked, onPick }: { picked: MascotId; onPick: (id: MascotId) => void }) {
  const ids = Object.keys(MASCOTS) as MascotId[];
  return (
    <span
      role="radiogroup"
      aria-label="Chọn thú cưng"
      className="mr-1 flex items-center gap-0.5 border-r border-rule pr-1.5"
    >
      {ids.map((id) => {
        const m = MASCOTS[id];
        const poster = posterOf(m);
        const on = id === picked;
        return (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={on}
            aria-label={m.label}
            title={m.label}
            onClick={() => onPick(id)}
            className={cx(
              "block h-8 w-8 rounded border bg-no-repeat transition-colors",
              on
                ? "border-rule-strong bg-recess"
                : "border-transparent opacity-55 hover:opacity-100",
            )}
            style={{
              backgroundImage: `url(${poster.url})`,
              /*
               * Nhân theo TOÀN dải, không theo một ô — nếu không nó co cả bộ
               * khung vào 32px và ô nào cũng thành một vệt.
               *
               * Và căn về mép TRÁI, không `center`: dải rộng gấp mấy lần nút,
               * nên "giữa dải" rơi đúng vào mối nối giữa hai khung và nút hiện
               * ra nửa con này ghép nửa con kia. Khung 0 nằm ở mép trái.
               */
              backgroundSize: `${m.cell.w * poster.frames * thumb(m)}px ${m.cell.h * thumb(m)}px`,
              backgroundPosition: "left center",
            }}
          />
        );
      })}
    </span>
  );
}

function PetPanel({
  needsRef,
  mascot,
  picked,
  onPick,
  onClose,
}: {
  needsRef: React.RefObject<PetNeeds>;
  mascot: Mascot;
  picked: MascotId;
  onPick: (id: MascotId) => void;
  onClose: () => void;
}) {
  /*
   * Mascot đọc qua ref bên trong vòng lặp, KHÔNG qua closure.
   *
   * Vòng lặp `requestAnimationFrame` phía dưới có danh sách phụ thuộc riêng và
   * không dựng lại khi mascot đổi — nên một closure sẽ giữ mãi con cũ và nút
   * chọn trông như không làm gì. Thêm `mascot` vào deps thì sửa được, nhưng cái
   * giá là dựng lại cả vòng lặp giữa chừng: `frameAcc` về 0 và con thú giật một
   * cái ngay lúc người dùng vừa bấm. Ref không có cả hai vấn đề, và đây đúng là
   * cách `needsRef` đã dùng ở tệp này.
   */
  const mascotRef = useRef(mascot);
  useEffect(() => {
    mascotRef.current = mascot;
  }, [mascot]);

  const spriteRef = useRef<HTMLButtonElement | null>(null);
  const worldRef = useRef<HTMLDivElement | null>(null);
  const fxRef = useRef<HTMLCanvasElement | null>(null);
  const start = pointAt(PATH_LENGTH * 0.18);
  const petRef = useRef<Pet>({
    d: PATH_LENGTH * 0.18,
    dir: 1,
    intent: "stand",
    frame: 0,
    frameAcc: 0,
    jumpStart: null,
    input: 0,
    running: false,
    lastInput: 0,
    goTo: null,
    task: null,
    taskUntil: 0,
    treatAt: null,
    camX: start.x - VIEW_W / 2,
    camY: start.y - VIEW_H * 0.62,
  });

  const [mood, setMood] = useState<PetIntent>("stand");
  const [place, setPlace] = useState("");
  const [full, setFull] = useState(false);
  const [busy, setBusy] = useState(false);
  /* Bản sao của chỉ số dành cho giao diện. Nó KHÔNG cập nhật mỗi khung hình —
     xem `pushNeeds` dưới đây. */
  /* Khởi tạo bằng giá trị mặc định rồi để vòng lặp đẩy giá trị thật xuống ngay ở
     khung hình đầu: đọc `needsRef.current` ngay trong lúc render là thứ quy tắc
     `react-hooks/refs` cấm, và lý do cũng thật — một lần render bị React bỏ đi
     vẫn kịp đọc, nên hai bên có thể lệch nhau mà không ai báo. */
  const [needs, setNeeds] = useState<PetNeeds>(freshNeeds);
  const [treat, setTreat] = useState<{ x: number; y: number; scale: number } | null>(null);
  const [bits, setBits] = useState<Bit[]>([]);

  /* Vòng lặp animation đọc `full` mà không được dựng lại mỗi lần nó đổi, nên nó
     đọc qua một ref. Gán trong hiệu ứng chứ không giữa lúc render — quy tắc
     `react-hooks/refs`, và nó có lý do: ghi ref lúc render thì lần render bị bỏ
     đi (StrictMode, hoặc render tranh chấp) vẫn để lại dấu vết. */
  const fullRef = useRef(false);
  useEffect(() => {
    fullRef.current = full;
  }, [full]);

  /* Hẹn giờ xoá các mẩu bay lên. Gom lại để tháo sạch khi component bị gỡ —
     một `setTimeout` gọi `setState` sau khi gỡ là một cảnh báo React và, tệ hơn,
     một rò rỉ nếu người dùng mở đóng bảng nhiều lần. */
  const timers = useRef<number[]>([]);
  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      timers.current = [];
    },
    [],
  );

  const spawnBits = useCallback((icon: Bit["icon"], count: number) => {
    const pet = petRef.current;
    const spot = pointAt(pet.d);
    setBits((prev) => {
      const made: Bit[] = Array.from({ length: count }, (_, i) => ({
        id: Date.now() + i + Math.random(),
        x: spot.x + (Math.random() - 0.5) * 26,
        y: spot.y - mascotRef.current.cell.h * spot.scale * 0.62 - Math.random() * 10,
        icon,
        drift: (Math.random() - 0.5) * 34,
        scale: spot.scale,
      }));
      const ids = new Set(made.map((m) => m.id));
      timers.current.push(
        window.setTimeout(() => setBits((cur) => cur.filter((b) => !ids.has(b.id))), 1200),
      );
      return [...prev, ...made];
    });
  }, []);

  const setIntent = useCallback((pet: Pet, intent: PetIntent) => {
    if (pet.intent === intent) return;
    pet.intent = intent;
    pet.frame = 0;
    pet.frameAcc = 0;
  }, []);

  const wake = useCallback(
    (pet: Pet) => {
      pet.lastInput = performance.now();
      if (pet.intent === "sleep") setIntent(pet, "stand");
    },
    [setIntent],
  );

  const hop = useCallback(
    (pet: Pet) => {
      if (pet.jumpStart !== null) return;
      if (pet.intent === "sleep") {
        // Đánh thức trước đã: khung hình đầu của bộ nhảy đứng thẳng, nên nhảy
        // thẳng từ tư thế nằm trông như dịch chuyển tức thời.
        setIntent(pet, "stand");
        return;
      }
      pet.jumpStart = performance.now();
    },
    [setIntent],
  );

  /** Chọc — cũng là thứ xảy ra khi bấm thẳng vào con thú. */
  const poke = useCallback(() => {
    const pet = petRef.current;
    wake(pet);
    pet.goTo = null;
    hop(pet);
    spawnBits("heart", 3);
    needsRef.current = applyAction(needsRef.current, "poke");
  }, [hop, needsRef, spawnBits, wake]);

  const act = useCallback(
    (action: PetAction) => {
      const pet = petRef.current;
      const asleep = pet.intent === "sleep";
      if (refuse(needsRef.current, action, asleep)) return;

      if (action === "rest") {
        pet.lastInput = performance.now();
        pet.goTo = null;
        if (asleep) {
          setIntent(pet, "stand");
          return;
        }
        if (pet.jumpStart !== null || pet.task !== null) return;
        // Nằm luôn quay mặt sang phải: tư thế nằm đổ người về phía trước, và
        // quay trái thì nó đổ ra ngoài mép khung.
        pet.dir = 1;
        setIntent(pet, "sleep");
        return;
      }

      wake(pet);
      if (action === "poke") {
        poke();
        return;
      }
      if (action === "walk") {
        const target = LANDMARKS[Math.floor(Math.random() * LANDMARKS.length)]!;
        pet.goTo = target.at;
        needsRef.current = applyAction(needsRef.current, "walk");
        return;
      }
      if (action === "feed") {
        /*
         * Miếng ăn rơi xuống một chỗ CÁCH con thú một quãng, rồi nó tự đi tới.
         *
         * Đặt ngay dưới chân thì "cho ăn" chỉ là một con số nhảy lên — cả hành
         * động gói gọn trong một khung hình và không có gì để nhìn. Đi tới chỗ
         * ăn là phần khiến nó ra dáng một con vật.
         */
        const away = (140 + Math.random() * 120) * (Math.random() < 0.5 ? -1 : 1);
        const at = Math.max(0, Math.min(PATH_LENGTH, pet.d + away));
        pet.treatAt = at;
        pet.goTo = at;
        pet.task = "toFood";
        setBusy(true);
        const spot = pointAt(at);
        setTreat({ x: spot.x, y: spot.y, scale: spot.scale });
      }
    },
    [needsRef, poke, setIntent, wake],
  );

  /* Bàn phím chỉ nghe khi bảng đang mở, và bỏ qua khi con trỏ ở một ô nhập liệu
     — nếu không thì gõ chữ "s" vào ô tìm kiếm sẽ ru con thú ngủ. */
  useEffect(() => {
    const inField = (event: KeyboardEvent) => {
      const el = event.target as HTMLElement | null;
      const tag = el?.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable;
    };
    const down = (event: KeyboardEvent) => {
      if (inField(event)) return;
      const pet = petRef.current;
      if (event.key === "ArrowLeft") pet.input = -1;
      else if (event.key === "ArrowRight") pet.input = 1;
      else if (event.key === " " || event.key === "ArrowUp") {
        event.preventDefault();
        poke();
        return;
      } else if (event.key.toLowerCase() === "s") {
        act("rest");
        return;
      } else if (event.key.toLowerCase() === "f") {
        act("feed");
        return;
      } else if (event.key === "Escape") {
        onClose();
        return;
      } else if (event.key === "Shift") {
        pet.running = true;
        return;
      } else {
        return;
      }
      pet.goTo = null;
      wake(pet);
    };
    const up = (event: KeyboardEvent) => {
      const pet = petRef.current;
      if (event.key === "Shift") pet.running = false;
      else if (
        (event.key === "ArrowLeft" && pet.input === -1) ||
        (event.key === "ArrowRight" && pet.input === 1)
      ) {
        pet.input = 0;
      }
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [act, onClose, poke, wake]);

  /*
   * MỘT vòng lặp cho vị trí, khung hình, camera, lớp hạt và chỉ số.
   *
   * Bản trước tách làm hai — `requestAnimationFrame` cho vị trí và `setInterval`
   * cho khung hình — và đó là nguồn của cảm giác giật: hai đồng hồ trôi khỏi
   * nhau nên chân bước và thân dịch không khớp pha.
   *
   * Mọi chuyển động tính theo GIÂY, nên tốc độ không đổi trên màn 120Hz hay khi
   * trình duyệt bỏ vài khung.
   */
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const pet = petRef.current;
    pet.lastInput = last;
    let shownMood: PetIntent = pet.intent;
    let shownPlace = "";
    let shownIntent = "";
    let lastLit = "";
    /* Chỉ số đẩy sang React khi Ô hiển thị đổi, không phải mỗi khung hình: thanh
       chỉ có 8 ô, nên 60 lần dựng lại mỗi giây cho ra đúng cùng một hình. */
    let shownSegments = "";

    /*
     * Lớp hạt chạy trong CÙNG vòng lặp này chứ không có `requestAnimationFrame`
     * riêng. Hai vòng lặp thì hai `dt` khác nhau, và đốm lửa sẽ trôi lệch pha
     * với con thú mỗi khi máy tải nặng.
     *
     * `prefers-reduced-motion` tắt hẳn lớp này. Khối `prefers-reduced-motion`
     * sẵn có ở globals.css chỉ với tới CSS animation, không với tới canvas.
     */
    const reduced =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const fx = reduced ? null : createFx();
    const fxCtx = fxRef.current?.getContext("2d") ?? null;

    const step = (now: number) => {
      raf = requestAnimationFrame(step);
      // Kẹp bước thời gian: chuyển tab đi rồi quay lại cho một `dt` khổng lồ, đủ
      // để con thú "dịch chuyển" qua nửa bản đồ trong đúng một khung hình.
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;

      const asleep = pet.intent === "sleep";

      // 1. Việc đang làm dở thắng mọi thứ khác.
      if (pet.task === "eating" && now >= pet.taskUntil) {
        pet.task = null;
        pet.treatAt = null;
        setTreat(null);
        setBusy(false);
        needsRef.current = applyAction(needsRef.current, "feed");
        spawnBits("spark", 4);
        hop(pet);
      }

      // 2. Ý định: người dùng bấm, đích đã đặt, hay tự nó đi.
      let dir: -1 | 0 | 1 = pet.input;
      if (dir === 0 && pet.jumpStart === null && !asleep && pet.task !== "eating") {
        if (pet.goTo !== null) {
          dir = pet.goTo > pet.d ? 1 : -1;
          if (Math.abs(pet.goTo - pet.d) < REACHED) {
            pet.goTo = null;
            dir = 0;
            if (pet.task === "toFood") {
              pet.task = "eating";
              pet.taskUntil = now + EAT_MS;
              spawnBits("crumb", 3);
            }
          }
        } else {
          const quietFor = now - pet.lastInput;
          if (pet.task === null && quietFor > IDLE_BEFORE_SLEEP_MS) {
            pet.dir = 1;
            setIntent(pet, "sleep");
          } else if (
            pet.task === null &&
            quietFor > IDLE_BEFORE_WANDER_MS &&
            Math.random() < dt * 0.5
          ) {
            // Đi tới một MỐC CÓ TÊN chứ không tới một chỗ ngẫu nhiên: khu trại
            // có những chỗ đáng đến, và dừng giữa quãng trống trông như hết pin.
            pet.goTo = LANDMARKS[Math.floor(Math.random() * LANDMARKS.length)]!.at;
          }
        }
      }

      // 3. Vị trí dọc đường đi.
      if (dir !== 0 && !asleep && pet.task !== "eating") {
        const speed = pet.running && pet.input !== 0 ? RUN_SPEED : WALK_SPEED;
        pet.d = Math.max(0, Math.min(PATH_LENGTH, pet.d + dir * speed * dt));
        pet.dir = dir;
      } else if (pet.task === "eating" && pet.treatAt !== null) {
        // Quay mặt về phía miếng ăn trong lúc nhai.
        pet.dir = pet.treatAt >= pet.d ? 1 : -1;
      }
      const spot = pointAt(pet.d);

      // 4. Ý định hoạt ảnh. Nhảy thắng tất cả; ngủ chỉ bị phá bởi thao tác người dùng.
      let height = 0;
      const jumpClip = clipOf(mascotRef.current, "hop");
      if (pet.jumpStart !== null) {
        const t = (now - pet.jumpStart) / JUMP_MS;
        if (t >= 1) {
          pet.jumpStart = null;
          setIntent(pet, "stand");
        } else {
          setIntent(pet, "hop");
          height = arc(t);
          pet.frame = Math.min(jumpClip.frames - 1, Math.floor(t * jumpClip.frames));
        }
      }
      if (pet.jumpStart === null && !asleep) {
        setIntent(pet, dir === 0 ? "stand" : pet.running && pet.input !== 0 ? "run" : "walk");
      }

      // 5. Khung hình cho các clip chạy theo đồng hồ.
      const clip = clipOf(mascotRef.current, pet.intent);
      if (clip.fps > 0) {
        pet.frameAcc += dt * clip.fps;
        pet.frame = clip.loop
          ? Math.floor(pet.frameAcc) % clip.frames
          : Math.min(clip.frames - 1, Math.floor(pet.frameAcc));
      }

      // 6. Chỉ số.
      needsRef.current = decayNeeds(
        needsRef.current,
        dt,
        asleep ? "resting" : dir !== 0 ? "moving" : "still",
      );
      const n = needsRef.current;
      const segments = `${Math.ceil(n.fullness * 8)}:${Math.ceil(n.energy * 8)}:${Math.ceil(n.mood * 8)}`;
      if (segments !== shownSegments) {
        shownSegments = segments;
        setNeeds({ ...n });
      }

      // 7. Camera. Ở toàn cảnh thì cả bức tranh vừa khít nên không có gì để bám.
      const zoom = fullRef.current ? FULL_ZOOM : 1;
      const viewW = fullRef.current ? WORLD_W * FULL_ZOOM : VIEW_W;
      const viewH = fullRef.current ? WORLD_H * FULL_ZOOM : VIEW_H;
      const wantX = Math.max(0, Math.min(WORLD_W - viewW / zoom, spot.x - viewW / zoom / 2));
      const wantY = Math.max(0, Math.min(WORLD_H - viewH / zoom, spot.y - (viewH / zoom) * 0.62));
      const k = Math.min(1, CAM_LERP * dt);
      pet.camX += (wantX - pet.camX) * k;
      pet.camY += (wantY - pet.camY) * k;

      // 8. Lớp hạt của bối cảnh: sao, mặt nước, đốm lửa, đom đóm.
      if (fx && fxCtx) fx.draw(now, dt, fxCtx);

      // 9. Ghi thẳng vào DOM.
      const world = worldRef.current;
      if (world) {
        world.style.transform = `scale(${zoom}) translate3d(${-Math.round(pet.camX)}px, ${-Math.round(pet.camY)}px, 0)`;
      }
      const node = spriteRef.current;
      if (node) {
        const m = mascotRef.current;
        node.style.backgroundImage = `url(${sheetUrl(m, pet.intent)})`;
        node.style.backgroundPosition = `${-pet.frame * m.cell.w}px 0`;
        /*
         * Ý ĐỊNH được ghi ra DOM, không phải tên clip: đó là từ vựng không đổi
         * khi đổi mascot, nên một bài kiểm bám vào nó vẫn đúng sau khi thay ảnh.
         */
        if (pet.intent !== shownIntent) {
          shownIntent = pet.intent;
          node.dataset.intent = pet.intent;
        }
        /*
         * Chỉ ghi lại khi ánh sáng thực sự đổi: `filter` là chuỗi, nên gán mỗi
         * khung hình bắt trình duyệt phân tích lại nó 60 lần/giây để ra cùng một
         * kết quả. Lưới 6px là dưới ngưỡng mắt thấy được.
         *
         * So sánh KHOÁ đã làm tròn chứ không so khoảng cách với vị trí trước.
         * Bản đầu viết `Math.abs(spot.x - lastLitX) > 6` với `lastLitX = NaN`, và
         * mọi so sánh với NaN đều sai — nên lần ghi đầu tiên không bao giờ xảy
         * ra, `filter` mãi rỗng, và toàn bộ phần ánh sáng lặng lẽ không chạy mà
         * không ném lỗi nào.
         */
        const litKey = `${Math.round(spot.x / 6)}:${Math.round(spot.y / 6)}`;
        if (litKey !== lastLit) {
          lastLit = litKey;
          node.style.filter = lightingAt(spot.x, spot.y);
        }
        /*
         * `transform-origin` đặt ở (anchorX, footY), nên `scale` co giãn quanh
         * BÀN CHÂN con thú. Sau phép co, `translate` đưa đúng điểm đó tới chỗ
         * đứng — vì điểm gốc của phép co là điểm duy nhất không dịch chuyển. Cú
         * nhảy cũng nhân `scale`: nhảy cao 46px ở gần và ở xa là hai độ cao khác
         * nhau trong cùng một phối cảnh.
         */
        node.style.transform =
          `translate3d(${Math.round(spot.x - mascotRef.current.anchorX)}px, ` +
          `${Math.round(spot.y - mascotRef.current.footY - height * spot.scale)}px, 0) ` +
          `scale(${(pet.dir * spot.scale).toFixed(3)}, ${spot.scale.toFixed(3)})`;
      }

      if (pet.intent !== shownMood) {
        shownMood = pet.intent;
        setMood(pet.intent);
      }
      if (spot.label !== shownPlace) {
        shownPlace = spot.label;
        setPlace(spot.label);
      }
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [hop, needsRef, setIntent, spawnBits]);

  /* Giữ nút bằng chuột/ngón tay. `pointerup` gắn lên `window` chứ không lên nút:
     thả tay ở ngoài nút thì nút không nhận sự kiện, và con thú đi mãi. */
  const hold = useCallback(
    (value: -1 | 1) => ({
      onPointerDown: (event: React.PointerEvent) => {
        event.preventDefault();
        const pet = petRef.current;
        pet.input = value;
        pet.goTo = null;
        wake(pet);
        const release = () => {
          petRef.current.input = 0;
          window.removeEventListener("pointerup", release);
          window.removeEventListener("pointercancel", release);
        };
        window.addEventListener("pointerup", release);
        window.addEventListener("pointercancel", release);
      },
    }),
    [wake],
  );

  const viewW = full ? WORLD_W * FULL_ZOOM : VIEW_W;
  const viewH = full ? WORLD_H * FULL_ZOOM : VIEW_H;

  return (
    <div style={{ width: viewW }}>
      {/* `shadow-overlay` — ngoại lệ hợp lệ của luật cấm đổ bóng (§6.3): đây là
          lớp phủ thật, nằm ĐÈ lên nội dung chứ không nằm cạnh. */}
      <div className="shadow-overlay rounded border border-rule-strong bg-panel">
        <div className="flex items-center justify-between gap-2 border-b border-rule px-3 py-2">
          <p className="flex min-w-0 items-center gap-2 text-label font-semibold uppercase tracking-wide text-ink-muted">
            <PixelIcon name="paw" scale={1} />
            <span className="truncate">
              {busy ? "đang ăn" : MOODS[mood]}
              {place && mood !== "sleep" && !busy ? ` · ${place}` : ""}
            </span>
          </p>
          {/* Hai nút này là điều khiển CỬA SỔ, không phải đồ chơi của con thú —
              nên chúng giữ bộ icon chung của ứng dụng thay vì dùng pixel. Ranh
              giới là: đồ hoạ của con thú thì pixel, khung cửa sổ thì không. */}
          <span className="flex shrink-0 items-center gap-0.5">
            <MascotPicker picked={picked} onPick={onPick} />
            <button
              type="button"
              onClick={() => setFull((v) => !v)}
              aria-label={full ? "Thu về cửa sổ nhỏ" : "Xem toàn cảnh khu trại"}
              title={full ? "Thu về cửa sổ nhỏ" : "Xem toàn cảnh khu trại"}
              className="rounded p-1 text-ink-muted transition-colors hover:bg-recess hover:text-ink"
            >
              {full ? (
                <Minimize2 size={15} strokeWidth={2} aria-hidden />
              ) : (
                <Maximize2 size={15} strokeWidth={2} aria-hidden />
              )}
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Đóng góc thú cưng"
              className="rounded p-1 text-ink-muted transition-colors hover:bg-recess hover:text-ink"
            >
              <X size={15} strokeWidth={2} aria-hidden />
            </button>
          </span>
        </div>

        {/*
         * Ống nhòm nhìn vào khung cảnh. Lớp trong mang CẢ bức tranh ở cỡ thật và
         * bị dịch đi; lớp ngoài cắt. Làm ngược lại — dịch riêng ảnh nền bằng
         * `background-position` — thì con thú phải được dịch bằng một phép tính
         * thứ hai, và hai phép tính đó sẽ trôi khỏi nhau ở đúng chỗ khó thấy
         * nhất là lúc camera chạm biên.
         */}
        <div
          className="relative overflow-hidden border-b border-rule bg-[#0d1017]"
          style={{ width: viewW, height: viewH }}
        >
          <div
            ref={worldRef}
            className="absolute left-0 top-0 origin-top-left bg-cover"
            style={{
              width: WORLD_W,
              height: WORLD_H,
              backgroundImage: "url(/landscape/petland-2.jpg)",
            }}
          >
            {/*
             * Canvas đứng TRƯỚC con thú trong DOM, nên con thú vẽ đè lên nó —
             * đúng thứ tự: đốm lửa và đom đóm là ánh sáng của khung cảnh, còn
             * con thú đứng trong khung cảnh đó.
             */}
            <canvas
              ref={fxRef}
              width={WORLD_W}
              height={WORLD_H}
              aria-hidden
              className="pointer-events-none absolute left-0 top-0"
            />

            {treat && (
              /* Miếng ăn là phần tử DOM chứ không vẽ lên canvas hiệu ứng: canvas
                 kia thuộc về BỐI CẢNH và bị thay cùng bức tranh, còn miếng ăn
                 thuộc về con thú. `scale` lấy theo phối cảnh chỗ nó nằm. */
              <span
                aria-hidden
                className="pointer-events-none absolute"
                style={{
                  left: treat.x,
                  top: treat.y,
                  transform: `translate(-50%, -100%) scale(${treat.scale})`,
                  transformOrigin: "center bottom",
                }}
              >
                <PixelIcon name="bone" scale={2} />
              </span>
            )}

            <button
              type="button"
              ref={spriteRef}
              onClick={poke}
              aria-label="Chọc cho thú cưng phản ứng"
              className="absolute left-0 top-0 cursor-pointer bg-transparent bg-no-repeat p-0"
              style={{
                width: mascot.cell.w,
                height: mascot.cell.h,
                transformOrigin: `${mascot.anchorX}px ${mascot.footY}px`,
              }}
            />

            <PixelBits bits={bits} />
          </div>
        </div>

        <PetHud
          needs={needs}
          asleep={mood === "sleep"}
          busy={busy}
          onAction={act}
          leading={
            <>
              <MoveButton label="Đi sang trái (←)" {...hold(-1)}>
                <ArrowLeft size={15} strokeWidth={2} aria-hidden />
              </MoveButton>
              <MoveButton label="Đi sang phải (→)" {...hold(1)}>
                <ArrowRight size={15} strokeWidth={2} aria-hidden />
              </MoveButton>
              <span aria-hidden className="mx-0.5 h-5 w-px bg-rule" />
            </>
          }
        />
      </div>
    </div>
  );
}

function MoveButton({
  label,
  children,
  className,
  ...props
}: React.ComponentProps<"button"> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cx(
        "inline-flex h-8 min-w-8 items-center justify-center rounded border border-rule-strong px-2 text-ink transition-colors hover:bg-recess",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
