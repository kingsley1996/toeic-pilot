"use client";

import { API_ROUTES, type EncounterPublic, type PetPublic } from "@toeic-pilot/shared";
import { Gem, GripHorizontal, LayoutGrid, Maximize2, Minimize2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { clamp, defaultPlace, readPlace, writePlace, type Place } from "@/components/petland-place";
import { tileForGuest } from "@/components/petland-bestiary";
import { speechFor } from "@/components/petland-speech";
import { CollectionScreen } from "@/components/petland-collection";
import { QuestCard } from "@/components/petland-quest";
import { GuestList } from "@/components/petland-quest-list";
import { tierGlow } from "@/components/petland-creature";
import { PHASE_LABEL, worldClockLabel, worldTime } from "@/components/petland-clock";
import { EGG_PANEL_W, EggScreen } from "@/components/petland-eggs";
import { PetlandMusicToggle } from "@/components/petland-music-toggle";
import { PetHud, PixelBits, type Bit } from "@/components/petland-ui";
import { subscribeToCheer } from "@/lib/pet-cheer";
import { subscribeToPetOpen } from "@/lib/pet-open";
import { publishPet } from "@/lib/pet-state";
import { PixelIcon } from "@/components/pixel-icon";
import {
  advance,
  atRest,
  conditionOf,
  tricksOf,
  restAt,
  takeOver,
  wanderRange,
  type PetAction,
  type PetCondition,
  type PetNeeds,
  type PetTrick,
  type Steer,
} from "@/components/petland-pet";
import { cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import {
  findPath,
  isWalkable,
  isWater,
  nearestWalkable,
  neighbourOf,
  spotNear,
  strollTarget,
  TILE,
  type MapData,
  type Tile,
} from "@/components/petland-map";
import { loadPetlandMap } from "@/lib/petland-map-source";
import type { PetView, Stage } from "@/components/petland-render";

/**
 * Góc thú cưng: một khung nhìn nhỏ nhìn vào bản đồ ô, ở góc dưới bên trái.
 *
 * Bản trước cho con thú đi trên một ĐƯỜNG một chiều vẽ đè lên một bức tranh, và
 * vị trí của nó là một số vô hướng. Bản này là lưới thật (ADR-010): vị trí là
 * `(tx, ty)`, đường đi do BFS tìm, và nó **sống ở máy chủ** nên đóng tab không
 * đưa con thú về chỗ mặc định.
 *
 * **Pixi chỉ được nạp khi bảng MỞ RA**, và đó là ràng buộc chứ không phải tối
 * ưu để dành. Khối này nằm trong `SidebarShell`, tức có mặt ở mọi trang có
 * sidebar; nạp thư viện lúc mount nghĩa là 163 KB đi theo cả trang từ vựng lẫn
 * trang luyện đề. `await import()` nằm trong nhánh `open`.
 */

/**
 * Hoạt ảnh của mỗi hành động kéo dài bao lâu, tính bằng mili giây.
 *
 * "Đi dạo" dài hơn hẳn vì nó KHÔNG phải một tư thế: nó là quãng đường con thú
 * thật sự đi, và con số này chỉ để khoá cái nút cho tới khi chuyến đi trông như
 * đã bắt đầu. Đi hết đường mất bao lâu thì tuỳ đường.
 */
const ACTION_MS: Record<PetAction, number> = {
  feed: 1100,
  poke: 620,
  walk: 900,
  sleep: 700,
  wake: 700,
};

/** Đi dạo phải đi ĐỦ XA để nhìn ra là một chuyến đi, không phải một bước sang bên. */
const STROLL_MIN_TILES = 5;

/**
 * Mẩu nào bay lên cho hành động nào.
 *
 * `walk` KHÔNG có mẩu: chuyến đi tự nó đã là phản hồi, và một nắm dấu chân bay
 * lên trời trong lúc con thú đang đi bộ là hai lời kể về cùng một việc.
 */
const BIT_ICON: Record<PetAction, Bit["icon"]> = {
  feed: "crumb",
  poke: "spark",
  walk: "paw",
  sleep: "zzz",
  wake: "sun",
};

/** Khớp với `pet-bit-rise` trong `globals.css` (1100ms), cộng một nhịp thở. */
const BIT_LIFE_MS = 1300;

/**
 * Phím lái con thú: WASD, và cả bốn phím mũi tên.
 *
 * Thêm phím mũi tên vì nó không tốn gì và là thứ nửa số người thử đầu tiên —
 * còn WASD thì tay trái không phải rời bàn phím. Hai bộ trỏ vào cùng một đường,
 * nên không có hành vi thứ hai để mà lệch.
 */
const STEER: Record<string, { x: number; y: number }> = {
  w: { x: 0, y: -1 },
  a: { x: -1, y: 0 },
  s: { x: 0, y: 1 },
  d: { x: 1, y: 0 },
  arrowup: { x: 0, y: -1 },
  arrowleft: { x: -1, y: 0 },
  arrowdown: { x: 0, y: 1 },
  arrowright: { x: 1, y: 0 },
};

/** Bong bóng thoại đứng bao lâu. Đủ đọc một câu, rồi nhường lại khung cảnh. */
/** Nghỉ bao lâu giữa hai chuyến tự đi, nhân với 0,6–1,5 để nhịp không đều. */
const WANDER_PAUSE_MS = 6000;
/** Chờ trước chuyến ĐẦU TIÊN: mở bảng ra mà con thú đi ngay thì đọc ra là giật. */
const WANDER_FIRST_MS = 2500;

/**
 * Biểu tượng cảm xúc theo tình trạng. `null` nghĩa là im lặng.
 *
 * Bình thường thì không nói gì: một con thú đủ no đủ vui không có gì để báo, và
 * một biểu tượng hiện đều đặn dù chẳng có tin gì mới là thứ mắt học cách bỏ qua
 * trong hai ngày.
 */
const EMOTE_ICON: Record<PetCondition, Bit["icon"] | null> = {
  hungry: "crumb",
  exhausted: "moon",
  cheerful: "heart",
  content: null,
};

/** Nhịp giữa hai lần hiện cảm xúc. Thưa, vì nó là lời thì thầm chứ không phải báo động. */
const EMOTE_EVERY_MS = 14_000;

const SPEECH_MS = 4500;

/**
 * Trận đánh dài bao lâu.
 *
 * Ba nhịp lao tới trong quãng này, và với đòn kết liễu thì 30% cuối dành cho cú
 * ngã. Ngắn hơn thì ba nhịp dính vào nhau thành một cú rung; dài hơn thì người
 * học đã trả lời xong mà vẫn phải ngồi xem.
 */
const FIGHT_MS = 1200;

/** Dưới ngưỡng này thì trên đầu khách không đủ chỗ, bong bóng lật xuống dưới. */
const SPEECH_FLIP_PX = 56;

const VIEW_W = 14;
const VIEW_H = 8;
/*
 * Toàn bản đồ. Số cứng chứ không đọc từ `map.json`: khung phải có kích thước
 * NGAY khi bấm nút, còn bản đồ thì `Stage` mới biết. `setView` kẹp lại theo cỡ
 * thật, nên đặt rộng hơn bản đồ chỉ tốn một khoảng thừa chứ không vỡ gì.
 */
const FULL_W = 18;
const FULL_H = 13;
const ZOOM = 2;

/**
 * Chỗ khách đứng, gieo từ id.
 *
 * Bản đồ 18×13 và con thú mặc định ở (3,8), nên khách đứng trong khoảng giữa
 * bản đồ để luôn nằm trong khung nhìn 14×8 dù camera đang ở đâu. Ô rơi vào
 * tường thì `nearestWalkable` ở vòng vẽ kéo ra — cùng cách vị trí con thú được
 * xử lý sau khi bản đồ bị vẽ lại.
 */
export function PetLand() {
  const { token, status } = useSession();
  const [open, setOpen] = useState(false);

  /* Thẻ ở sidebar là đường vào chính; bảng nổi chỉ là chỗ nó bung ra. */
  useEffect(() => subscribeToPetOpen(() => setOpen(true)), []);
  const wrap = useRef<HTMLDivElement | null>(null);
  const place = useRef<Place | null>(null);
  const watcher = useRef<ResizeObserver | null>(null);

  /*
   * Vị trí ghi THẲNG vào `style`, không đi qua state.
   *
   * Kéo sinh hàng trăm sự kiện `pointermove` mỗi giây; mỗi cái một `setState` là
   * mỗi cái một lần dựng lại cả bảng — kèm cả canvas Pixi bên trong. Ghi thẳng
   * vào DOM cũng tránh luôn chuyện lệch hydrate: máy chủ không có `localStorage`
   * nên nó dựng ở chỗ mặc định, còn hiệu ứng thì chỉ chạy ở trình duyệt.
   */
  const settle = () => {
    const el = wrap.current;
    if (!el) return;
    const panel = { w: el.offsetWidth, h: el.offsetHeight };
    const screen = { w: window.innerWidth, h: window.innerHeight };
    const next = clamp(place.current ?? readPlace() ?? defaultPlace(panel, screen), panel, screen);
    place.current = next;
    el.style.left = `${next.x}px`;
    el.style.top = `${next.y}px`;
  };

  /*
   * Đặt chỗ ngay lúc node GẮN VÀO, qua ref callback — không qua `useEffect`.
   *
   * Đây là bẫy ba trạng thái của phiên, lần này hiện ra thành vị trí sai. Lượt
   * dựng đầu tiên `status` là `loading` nên component trả về `null`, tức
   * `wrap.current` còn rỗng khi hiệu ứng chạy và nó không làm được gì. Phiên
   * phân giải xong thì div mới gắn vào — nhưng danh sách phụ thuộc không đổi
   * nên hiệu ứng KHÔNG chạy lại, và bảng nằm nguyên ở toạ độ inline khởi tạo:
   * góc trên bên trái. Nạp lại trang là thấy ngay, còn điều hướng trong app thì
   * không, nên nó dễ lọt.
   *
   * Ref callback chạy đúng lúc node vào DOM, bất kể lượt dựng thứ mấy — và nó
   * chạy trong pha commit, trước khi trình duyệt vẽ, nên không có cú nháy nào.
   */
  const attach = useCallback((el: HTMLDivElement | null) => {
    wrap.current = el;
    watcher.current?.disconnect();
    if (!el) return;
    settle();
    /*
     * Kẹp lại mỗi khi bảng ĐỔI KÍCH THƯỚC, không chỉ khi mở/đóng.
     *
     * Bản trước chỉ kẹp theo cờ `open`, và nó bỏ sót hai đường: thanh chỉ số về
     * sau một lượt gọi API (bảng cao thêm), và nút xem toàn bản đồ (bảng rộng và
     * cao thêm). Cả hai đẩy phần dưới của bảng xuống dưới mép màn hình — nút
     * hiện ra nhưng bấm không tới, mà nhìn thì vẫn thấy nó nằm đó.
     *
     * `ResizeObserver` bắt mọi nguyên nhân, kể cả những nguyên nhân chưa được
     * viết ra — khác hẳn một danh sách phụ thuộc phải nhớ bổ sung.
     */
    const observer = new ResizeObserver(() => settle());
    observer.observe(el);
    watcher.current = observer;
    // `settle` chỉ đọc ref và `window`, không đọc props hay state, nên bản chụp
    // ở lượt dựng đầu vẫn đúng mãi.
  }, []);

  useEffect(() => {
    // Kẹp lại khi cửa sổ đổi cỡ: bảng kéo sang mép phải màn rộng sẽ nằm ngoài
    // vùng nhìn thấy trên màn hẹp, và lúc đó chuột không với tới để kéo về.
    window.addEventListener("resize", settle);
    return () => {
      window.removeEventListener("resize", settle);
      watcher.current?.disconnect();
    };
  }, []);

  const onDragStart = (event: React.PointerEvent) => {
    const el = wrap.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    const grabX = event.clientX - box.left;
    const grabY = event.clientY - box.top;
    (event.target as HTMLElement).setPointerCapture(event.pointerId);

    const move = (moveEvent: PointerEvent) => {
      place.current = { x: moveEvent.clientX - grabX, y: moveEvent.clientY - grabY };
      settle();
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (place.current) writePlace(place.current);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  if (status !== "authenticated" || !token) return null;

  return (
    <div
      ref={attach}
      className="fixed z-40 max-sm:origin-bottom-left max-sm:scale-[0.7]"
      /* Toạ độ khởi tạo nằm NGOÀI màn hình, không phải (20,20).
         `settle` chạy ngay khi node gắn vào nên bình thường không ai thấy nó ở
         đây — nhưng nếu có ngày `settle` không chạy được, một cái bảng vắng mặt
         là lỗi tự nói ra, còn một cái bảng nằm ở góc trên trái thì trông như một
         lựa chọn thiết kế. */
      style={{ left: -9999, top: -9999 }}
    >
      {/*
       * Đóng thì KHÔNG dựng gì cả — không còn nút thu gọn nổi trên nội dung.
       *
       * Thẻ thú cưng ở sidebar vừa là chỗ ở cố định vừa là đường vào, nên một
       * cái nút thứ hai nổi đè lên trang chỉ còn là thứ che nội dung. Nó cũng là
       * lý do `PetLand` không cần biết người học đang làm bài hay không nữa: con
       * thú chỉ hiện ra khi có người mở nó.
       *
       * Toast và lời thoại cũng không ở đây — chúng bám vào thẻ ở sidebar.
       */}
      {open && <PetPanel token={token} onDrag={onDragStart} onClose={() => setOpen(false)} />}
    </div>
  );
}

function PetPanel({
  token,
  onDrag,
  onClose,
}: {
  token: string;
  onDrag: (event: React.PointerEvent) => void;
  onClose: () => void;
}) {
  // `canPublish` LÀ "role === admin" (xem `lib/session.tsx`). Nút gọi khách chỉ
  // là công cụ thử, nhưng nó vẫn ghi vào database, nên nó theo đúng ranh giới mà
  // `/admin/pet` đã vẽ: vận hành, không phải biên tập.
  const { canPublish: isAdmin } = useSession();
  const host = useRef<HTMLDivElement | null>(null);
  const shell = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState(false);
  const [full, setFull] = useState(false);
  /*
   * Nhu cầu là STATE (thanh chỉ số phải vẽ lại), còn vị trí con thú là ref
   * (vòng lặp ghi 60 lần/giây). Hai thứ đổi ở hai nhịp khác hẳn nhau nên không
   * dùng chung một cơ chế: cho nhu cầu vào ref thì thanh không nhích, cho vị trí
   * vào state thì cả bảng dựng lại mỗi khung hình.
   */
  const [needs, setNeeds] = useState<PetNeeds | null>(null);
  const [pet, setPetHere] = useState<PetPublic | null>(null);

  /* Mọi con thú mới — lúc mở bảng, sau một hành động, sau khi đổi con — đều đi
     qua đây, nên thẻ ở sidebar không thể bị bỏ quên ở một nhánh nào đó. */
  const setPet = useCallback((next: PetPublic) => {
    setPetHere(next);
    publishPet(next);
  }, []);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  /*
   * Cột bên phải có HAI màn và mỗi lúc chỉ mở một: mở trứng, rồi xem tủ. Một cờ
   * bật/tắt cho mỗi màn sẽ cho phép cả hai cùng mở, và lúc đó bảng rộng gấp ba
   * bản đồ.
   */
  /**
   * MỘT ô bên phải, MỘT trạng thái nói ô ấy đang là gì.
   *
   * Trước đây là ba cờ độc lập (`side`, `questOpen`, `listKind`) và chúng mâu
   * thuẫn được với nhau: mở danh sách khách rồi bấm nút trứng thì `side` đổi
   * thành `"eggs"` trong khi `listKind` vẫn còn, nên màn trứng bị điều kiện
   * `!listKind` chặn lại và cái nút trông như hỏng. Không có lỗi nào để đọc —
   * chỉ là bấm mà không có gì xảy ra.
   *
   * Một biến thì trạng thái ấy không tồn tại được: mở cái này là đóng cái kia,
   * theo đúng nghĩa đen.
   */
  const [panel, setPanel] = useState<
    | null
    | { kind: "eggs" }
    | { kind: "collection" }
    | { kind: "list"; of: "npc" | "intruder" }
    | { kind: "quest" }
  >(null);
  const [meetings, setMeetings] = useState<EncounterPublic[]>([]);
  /**
   * Vị khách đang mở thẻ. `null` nghĩa là chưa chọn ai.
   *
   * Giữ ID chứ không giữ cả object: object được thay mới sau mỗi lần đọc lại
   * (mỗi phút một lần), và một bản sao cũ nằm trong state là một thẻ nhiệm vụ
   * hiện số bước cũ trong khi máy chủ đã đếm khác.
   */
  const [activeId, setActiveId] = useState<string | null>(null);

  /**
   * Khách và chỗ nó đứng, cho vòng vẽ đọc mỗi khung hình.
   *
   * Chỗ đứng do TRÌNH DUYỆT chọn, không do máy chủ: máy chủ không đọc
   * `map.json` — cùng lý do `PUT /pet/position` không kiểm ô đi được — nên nó
   * không biết ô nào đứng được. Chọn một lần khi khách đổi, rồi giữ nguyên:
   * chọn lại mỗi khung hình thì con vật nhảy loạn quanh bản đồ.
   */
  type Guest = { id: string; tile: number; x: number; y: number; danger: boolean };
  /**
   * Những vị khách đang đứng trên bản đồ, theo đúng thứ tự vẽ.
   *
   * Ở ref chứ không state vì vòng lặp vẽ đọc nó mỗi khung. Chỗ đứng của mỗi
   * người chốt MỘT LẦN (xem effect đặt chỗ), nên mảng này chỉ đổi khi có người
   * tới hoặc đi — không phải mỗi lần máy chủ trả lời.
   */
  const guestsRef = useRef<Guest[]>([]);
  /** Cầu nối một chiều từ cú bấm trong canvas ra React — cùng khuôn `strollRef`. */
  /**
   * Mở thẻ nhiệm vụ. `quiet` nghĩa là mở do HÚC vào, không do bấm.
   *
   * Húc vào thì người dùng đang lái bằng bàn phím, nên ô nhập của thẻ **không**
   * được tự lấy focus: lấy rồi thì phím W tiếp theo gõ chữ "w" vào ô đó thay vì
   * đi lên, và bàn phím trông như chết. Bấm chuột mở thẻ thì ngược lại — tay đã
   * rời bàn phím, tự đặt con trỏ vào ô nhập là đúng việc.
   */
  const openQuestRef = useRef<(id: string, quiet?: boolean) => void>(() => {});
  const [quietOpen, setQuietOpen] = useState(false);
  /*
   * Giờ Petland cho phần CHỮ, tách khỏi giờ cho phần VẼ.
   *
   * Bầu trời đọc đồng hồ mỗi khung hình vì nó phải đổi mượt; con số thì không —
   * cho nó vào state theo nhịp 60 khung/giây là dựng lại cả bảng sáu mươi lần
   * mỗi giây để đổi một chữ số mỗi hai giây rưỡi. Một ngày Petland dài một giờ
   * thật, nên một phút trong đó là 2,5 giây: hẹn giờ ở đúng nhịp ấy.
   */
  const [clock, setClock] = useState(() => ({ ...worldTime(Date.now()), at: Date.now() }));
  /*
   * Giữ `Stage` ở ref để nút toàn-bản-đồ gọi được `setView`, còn hiệu ứng dựng
   * sân khấu thì KHÔNG phụ thuộc vào `full`. Cho `full` vào danh sách phụ thuộc
   * cũng chạy, nhưng nó tháo cả sân khấu ra dựng lại mỗi lần bấm — mất một WebGL
   * context mỗi lần, và con thú nhảy về chỗ cũ giữa lúc đang đi.
   */
  const stageRef = useRef<Stage | null>(null);
  /*
   * Hoạt ảnh hành động sống trong REF, không trong state.
   *
   * Vòng `requestAnimationFrame` đọc nó 60 lần mỗi giây; để trong state thì mỗi
   * khung hình là một lần dựng lại cả bảng — và tệ hơn, vòng lặp có danh sách
   * phụ thuộc riêng nên nó sẽ giữ mãi giá trị của lần dựng đầu tiên (chính cái
   * bẫy closure đã ghi cho `mascot`).
   */
  const actionFx = useRef<{ kind: PetAction; start: number } | null>(null);
  /** Cầu nối một chiều: nút "Đi dạo" đặt vào đây, vòng lặp lấy ra và đi. */
  const strollRef = useRef(false);
  /**
   * Những phím hướng đang được GIỮ, theo thứ tự bấm.
   *
   * Một mảng chứ không một hướng: giữ D rồi bấm thêm W thì người ta muốn đi lên,
   * và thả W ra thì phải quay lại đi sang phải — chứ không đứng im vì "phím vừa
   * thả không còn". Phần tử cuối là hướng đang có hiệu lực.
   *
   * Ở ref vì vòng vẽ đọc nó mỗi khung hình; đưa vào state là dựng lại cả bảng
   * kèm canvas Pixi mỗi lần bấm một phím.
   */
  const heldRef = useRef<string[]>([]);
  /**
   * Vị khách con thú đang húc vào, hoặc `null`.
   *
   * Chỉ để phát hiện lúc CHUYỂN từ "chưa chạm" sang "đang chạm". Giữ phím áp
   * vào một NPC là sáu chục khung hình mỗi giây đều thấy "đang chạm", và mở thẻ
   * ở mỗi khung là sáu chục lần dựng lại cả bảng — kèm canvas Pixi bên trong.
   */
  const bumpRef = useRef<string | null>(null);
  /** Ô đang có khách đứng, để đường đi vòng qua họ thay vì xuyên thẳng. */
  const occupiedRef = useRef<ReadonlySet<string>>(new Set());
  /**
   * Ô sinh vật đang vẽ. REF chứ không state, cùng lý do `actionFx` là ref: vòng
   * vẽ không dựng lại khi state đổi, nên một closure giữ mãi con cũ và bộ sưu
   * tập trông như bấm không ăn.
   */
  const speciesRef = useRef(0);
  /**
   * Vòng sáng dưới chân, theo hạng hiếm. REF vì vòng vẽ đọc nó mỗi khung hình.
   *
   * Tính lại khi ĐỔI CON và khi đổi sáng/tối, không tính mỗi khung hình:
   * `getComputedStyle` là một lần đọc lại bố cục, và gọi nó 60 lần mỗi giây cho
   * một màu gần như không bao giờ đổi là trả tiền cho đúng thứ không xảy ra.
   */
  const glowRef = useRef<{ color: number; strength: number }>({ color: 0x9aaab5, strength: 0 });
  /**
   * Con thú đang ngủ. REF vì vòng vẽ đọc nó mỗi khung hình, và nó quyết định hai
   * việc: con thú không đi, và nó nằm thở chậm thay vì đứng.
   */
  const asleepRef = useRef(false);
  /**
   * Người dùng đã xin giảm chuyển động.
   *
   * REF vì vòng vẽ đọc nó mỗi khung hình, nhưng nghe `change` để đổi ngay khi
   * người dùng đổi cài đặt hệ điều hành — không bắt họ tải lại trang. Cùng khuôn
   * với `glowRef`, vốn cũng nghe sáng/tối.
   */
  const reducedRef = useRef(false);
  /** Tình trạng con thú, cho vòng vẽ đọc mỗi khung. Xem `conditionOf`. */
  const conditionRef = useRef<PetCondition>("content");
  /** Vốn tiết mục của con đang nuôi, theo bậc hiếm. Xem `tricksOf`. */
  const tricksRef = useRef<ReadonlySet<PetTrick>>(new Set());
  /** Ô con trỏ đang chỉ vào, cho tiết mục "nhìn theo con trỏ". */
  const pointerRef = useRef<Tile | null>(null);
  /**
   * Chỗ đứng cần NHẢY TỚI ngay, không phải đi bộ tới.
   *
   * Đổi con là đưa một con khác ra sân, nên nó xuất hiện ở chỗ CỦA NÓ chứ không
   * bước từ chỗ con cũ sang. Vị trí sống trong closure của vòng vẽ (`tile`,
   * `from`, `saved`), nên đây là đường duy nhất chạm tới được — cùng hình dạng
   * với `strollRef`.
   */
  const placeRef = useRef<{ x: number; y: number; facing: "left" | "right" } | null>(null);
  const [bits, setBits] = useState<Bit[]>([]);
  const [speech, setSpeech] = useState<string | null>(null);
  const bubble = useRef<HTMLDivElement | null>(null);
  const speechUntil = useRef(0);
  /** Ai đang nói — bong bóng phải mọc trên đầu đúng người đó, không phải người đầu mảng. */
  const speakingRef = useRef<string | null>(null);
  const refreshMeetings = useRef<() => void>(() => {});
  /*
   * Trận đánh đang chạy: mốc bắt đầu và có hạ gục được không.
   *
   * Ở ref chứ không ở state, cùng lý do mọi thứ khác trong vòng lặp vẽ: nó được
   * đọc mỗi khung hình, và một `setState` mỗi khung là dựng lại cả bảng kèm
   * canvas Pixi bên trong.
   */
  const fightRef = useRef<{ id: string; started: number | null; win: boolean } | null>(null);
  const [size, setSize] = useState({ w: VIEW_W, h: VIEW_H });

  /*
   * Bản đồ và ô con thú đang đứng, để chỗ chọn chỗ đứng cho khách đọc được.
   *
   * `mapReady` là STATE chứ không chỉ là ref: khách có thể tới trước lúc
   * `map.json` tải xong, và một ref thay đổi không chạy lại effect nào — khách
   * sẽ nằm mãi ở chỗ mặc định vì lượt tính duy nhất đã chạy lúc chưa có bản đồ.
   */
  const mapRef = useRef<MapData | null>(null);
  const petTileRef = useRef<Tile>({ x: 2, y: 2 });
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let alive = true;
    let stage: Stage | null = null;
    let raf = 0;

    let map: MapData | null = null;
    /*
     * Toàn bộ chuyện đi lại nằm trong MỘT object, và luật của nó sống ở
     * `petland-pet.ts`.
     *
     * Trước đây là năm biến rời (`tile`, `from`, `progress`, `queue`, `facing`)
     * cộng một máy trạng thái viết thẳng trong closure của `requestAnimationFrame`
     * — chỗ mà cách duy nhất để kiểm là bấm thử bằng tay, và một lỗi lệch một ô
     * thì mắt rất dễ bỏ qua. Ba lỗi liên tiếp đã ra từ đó. Tách sang một module
     * số học thuần thì `scripts/check-petland-walk.mjs` chạy được nó với `dt`
     * rung như khung hình thật, và cả ba lỗi ấy đều bị bắt.
     */
    let walk = restAt({ x: 0, y: 0 });
    /*
     * Con thú TỰ ĐI, và phạm vi đi phụ thuộc tình trạng (ADR-013 §4).
     *
     * Hôm nay nó chỉ đi khi được bảo đi, và một con vật đứng bất động cho tới
     * khi bị bấm là thứ không ai mở ra xem lần thứ hai. Đây cũng chính là chỗ ba
     * chỉ số trở nên nhìn thấy được: no và vui thì đi xa, đói thì quanh quẩn,
     * kiệt sức thì ngồi im.
     *
     * `ambient` đánh dấu chuyến đi là do NÓ tự quyết, và chuyến ấy KHÔNG ghi vị
     * trí lên máy chủ: một `PUT` mỗi mươi giây suốt lúc bảng mở là cái giá không
     * ai xin, và chỗ đứng do nó tự chọn thì cũng chẳng ai nhớ để mà tiếc.
     */
    let ambient = false;
    let idleUntil = 0;
    /*
     * Vòng vẽ DỪNG HẲN khi tab bị ẩn (ADR-010 §10).
     *
     * Trình duyệt tự giảm nhịp `requestAnimationFrame` ở tab nền, nhưng "tự
     * giảm" không phải "dừng", và mức giảm là chính sách của từng trình duyệt
     * chứ không phải thứ mình quyết. Cái vòng này vẽ WebGL sáu chục lần một
     * giây; để nó chạy sau lưng người dùng là đốt pin cho một khung hình không
     * ai nhìn.
     *
     * Giữ `loopRef` vì `loop` chỉ tồn tại sau khi sân khấu dựng xong, còn người
     * nghe sự kiện thì phải đăng ký từ đầu.
     */
    let loopRef: ((now: number) => void) | null = null;
    /*
     * Cầu nối để `onKeyDown` gọi được phép chọn ô kế tiếp.
     *
     * Phép ấy đọc `tile`, `map` và trạng thái ngủ — những thứ chỉ vòng vẽ mới
     * giữ đúng bản mới nhất — nên nó được dựng lại mỗi khung và cất ở đây. Viết
     * lại một bản thứ hai trong `onKeyDown` là hai định nghĩa cho "ô kế tiếp",
     * và chúng lệch nhau vào đúng ngày ai đó đổi luật đi lại.
     */
    const steerRef: { current: Steer } = { current: () => null };
    let last = performance.now();
    let saved: Tile = walk.tile;

    /*
     * Ghi vị trí khi con thú DỪNG HẲN, không phải mỗi ô.
     *
     * Đi qua mười hai ô là mười hai lần đổi vị trí; ghi từng lần là mười hai
     * request cho một cú bấm. Và các lệnh ghi phải NỐI TIẾP nhau — hai lệnh cách
     * nhau vài chục mili giây có thể về sai thứ tự, và khi đó chỗ lưu lại là chỗ
     * CŨ HƠN: vẫn hợp lệ, vẫn không lỗi, chỉ là sai. Cùng bài học `persistBoard`
     * của màn học từ vựng.
     */
    let writing: Promise<unknown> = Promise.resolve();
    const save = (at: Tile, dir: "left" | "right") => {
      if (at.x === saved.x && at.y === saved.y) return;
      saved = at;
      writing = writing
        .then(() =>
          apiFetch(API_ROUTES.petPosition, {
            method: "PUT",
            token,
            body: JSON.stringify({ tile_x: at.x, tile_y: at.y, facing: dir }),
          }),
        )
        // Mất một mốc vị trí thì lần sau con thú đứng hơi khác chỗ. Không đáng
        // để chặn thao tác, và càng không đáng để hiện lỗi.
        .catch(() => {});
    };

    /*
     * Lái bằng bàn phím: nghe ở `window`, nhưng có CỔNG "đang chơi ở bảng này".
     *
     * Ba bản trước đó, và vì sao hai bản đầu sai:
     *
     *   1. Nghe ở `window` trần — sai. Bảng nổi trên MỌI trang của khu học, kể
     *      cả màn gõ lại từ, nên gõ chữ "w" trong một bài tập sẽ lái con thú.
     *   2. Nghe ở riêng khung bản đồ, chỉ khi nó giữ focus — quá hẹp. Bấm bất
     *      cứ nút nào là bàn phím chết lặng, và không có gì nói vì sao.
     *   3. Nghe ở cả bảng — vẫn hụt, và chỗ hụt chỉ lộ ra khi đo: nút "Cho ăn"
     *      **tự mờ đi ngay sau khi bấm**, mà một phần tử disabled thì mất focus
     *      về `document.body` — tức là ra ngoài bảng. Sự kiện phím không bao giờ
     *      nổi tới đây nữa.
     *
     * Cổng `engaged` trả lời đúng câu hỏi thật: *bàn phím đang nói với ai?*
     * Người dùng chạm vào bảng thì nó nói với bảng, cho tới khi họ bấm hoặc
     * focus sang chỗ khác. Không phụ thuộc vào việc focus đang nằm ở đâu, nên
     * một cái nút tự mờ đi không cắt được đường.
     *
     * Ô nhập chữ vẫn phải bỏ qua — tập ĐÓNG và nhỏ: ô gõ từ và ô chép chính tả
     * của thẻ nhiệm vụ. Khung bản đồ vẫn nhận focus và có viền focus thấy được,
     * cho món nợ "không điều khiển được bằng bàn phím" của ADR-010 §10.
     */
    // Bảng vừa được người dùng mở ra, nên mặc định là đang nói với nó.
    let engaged = true;
    const onPointerAnywhere = (event: Event) => {
      const box = shell.current;
      engaged = box !== null && event.target instanceof Node && box.contains(event.target);
    };
    const isTyping = (target: EventTarget | null): boolean => {
      if (!(target instanceof HTMLElement)) return false;
      const tag = target.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (!engaged || isTyping(event.target)) return;
      const step = STEER[event.key.toLowerCase()];
      if (!step) return;
      // Phím mũi tên cuộn trang, và một cái bảng nổi làm trang nhảy dưới chân
      // người dùng thì tệ hơn là không lái được.
      event.preventDefault();
      if (event.repeat) return;
      const held = heldRef.current;
      const name = event.key.toLowerCase();
      if (!held.includes(name)) held.push(name);
      /*
       * Giành quyền lái, nhưng **để bước đang đi dở đi cho hết**.
       *
       * `slice(0, 1)` bỏ phần còn lại của tuyến do cú bấm chuột nạp — thứ có
       * thể dài cả chục ô và chặn bàn phím mất vài giây — mà vẫn giữ đúng ô
       * đang đi. Xoá sạch rồi đặt `progress = 0` như bản trước thì con thú
       * DỊCH TỚI ô đích ngay lập tức, vì `tile` đã là đích còn `from` mới là
       * chỗ xuất phát: đổi hướng giữa bước là một cú nhảy nửa ô.
       *
       * Và nạp ngay MỘT ô nếu đang đứng yên: vòng vẽ chỉ đọc trạng thái giữ mỗi
       * khung hình, nên một cú gõ nhanh hơn 16ms sẽ nhả phím trước khi vòng vẽ
       * kịp nhìn — bấm mà không có gì xảy ra, và đó chính là chỗ "không chính
       * xác" mà người dùng thấy.
       */
      /*
       * Bỏ phần còn lại của tuyến do cú bấm chuột nạp — thứ có thể dài cả chục ô
       * và chặn bàn phím mất vài giây — nhưng KHÔNG đụng vào bước đang đi.
       *
       * Bước đang đi là cặp (`from` → `tile`), không nằm trong hàng đợi, nên xoá
       * hàng đợi không làm con thú nhảy. Bản trước giữ lại `queue[0]`, tức là ô
       * kế tiếp theo hướng CŨ: bấm sang trái thì con thú vẫn đi thêm một ô sang
       * phải trước đã.
       *
       * Rồi nạp ngay một ô theo hướng mới: vòng vẽ chỉ đọc trạng thái GIỮ mỗi
       * khung hình, nên một cú gõ ngắn hơn 16ms nhả phím trước khi nó kịp nhìn —
       * bấm mà không có gì xảy ra.
       */
      takeOver(walk, steerRef.current);
      ambient = false;
      idleUntil = 0;
    };

    const onKeyUp = (event: KeyboardEvent) => {
      if (isTyping(event.target)) return;
      const name = event.key.toLowerCase();
      if (!STEER[name]) return;
      heldRef.current = heldRef.current.filter((key) => key !== name);
    };

    // Rời khỏi khung thì THẢ HẾT. Không có nó thì giữ W rồi chuyển sang cửa sổ
    // khác sẽ không bao giờ nhận được `keyup`, và con thú đi mãi về phía bắc cho
    // tới khi đụng tường — người dùng quay lại thấy nó ở một góc bản đồ mà họ
    // không nhớ đã dắt nó tới. Nghe ở CẢ cửa sổ, vì đổi tab không phải lúc nào
    // cũng làm phần tử đang focus nhận `blur`.
    const onBlur = () => {
      heldRef.current = [];
    };

    const onVisibility = () => {
      if (document.hidden) {
        cancelAnimationFrame(raf);
        raf = 0;
        // Và cả ticker của Pixi: nó là một vòng rAF THỨ HAI, độc lập với vòng
        // này. Dừng mỗi vòng của mình thì máy vẫn vẽ WebGL sau lưng người dùng.
        stage?.setRunning(false);
        // Thả hết phím: không có `keyup` nào tới trong lúc tab bị ẩn.
        heldRef.current = [];
        return;
      }
      stage?.setRunning(true);
      if (raf !== 0 || loopRef === null) return;
      // Đặt lại mốc thời gian trước khi chạy tiếp: `now - last` sau một tiếng
      // bị ẩn là một `dt` khổng lồ, và dù nó đã bị kẹp ở 0,1 giây thì con thú
      // vẫn nhảy một cái ngay lúc người dùng quay lại.
      last = performance.now();
      raf = requestAnimationFrame(loopRef);
    };

    const onPointerMove = (event: PointerEvent) => {
      pointerRef.current = stage?.tileAt(event.clientX, event.clientY) ?? null;
    };
    const onPointerLeave = () => {
      pointerRef.current = null;
    };

    const onClick = (event: MouseEvent) => {
      if (!stage || !map) return;
      const target = stage.tileAt(event.clientX, event.clientY);
      if (!target) return;
      /*
       * Bấm trúng khách thì MỞ THẺ, không dắt con thú tới đó: hai nghĩa trên
       * cùng một cú bấm thì cái nào cũng sai một nửa.
       *
       * Xét TRƯỚC cái chốt "đang ngủ", và đó là chỗ đã hỏng: giấc ngủ chỉ nên
       * khoá việc dắt con thú đi, còn trả lời một câu hỏi thì không liên quan
       * gì tới nó — người dùng bấm vào NPC trong lúc con thú ngủ và không có gì
       * xảy ra, không thông báo, không lý do.
       *
       * Vùng bấm cao HAI ô: sprite sinh vật neo ở đáy ô nên phần đầu và dấu
       * hiệu nhô lên ô phía trên, và người ta bấm vào chỗ nhìn thấy chứ không
       * vào ô mà nó "thuộc về".
       */
      // Người ĐỨNG THẤP nhất được ưu tiên: bốn vị khách có thể đứng gần nhau,
      // và người ở hàng dưới được vẽ đè lên người ở hàng trên — nên bấm phải
      // trúng người mắt đang nhìn thấy, không phải người tình cờ đứng trước
      // trong mảng.
      const guest = guestsRef.current
        .filter((one) => one.x === target.x && (one.y === target.y || one.y - 1 === target.y))
        .sort((a, b) => b.y - a.y)[0];
      if (guest) {
        openQuestRef.current(guest.id);
        /*
         * Con thú CHẠY TỚI chỗ khách, và nó dừng ở ô BÊN CẠNH.
         *
         * Đi vào đúng ô của khách thì hai sprite chồng khít lên nhau và con nào
         * đứng trước là chuyện của thứ tự thêm vào, không phải của khung cảnh.
         * `neighbourOf` chọn ô kề gần con thú nhất, nên nó đi đường ngắn nhất
         * chứ không vòng qua lưng người ta.
         *
         * Đang ngủ thì bỏ đoạn đi: vòng lặp chính đã xoá sạch đường đi khi ngủ,
         * nên xếp đường ở đây chỉ là xếp cho có. Thẻ nhiệm vụ vẫn mở như thường
         * — trả lời một câu hỏi không dính gì tới việc con thú đang ngủ.
         */
        if (!asleepRef.current) {
          const spot = neighbourOf(map, { x: guest.x, y: guest.y }, walk.tile);
          if (spot) walk.queue = findPath(map, walk.tile, spot, occupiedRef.current);
        }
        return;
      }
      if (asleepRef.current) return;
      walk.queue = findPath(map, walk.tile, target, occupiedRef.current);
      ambient = false;
      idleUntil = 0;
    };

    /*
     * Thanh chỉ số KHÔNG chờ gói WebGL.
     *
     * Cả ba việc chạy song song, nhưng bản trước chỉ `setPet`/`setNeeds` sau khi
     * `Promise.all` xong — tức là sau khi gói Pixi tải và biên dịch xong. Ở bản
     * dev có sẵn cache thì không ai thấy; ở bản production trên một máy nguội,
     * gói ấy là một tệp riêng phải tải về, và trong lúc đó bảng đã mở ra mà chưa
     * có "Lv" nào — đúng chỗ CI đỏ.
     *
     * Số liệu con thú đến từ một lượt gọi API và không dính gì tới việc vẽ, nên
     * nó phải hiện ngay khi API trả lời. Một promise, hai người tiêu thụ: không
     * gọi API hai lần.
     */
    const petLoad = apiFetch<PetPublic>(API_ROUTES.pet, { token });
    void petLoad
      .then((pet) => {
        if (!alive) return;
        setNeeds(pet.needs);
        setPet(pet);
      })
      .catch(() => {});

    void Promise.all([loadPetlandMap(), petLoad, import("@/components/petland-render")])
      .then(async ([loaded, pet, render]) => {
        const parsed = loaded?.map ?? null;
        if (!parsed || !alive) return;
        map = parsed;
        mapRef.current = parsed;
        setMapReady(true);
        // Ô đã lưu có thể trỏ vào tường sau khi bản đồ được vẽ lại trong trình
        // sửa. Kéo con thú ra chỗ đứng được thay vì để nó kẹt trong hàng rào.
        const start = nearestWalkable(parsed, { x: pet.tile_x, y: pet.tile_y });
        // Chỗ chọn chỗ đứng cho khách đo khoảng cách tới con thú, nên nó cần ô
        // này — và nó sống ngoài effect này.
        walk = restAt(start, pet.facing === "left" ? "left" : "right");
        petTileRef.current = start;
        saved = start;
        /*
         * Ô lấy TỪ MÁY CHỦ, không tra ở đây.
         *
         * Bảng loài là dữ liệu admin sửa được (`pet_species`), nên một bảng tra
         * thứ hai phía frontend sẽ trôi khỏi nó vào đúng ngày ai đó đổi ô của
         * một loài — và hậu quả là con thú vẽ nhầm hình, không phải một lỗi.
         */
        speciesRef.current = pet.tile;

        const made = await render.createStage(el, parsed, {
          zoom: ZOOM,
          viewW: VIEW_W,
          viewH: VIEW_H,
        });
        if (!alive) {
          made.destroy();
          return;
        }
        stage = made;
        stageRef.current = made;
        el.addEventListener("click", onClick);
        el.addEventListener("pointermove", onPointerMove);
        el.addEventListener("pointerleave", onPointerLeave);
        window.addEventListener("keydown", onKeyDown);
        window.addEventListener("keyup", onKeyUp);
        window.addEventListener("blur", onBlur);
        document.addEventListener("pointerdown", onPointerAnywhere, true);
        document.addEventListener("focusin", onPointerAnywhere, true);

        const loop = (now: number) => {
          const dt = Math.min(0.1, (now - last) / 1000);
          last = now;

          // Đổi con: đặt lại chỗ đứng TRƯỚC khi xử lý bước đi, nếu không con
          // mới sẽ đi nốt quãng đường mà con cũ đang đi dở.
          const jump = placeRef.current;
          if (jump && map) {
            placeRef.current = null;
            // Ô đã lưu có thể trỏ vào tường sau khi bản đồ được vẽ lại trong
            // trình sửa — cùng lý do lần nạp đầu cũng gọi `nearestWalkable`.
            const at = nearestWalkable(map, { x: jump.x, y: jump.y });
            walk = restAt(at, jump.facing);
            petTileRef.current = at;
            saved = at;
          }

          // "Đi dạo" đặt cờ; chỗ BIẾT bản đồ mới dựng được đường đi. Bấm lúc
          // đang đi thì bỏ qua — một tuyến mới đè lên tuyến cũ làm con thú quay
          // ngoắt giữa đường, đọc ra là giật chứ không phải đổi ý.
          // Đang ngủ thì không nhận đường đi mới, và bỏ luôn đường đang đi dở:
          // một con thú vừa ngủ vừa băng qua bản đồ đọc ra là hỏng.
          if (asleepRef.current) {
            strollRef.current = false;
            walk.queue = [];
          }

          if (strollRef.current) {
            strollRef.current = false;
            if (map && walk.queue.length === 0) {
              const target = strollTarget(map, walk.tile, STROLL_MIN_TILES, Math.random);
              if (target) {
                walk.queue = findPath(map, walk.tile, target, occupiedRef.current);
                ambient = false;
              }
            }
          }

          /*
           * Luật đi lại nằm ở `petland-pet.ts`; ở đây chỉ cấp cho nó ô kế tiếp.
           *
           * `steer` là thứ duy nhất còn ở lại, vì nó phải đọc bản đồ, trạng thái
           * ngủ và bảng phím — ba thứ thuộc về màn hình này chứ không thuộc về
           * số học của một bước đi.
           */
          /*
           * Ô nào đang có người đứng. Dựng lại mỗi khung hình vì danh sách khách
           * đổi được — nhiều nhất bốn phần tử, nên nó rẻ hơn mọi cách nhớ lại.
           */
          const occupied = new Map(
            guestsRef.current.map((guest) => [`${guest.x},${guest.y}`, guest.id] as const),
          );
          occupiedRef.current = new Set(occupied.keys());

          /*
           * HÚC VÀO một vị khách cũng là mở thẻ của họ, y như bấm chuột.
           *
           * Chỉ bắt lúc CHUYỂN từ "chưa chạm" sang "đang chạm" (`bumpRef`): giữ
           * phím áp vào một NPC là sáu chục khung hình mỗi giây đều thấy đang
           * chạm, và mở thẻ ở mỗi khung là sáu chục lần dựng lại cả bảng.
           *
           * Chỉ tính khi NGƯỜI DÙNG đang lái. Đi dạo là con thú tự đi, và một
           * cái thẻ nhiệm vụ tự bật ra giữa lúc người ta đang đọc thứ khác là
           * một cửa sổ chen ngang — `findPath` vòng qua khách thay vì húc vào.
           */
          const aim = heldRef.current;
          const aimKey = aim.length > 0 ? STEER[aim[aim.length - 1]] : null;
          const ahead = aimKey ? { x: walk.tile.x + aimKey.x, y: walk.tile.y + aimKey.y } : null;
          const bumped = ahead ? (occupied.get(`${ahead.x},${ahead.y}`) ?? null) : null;
          if (bumped !== null && bumped !== bumpRef.current) openQuestRef.current(bumped, true);
          bumpRef.current = bumped;

          const steer: Steer = (at) => {
            if (!map || asleepRef.current) return null;
            const held = heldRef.current;
            const key = held.length > 0 ? STEER[held[held.length - 1]] : null;
            if (!key) return null;
            // Đâm vào tường — hay vào một vị khách — thì đứng yên, nhưng VẪN
            // quay mặt về hướng ấy: một con thú không nhúc nhích mà cũng không
            // quay đầu đọc ra là phím không ăn, chứ không đọc ra là có vật cản.
            walk.facing = key.x < 0 ? "left" : key.x > 0 ? "right" : walk.facing;
            const next = { x: at.x + key.x, y: at.y + key.y };
            if (occupied.has(`${next.x},${next.y}`)) return null;
            return isWalkable(map, next.x, next.y) ? next : null;
          };
          steerRef.current = steer;

          /*
           * Tự đi lang thang. Chỉ khi ĐANG ĐỨNG YÊN và người dùng không lái —
           * nó không bao giờ được giành tay lái, chỉ lấp chỗ trống.
           *
           * Tắt hẳn khi người dùng xin giảm chuyển động: một khung cảnh tự động
           * đậy lên là đúng thứ họ vừa nói là không muốn.
           */
          if (map && atRest(walk) && !asleepRef.current && heldRef.current.length === 0) {
            /*
             * Tiết mục "nhìn theo con trỏ" (epic trở lên): đứng yên thì quay mặt
             * về phía con trỏ. Đặt `facing` chứ không dựng gì mới — con thú
             * trông như đang để ý tới người dùng, và đó là toàn bộ hiệu ứng.
             */
            const eye = pointerRef.current;
            if (eye && tricksRef.current.has("watch") && eye.x !== walk.tile.x) {
              walk.facing = eye.x < walk.tile.x ? "left" : "right";
            }

            if (idleUntil === 0) idleUntil = now + WANDER_FIRST_MS;
            else if (now >= idleUntil) {
              const range = wanderRange(conditionRef.current, reducedRef.current);
              /*
               * Tiết mục "tự tới chỗ khách" (legendary): thay vì đi lang thang
               * ngẫu nhiên, nó nhắm tới ô cạnh vị khách gần nhất.
               *
               * KHÔNG mở thẻ nhiệm vụ khi tới nơi — húc vào chỉ tính khi NGƯỜI
               * DÙNG đang lái (ADR-012), và một cái thẻ tự bật ra vì con thú đi
               * ngang qua là một cửa sổ chen ngang.
               */
              const guest = tricksRef.current.has("greet") ? guestsRef.current[0] : undefined;
              const toward =
                guest && range ? neighbourOf(map, { x: guest.x, y: guest.y }, walk.tile) : null;
              const spot =
                toward ?? (range ? strollTarget(map, walk.tile, 2, Math.random, range) : null);
              if (spot) {
                walk.queue = findPath(map, walk.tile, spot, occupiedRef.current);
                ambient = walk.queue.length > 0;
              }
              idleUntil = now + WANDER_PAUSE_MS * (0.6 + Math.random() * 0.9);
            }
          }

          const before = walk.tile;
          advance(walk, dt, steer);
          if (walk.tile !== before) petTileRef.current = walk.tile;
          // Ghi chỗ đứng khi ĐỨNG YÊN và không còn phím nào giữ. `save` tự bỏ
          // qua khi chưa đổi ô, nên gọi mỗi khung hình chỉ là một phép so sánh —
          // còn ghi từng ô thì đi mười hai ô là mười hai request.
          // Chuyến do NÓ tự đi thì không ghi — xem `ambient`.
          if (atRest(walk) && heldRef.current.length === 0 && !ambient) {
            save(walk.tile, walk.facing);
          }
          const fx = actionFx.current;
          let action: PetView["action"] = null;
          if (fx) {
            const t = (now - fx.start) / ACTION_MS[fx.kind];
            // Hết thì DỌN, không để `t` chạy quá 1: tư thế tính từ `sin`, nên
            // một `t` không có điểm dừng sẽ làm con thú nhai mãi mãi.
            if (t >= 1) actionFx.current = null;
            else action = { kind: fx.kind, t };
          }

          /*
           * Trận đánh: con thú phải TỚI NƠI rồi mới đánh.
           *
           * Trả lời từ cái nút trên thanh tiêu đề thì con thú có thể đang ở nửa
           * bản đồ bên kia, và một cú lao tới dài nửa ô ở đó chỉ là một cái nhích
           * — hoạt cảnh vẫn chạy, chỉ là không ai hiểu nó đang diễn tả cái gì.
           *
           * Ba lối thoát để nó không treo mãi, và treo thì hỏng nặng hơn là xấu:
           * `fightRef` còn giá trị nghĩa là vị khách bị giữ lại trên bản đồ sau
           * khi máy chủ đã báo xong. Nên vắng khách, đang ngủ, hay không có
           * đường đi đều đánh ngay tại chỗ.
           */
          const brawl = fightRef.current;
          let bout: PetView["fight"] = null;
          if (brawl && brawl.started === null) {
            const foe = guestsRef.current.find((one) => one.id === brawl.id) ?? null;
            const near =
              foe !== null && Math.abs(foe.x - walk.tile.x) + Math.abs(foe.y - walk.tile.y) <= 1;
            if (foe === null || asleepRef.current || (near && atRest(walk))) {
              brawl.started = now;
            } else if (walk.queue.length === 0 && map) {
              const spot = neighbourOf(map, { x: foe.x, y: foe.y }, walk.tile);
              walk.queue = spot ? findPath(map, walk.tile, spot, occupiedRef.current) : [];
              if (walk.queue.length === 0) brawl.started = now;
            }
          }
          if (brawl && brawl.started !== null) {
            const t = (now - brawl.started) / FIGHT_MS;
            if (t >= 1) {
              fightRef.current = null;
              // Hạ gục xong thì mới xoá vị khách. Máy chủ đã trả "xong" từ lúc
              // câu trả lời đúng, nhưng xoá ngay lúc ấy thì cú ngã không bao giờ
              // được vẽ — kẻ xâm nhập chỉ biến mất giữa không trung.
              if (brawl.win) {
                guestsRef.current = guestsRef.current.filter((one) => one.id !== brawl.id);
              }
            } else {
              bout = { id: brawl.id, t, win: brawl.win };
            }
          }

          made.draw({
            tile: walk.tile,
            from: walk.from,
            /*
             * Giảm chuyển động thì BỎ NỘI SUY: `1` nghĩa là vẽ thẳng ở ô đích.
             *
             * Con thú vẫn đi đúng từng ô và vẫn mất đúng ngần ấy thời gian —
             * chỉ là nó xuất hiện ở ô mới thay vì trượt tới đó. Đúng cách ADR-010
             * §10 chốt, và nó giữ được thứ quan trọng nhất: cái góc này vẫn chơi
             * được, chứ không bị tắt đi.
             */
            progress: reducedRef.current ? 1 : walk.progress,
            facing: walk.facing,
            species: speciesRef.current,
            glow: glowRef.current,
            // Giờ Petland tính lại MỖI KHUNG HÌNH, và nó rẻ hơn nhớ lại: một
            // phép chia lấy dư trên `Date.now()`. Nhớ lại rồi làm mới theo hẹn
            // giờ thì bầu trời nhảy bậc mỗi lần hẹn giờ chạy, đúng thứ bảng mốc
            // màu được nội suy để tránh.
            sky: worldTime(Date.now()).sky,
            clock: now / 1000,
            action,
            sleeping: asleepRef.current,
            encounters: guestsRef.current,
            fight: bout,
            reduced: reducedRef.current,
            condition: conditionRef.current,
            swimming: map !== null && isWater(map, walk.tile.x, walk.tile.y),
            tricks: {
              bounce: tricksRef.current.has("bounce"),
              trail: tricksRef.current.has("trail"),
              float: tricksRef.current.has("float"),
            },
          });

          /*
           * Bong bóng thoại bám theo đầu vị khách, ghi THẲNG vào `style`.
           *
           * Không đi qua state, cùng lý do vị trí bảng cũng không: đây là một
           * lần ghi mỗi khung hình, và một `setState` mỗi khung là dựng lại cả
           * bảng — kèm canvas Pixi bên trong — sáu chục lần một giây.
           *
           * Phải bám thật chứ không chốt lúc bấm: bấm xong thì con thú chạy tới,
           * máy quay xê dịch theo nó, và một chỗ đứng yên sẽ trôi khỏi cái đầu
           * mà nó đang chỉ vào.
           */
          const balloon = bubble.current;
          if (balloon) {
            const talker = speakingRef.current;
            const at = talker ? (stage?.guestScreen(talker) ?? null) : null;
            const showing = at !== null && now < speechUntil.current;
            balloon.style.opacity = showing ? "1" : "0";
            if (at) {
              // Khung bản đồ cắt phần tràn ra ngoài, nên một vị khách đứng sát
              // mép trên sẽ có bong bóng bị xén mất một nửa. Hết chỗ ở trên thì
              // LẬT XUỐNG DƯỚI — vẫn chỉ đúng người nói, chỉ đổi phía.
              const flip = at.y < SPEECH_FLIP_PX;
              balloon.style.left = `${at.x}px`;
              balloon.style.top = `${flip ? at.y + TILE * ZOOM + 6 : at.y - 10}px`;
              balloon.style.transform = flip ? "translate(-50%, 0)" : "translate(-50%, -100%)";
            }
          }
          raf = requestAnimationFrame(loop);
        };
        loopRef = loop;
        if (!document.hidden) raf = requestAnimationFrame(loop);
      })
      .catch(() => alive && setError(true));

    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      alive = false;
      document.removeEventListener("visibilitychange", onVisibility);
      cancelAnimationFrame(raf);
      el.removeEventListener("click", onClick);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerleave", onPointerLeave);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("pointerdown", onPointerAnywhere, true);
      document.removeEventListener("focusin", onPointerAnywhere, true);
      // `destroy` gỡ cả canvas lẫn texture khỏi GPU. Không gọi thì mỗi lần mở
      // lại bảng là một context WebGL nữa, và trình duyệt chỉ cho vài cái.
      stageRef.current = null;
      stage?.destroy();
    };
  }, [token, setPet]);

  /*
   * Màu vòng sáng đọc lại khi ĐỔI CON hoặc khi đổi sáng/tối.
   *
   * Một hiệu ứng chứ không phải gán tay ở từng chỗ đổi con: token màu có hai giá
   * trị (sáng và tối), nên người bấm nút chuyển chủ đề giữa chừng sẽ giữ màu của
   * chế độ cũ cho tới lần tải lại — và đó đúng là kiểu sai không ai báo, vì vòng
   * sáng vẫn có màu, chỉ là màu của bảng màu bên kia.
   *
   * Nghe cả hai đường vì chủ đề có BA trạng thái: `data-theme` khi người dùng
   * chọn tay, và `prefers-color-scheme` khi họ để theo hệ thống. Nghe một đường
   * là đúng cho một nửa số người dùng.
   */
  useEffect(() => {
    const tick = window.setInterval(
      () => setClock({ ...worldTime(Date.now()), at: Date.now() }),
      2500,
    );
    return () => window.clearInterval(tick);
  }, []);

  /*
   * Đang ngủ hay không suy ra từ MỐC, không từ một cờ.
   *
   * Máy chủ gửi `sleep_until`; giấc ngủ tự hết khi tới mốc, nên trình duyệt phải
   * tự nhận ra điều đó thay vì chờ một lần đọc mới. `clock` nhích mỗi 2,5 giây
   * nên phép so này được tính lại đủ dày, và con thú dậy trên màn hình gần như
   * đúng lúc nó dậy ở máy chủ.
   */
  /*
   * Vị khách đang mở thẻ, TRA LẠI từ danh sách mỗi lần dựng.
   *
   * Suy ra chứ không giữ trong state: danh sách được đọc lại mỗi phút, và một
   * bản sao cũ nằm trong state là một thẻ hiện số bước cũ trong khi máy chủ đã
   * đếm khác. Người ấy hết hạn hay làm xong thì `active` thành `undefined` và
   * thẻ tự đóng — không cần ai đi dọn.
   */
  const active = meetings.find((one) => one.id === activeId) ?? null;

  /*
   * Ô bên phải RỖNG thì coi như đóng.
   *
   * Một cuộc chạm mặt sống mười phút và có thể hết hạn ngay trong lúc thẻ của nó
   * đang mở: máy chủ bỏ nó khỏi danh sách ở lần đọc kế tiếp, `active` thành
   * `null`, và nếu chỉ nhìn `panel` thì bảng vẫn chừa nguyên chỗ cho một cái thẻ
   * không còn được vẽ — đúng cái khoảng trống bên cạnh bản đồ đã phải sửa một
   * lần rồi. Suy ra chứ không dọn bằng một effect: dọn bằng effect là thêm một
   * đường đổi state nữa phải giữ cho đồng bộ.
   */
  const shown = panel?.kind === "quest" && active === null ? null : panel;

  /*
   * Đóng ô bên phải thì TRẢ FOCUS về khung bản đồ.
   *
   * Bấm nút X là focus nằm trên chính cái nút vừa bị gỡ khỏi cây, và trình duyệt
   * đẩy nó ra `document.body` — ngoài bảng, nên bàn phím thôi lái được. Đó đúng
   * là triệu chứng "húc vào NPC rồi tắt đi thì phím không nhận".
   *
   * Chỉ trả khi focus đang ở TRONG bảng hoặc đã rơi ra `body`: nếu người dùng
   * đã chuyển sang gõ ở chỗ khác trên trang thì kéo focus về đây là cướp bàn
   * phím của họ.
   */
  const wasOpen = useRef(false);
  useEffect(() => {
    const open = shown !== null;
    if (wasOpen.current && !open) {
      const box = shell.current;
      const at = document.activeElement;
      if (box && (at === null || at === document.body || box.contains(at))) {
        host.current?.focus();
      }
    }
    wasOpen.current = open;
  }, [shown]);

  const asleep = pet?.sleep_until != null && new Date(pet.sleep_until).getTime() > clock.at;
  // Ghi ref trong EFFECT, không trong lúc dựng: `react-hooks` chặn thẳng việc
  // chạm ref lúc render, và luật đó đúng — một lượt dựng bị bỏ đi vẫn kịp để
  // lại dấu vết trong ref. Trễ một khung hình ở đây không ai thấy.
  useEffect(() => {
    asleepRef.current = asleep;
  }, [asleep]);

  useEffect(() => {
    // `null` là lúc chưa đọc xong lượt gọi đầu — coi như bình thường, chứ không
    // vẽ một con thú kiệt sức rồi sửa lại sau nửa giây.
    conditionRef.current = needs ? conditionOf(needs) : "content";
  }, [needs]);

  /*
   * Hỏi máy chủ có ai đang đứng chờ không — lúc mở bảng, rồi mỗi phút.
   *
   * Mỗi phút chứ không mỗi vài giây: nhịp sinh là hai mươi phút, nên hỏi dày
   * hơn chỉ tốn request mà không đổi được gì. Và mỗi lần hỏi là một lần MÁY CHỦ
   * có cơ hội sinh ra khách — đó là chủ ý (ADR-012 §1), không phải tác dụng phụ.
   */
  useEffect(() => {
    if (!token) return;
    let alive = true;
    const ask = () => {
      /*
       * Tab bị ẩn thì KHÔNG hỏi.
       *
       * Không phải để tiết kiệm một request: `GET /pet/encounters` là đường
       * SINH RA khách (ADR-012 §1), nên hỏi sau lưng người dùng nghĩa là một
       * NPC ra đời rồi hết hạn trong lúc họ không có mặt — đúng cái "bỏ lỡ một
       * thứ chưa từng có" mà cả cơ chế được dựng để không thể xảy ra.
       */
      if (document.hidden) return;
      apiFetch<EncounterPublic[]>(API_ROUTES.petEncounters, { token })
        .then((rows) => {
          if (alive) setMeetings(rows);
        })
        .catch(() => {});
    };
    // Bấm nút gọi khách xong phải thấy ngay, không đợi hết một phút. Cầu nối là
    // một ref vì `ask` sống trong effect này — chỗ duy nhất giữ được cờ `alive`.
    refreshMeetings.current = ask;
    ask();
    const tick = window.setInterval(ask, 60_000);
    // Quay lại thì hỏi NGAY, không đợi hết một phút: người dùng vừa có mặt trở
    // lại, và đó chính là lúc được phép sinh khách.
    document.addEventListener("visibilitychange", ask);
    return () => {
      alive = false;
      window.clearInterval(tick);
      document.removeEventListener("visibilitychange", ask);
    };
  }, [token]);

  /*
   * Chọn hình dạng và chỗ đứng cho khách, MỘT LẦN mỗi khách.
   *
   * Cả hai suy ra từ `encounter.id` chứ không do máy chủ gửi: bảng phân vai sinh
   * vật (`petland-bestiary.ts`) sống ở frontend, và bản đồ là một tệp tĩnh mà
   * máy chủ không đọc. Gieo từ id nên cùng một khách luôn ra cùng một con ở cùng
   * một chỗ, kể cả sau khi tải lại trang — bốc ngẫu nhiên mỗi lần dựng thì con
   * vật đổi hình giữa hai lần chớp mắt.
   */
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const kept = new Map(guestsRef.current.map((guest) => [guest.id, guest]));
    /*
     * Đặt chỗ MỘT LẦN cho mỗi vị khách, khoá theo `id`.
     *
     * Danh sách được đọc lại mỗi phút và mỗi câu trả lời, nên effect này chạy
     * lại liên tục — mà chỗ đứng lại đo theo ô con thú đang đứng. Không giữ lại
     * thì cả bản đồ xáo chỗ mỗi phút, và kẻ xâm nhập nhảy sang chỗ khác giữa
     * hai bước của chính nó.
     *
     * Người đã có thì giữ nguyên; người mới thì tránh cả những ô đã có người —
     * hai vị khách chồng khít lên nhau là một cú bấm không biết mở thẻ của ai.
     */
    const taken = new Set<string>();
    for (const guest of guestsRef.current) taken.add(`${guest.x},${guest.y}`);

    const next: Guest[] = [];
    for (const meeting of meetings) {
      const already = kept.get(meeting.id);
      if (already) {
        next.push(already);
        continue;
      }
      const danger = meeting.kind === "intruder";
      const seed = [...meeting.id].reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
      // Đứng được VÀ nhìn thấy được — xem `spotNear`. Bản cũ bốc bằng một công
      // thức thuần trên toạ độ bản đồ, nên khách vừa rơi vào tường vừa rơi ra
      // ngoài khung nhìn 14×8, và cả ba triệu chứng (không dấu hiệu, không bấm
      // được, đứng trong vật cản) đều là cùng một lỗi ấy.
      const spot = spotNear(map, petTileRef.current, seed, taken);
      taken.add(`${spot.x},${spot.y}`);
      next.push({
        id: meeting.id,
        tile: tileForGuest(meeting.id, danger ? "intruder" : "npc"),
        ...spot,
        danger,
      });
    }

    // Người vừa bị hạ gục ở lại thêm cho tới khi cú ngã diễn xong. Máy chủ đã
    // bỏ họ khỏi danh sách từ lúc câu trả lời đúng, nhưng xoá ngay lúc ấy thì
    // cú ngã không bao giờ được vẽ — kẻ xâm nhập biến mất giữa không trung.
    const falling = fightRef.current;
    if (falling?.win) {
      const victim = kept.get(falling.id);
      if (victim && !next.some((guest) => guest.id === victim.id)) next.push(victim);
    }
    guestsRef.current = next;
  }, [meetings, mapReady]);

  useEffect(() => {
    openQuestRef.current = (id: string, quiet = false) => {
      const guest = meetings.find((one) => one.id === id);
      if (!guest) return;
      setQuietOpen(quiet);
      setActiveId(id);
      setPanel({ kind: "quest" });
      setSpeech(speechFor(guest.id, guest.kind === "intruder", guest.steps_done));
      speakingRef.current = id;
      // Bong bóng tự tắt; thẻ nhiệm vụ ở bên cạnh mới là chỗ làm việc. Để nó
      // đứng mãi thì nó che mất chính con vật vừa nói.
      speechUntil.current = performance.now() + SPEECH_MS;
    };
  }, [meetings]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => {
      reducedRef.current = media.matches;
    };
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    tricksRef.current = tricksOf(pet?.tier);
  }, [pet?.tier]);

  const tier = pet?.tier;
  useEffect(() => {
    if (!tier) return;
    const refresh = () => {
      glowRef.current = tierGlow(tier);
    };
    refresh();
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", refresh);
    const watcher = new MutationObserver(refresh);
    watcher.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => {
      media.removeEventListener("change", refresh);
      watcher.disconnect();
    };
  }, [tier]);

  /*
   * Hành động đi thẳng lên máy chủ và lấy nhu cầu MỚI về, không tự tính ở đây.
   *
   * Tự cộng trước rồi gửi sau ("ghi lạc quan") là đúng cho việc đổi con mascot —
   * thứ không có gì để mất nếu trượt. Ở đây thì khác: máy chủ mới biết con thú đã
   * đói bao lâu, và một con số client tự nghĩ ra sẽ bị đè ngay ở lần đọc kế tiếp,
   * nên người dùng thấy thanh chỉ số nhảy lên rồi tụt xuống.
   */
  /**
   * Những mẩu bay lên khỏi đầu con thú.
   *
   * Neo theo chỗ con thú đang đứng TRONG canvas (`stage.petScreen()`), không
   * neo vào giữa bảng: con thú đi khắp bản đồ, nên một chỗ cố định sẽ thả nắm
   * vụn xuống một bụi cỏ nào đó cách nó nửa màn hình.
   *
   * Tự dọn sau khi hoạt ảnh CSS chạy xong. Không dọn thì mỗi lần bấm là thêm
   * vài node nằm lại vĩnh viễn, trong suốt nhưng vẫn được trình duyệt vẽ.
   */
  const spawnBits = useCallback((icon: Bit["icon"], count = 4) => {
    const stage = stageRef.current;
    if (!stage) return;
    const at = stage.petScreen();
    const born = Date.now();
    const made: Bit[] = Array.from({ length: count }, (_, i) => ({
      id: born + i,
      // Một mẩu lẻ thì bay thẳng trên đầu; cả nắm thì dàn ngang ra.
      x: at.x + (count === 1 ? 4 : (i - (count - 1) / 2) * 7),
      y: at.y - 6,
      icon,
      // Mỗi mẩu lệch một hướng: cả nắm bay thẳng đứng song song nhau đọc ra là
      // một hiệu ứng, không phải nhiều mẩu.
      drift: count === 1 ? 5 + Math.random() * 7 : (i - (count - 1) / 2) * 9,
      scale: 0.8 + (i % 2) * 0.2,
    }));
    setBits((current) => [...current, ...made]);
    window.setTimeout(
      () => setBits((current) => current.filter((b) => b.id < born || b.id >= born + count)),
      BIT_LIFE_MS,
    );
  }, []);

  /*
   * Bong bóng cảm xúc: THỈNH THOẢNG, không thường trực (ADR-013 §3).
   *
   * Một biểu tượng dính mãi trên đầu là một lời nhắc nợ, và cái góc này không
   * được phép có nợ. Nó chỉ nói "tôi đang thế này" rồi biến đi.
   *
   * Lúc bình thường thì im lặng — không có gì để nói thì đừng nói. Đang ngủ cũng
   * im: mẩu Zzz đã lo phần ấy rồi.
   */
  useEffect(() => {
    if (asleep) return;
    const icon = EMOTE_ICON[needs ? conditionOf(needs) : "content"];
    if (!icon) return;
    const tick = window.setInterval(() => {
      if (document.hidden || reducedRef.current) return;
      spawnBits(icon, 1);
    }, EMOTE_EVERY_MS);
    return () => window.clearInterval(tick);
  }, [needs, asleep, spawnBits]);

  /*
   * Trả lời đúng ở màn học thì con thú loé sáng ngay (§22 của tài liệu cơ chế).
   *
   * Đây là nửa NHÌN THẤY của việc nối học với thú; nửa kia là `reward_study` bên
   * máy chủ nâng tinh thần và cấp XP. Không có nửa này thì con thú vẫn lớn lên
   * nhưng không ai thấy nó lớn vì cái gì.
   *
   * Đang ngủ thì im — cùng luật với mấy mẩu cảm xúc bên dưới: không đánh thức
   * con thú bằng một hiệu ứng.
   */
  useEffect(
    () =>
      subscribeToCheer(() => {
        if (document.hidden || reducedRef.current || asleepRef.current) return;
        spawnBits("spark", 3);
      }),
    [spawnBits],
  );

  /*
   * Zzz bay lên đều đều SUỐT giấc ngủ, không chỉ một lần lúc bấm.
   *
   * Tư thế nằm và nhịp thở chậm nói "đang ngủ" cho người đang nhìn; nhưng ai vừa
   * mở bảng lên giữa giấc thì chỉ thấy một con thú đứng im hơi bẹp. Một mẩu Zzz
   * mỗi hai giây rưỡi là thứ nói ra trạng thái ấy mà không cần chữ.
   *
   * MỘT mẩu mỗi nhịp, không phải một nắm: nắm vụn là phản hồi cho một cú bấm,
   * còn đây là một trạng thái đang kéo dài — bắn cả nắm mỗi hai giây biến góc
   * này thành cái máy nháy.
   *
   * `prefers-reduced-motion` thì KHÔNG bắn gì cả. Luật chung ở `globals.css` rút
   * mọi animation về 0,01ms, nên mẩu Zzz sẽ hiện ra rồi biến mất tức khắc —
   * thành một chấm nhấp nháy hai giây một lần, tệ hơn hẳn là không có.
   */
  useEffect(() => {
    if (!asleep) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    spawnBits(BIT_ICON.sleep, 1);
    const tick = window.setInterval(() => spawnBits(BIT_ICON.sleep, 1), 2500);
    return () => window.clearInterval(tick);
  }, [asleep, spawnBits]);

  const act = (action: PetAction) => {
    setBusy(true);
    setRefused(null);
    /*
     * Hoạt ảnh chạy NGAY, không chờ máy chủ trả lời.
     *
     * Đây là ngoại lệ đúng chỗ so với luật "không tự tính, chờ máy chủ" ngay bên
     * dưới: con số thì phải chờ, vì chỉ máy chủ biết con thú đã đói bao lâu; còn
     * cái nhún và nắm vụn thì không phải một con số, và bắt chúng đợi một vòng
     * mạng biến mọi cú bấm thành trễ nhịp.
     *
     * Bị từ chối (409) thì tư thế đã trót chạy vài trăm mili giây — chấp nhận
     * được: nút đã tự mờ ở phần lớn trường hợp, nên đây là ngã rẽ hiếm.
     */
    actionFx.current = { kind: action, start: performance.now() };
    if (action === "walk") strollRef.current = true;
    else spawnBits(BIT_ICON[action]);

    void apiFetch<PetPublic>(API_ROUTES.petActions, {
      method: "POST",
      token,
      body: JSON.stringify({ action }),
    })
      .then((updated) => {
        setNeeds(updated.needs);
        setPet(updated);
      })
      .catch((err) => {
        // 409 mang LỜI GIẢI THÍCH, không phải một lỗi kỹ thuật: nói lại nguyên
        // văn thay vì dịch nó thành "thao tác không thành công".
        setRefused(err instanceof ApiError && err.status === 409 ? err.message : null);
      })
      .finally(() => setBusy(false));
  };

  return (
    /*
     * Chặn trên chiều rộng chốt theo BẢN ĐỒ (cộng cột trứng khi nó mở).
     *
     * `w-fit` lấy chiều rộng theo khối con rộng nhất, mà canvas thì có kích
     * thước cố định — nên bất kỳ khối nào rộng hơn khung nhìn cũng nới bảng ra
     * và để lại một dải trống bên phải bản đồ. Màn trứng đã làm đúng thế.
     *
     * Để khối con tự co lại là chưa đủ: đó là một quy ước mà khối MỚI nào cũng
     * phải nhớ, và quên thì hỏng im lặng. Chặn ở đây thì cái bẫy đóng lại một
     * lần cho tất cả.
     *
     * Chặn bằng LỚP đọc biến CSS chứ không bằng `style` nội tuyến, vì nó phải
     * khác nhau theo bề ngang màn hình: dưới `sm` cột trứng nằm dưới bản đồ nên
     * không được cộng vào. `style` nội tuyến thắng mọi lớp nên không làm được
     * việc đó.
     *
     * `+2px` là hai đường viền: `box-sizing` là `border-box`, nên chặn bằng
     * đúng bề rộng canvas sẽ ăn mất 2px của chính canvas và nó lòi ra ngoài.
     */
    <div
      ref={shell}
      className="shadow-overlay w-fit max-w-[calc(var(--pet-map-w)+2px)] rounded border border-rule-strong bg-panel sm:max-w-[calc(var(--pet-map-w)+var(--pet-side-w)+2px)]"
      style={
        {
          "--pet-map-w": `${size.w * TILE * ZOOM}px`,
          "--pet-map-h": `${size.h * TILE * ZOOM}px`,
          "--pet-egg-w": `${EGG_PANEL_W}px`,
          // Chỉ cộng vào chặn trên khi cột thật sự đang mở; đóng lại thì bảng
          // phải co về đúng bề ngang bản đồ chứ không giữ chỗ trống.
          "--pet-side-w": shown === null ? "0px" : `${EGG_PANEL_W}px`,
        } as React.CSSProperties
      }
    >
      {/* Cả thanh tiêu đề là tay cầm kéo — trừ hai cái nút. Kéo bằng khung ảnh
          thì không được: bấm vào khung là ra lệnh cho con thú đi, và hai ý nghĩa
          trên cùng một cú bấm thì cái nào cũng sai một nửa. */}
      <div
        onPointerDown={onDrag}
        title="Kéo để đổi chỗ"
        className="flex cursor-grab items-center justify-between gap-3 border-b border-rule px-3 py-1.5 active:cursor-grabbing"
      >
        <span className="flex items-center gap-1.5 text-small font-semibold text-ink">
          <GripHorizontal size={12} strokeWidth={2} className="text-ink-faint" aria-hidden />
          Thú cưng
          {pet && (
            <>
              <span className="font-data text-label tabular-nums text-ink-muted">
                Lv {pet.level}
              </span>
              {/* Thanh XP nhỏ, và nó BIẾN MẤT khi kịch bảng thay vì hiện đầy
                  100%: một thanh đầy ở đó đọc ra là "sắp lên level" trong khi
                  không còn level nào để lên. */}
              {pet.xp_for_next > 0 && (
                <span
                  role="progressbar"
                  aria-valuenow={pet.xp_into_level}
                  aria-valuemin={0}
                  aria-valuemax={pet.xp_for_next}
                  aria-label="Tiến độ level của thú cưng"
                  className="block h-1 w-10 overflow-hidden rounded bg-recess"
                >
                  <span
                    className="block h-full bg-action"
                    style={{
                      width: `${Math.round((pet.xp_into_level / pet.xp_for_next) * 100)}%`,
                    }}
                  />
                </span>
              )}
            </>
          )}
        </span>
        {/* Đồng hồ của thế giới, kèm mặt trời hay mặt trăng.
            Không phải giờ của người dùng, nên nó phải nói ra buổi bằng CHỮ trong
            `title`: một con số "02:15" cạnh con thú mà không giải thích gì thì
            người đọc sẽ so nó với đồng hồ trên máy mình rồi kết luận là sai. */}
        <span
          className="flex shrink-0 items-center gap-1 font-data text-label tabular-nums text-ink-faint"
          title={`Giờ ở Petland — ${PHASE_LABEL[clock.phase]} (một ngày ở đây dài một giờ thật)`}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <PixelIcon name={clock.phase === "night" ? "moon" : "sun"} scale={1} />
          {worldClockLabel(clock)}
        </span>
        <span className="flex items-center gap-1" onPointerDown={(e) => e.stopPropagation()}>
          {/* Trứng là thứ ruby MUA, nên nút của nó đứng cạnh khung nhìn chứ
              không nằm trong hàng hành động: cho ăn, chọc và đi dạo vĩnh viễn
              miễn phí, và trộn một nút mất tiền vào giữa chúng là bước đầu tiên
              của việc con thú phụ thuộc vào ruby (ADR-011 §3). */}
          {/* Lối vào thứ hai cho nhiệm vụ, và nó không phải thừa: đường chính là
              bấm vào con vật trên bản đồ, mà con vật thì nhỏ, có thể bị con thú
              che, và biến mất hoàn toàn nếu canvas không dựng được. Một cái nút
              ở thanh tiêu đề là thứ luôn tới được. */}
          {/* MỘT nút cho mỗi LOẠI, và nó mở một DANH SÁCH chứ không mở thẳng
              một thẻ. Bấm thẳng thì cái nút phải tự đoán người dùng muốn ai
              trong hai người — đoán sai là mở nhầm việc, và người ta không biết
              còn người kia. Danh sách thì hỏi, và tiện thể trả lời luôn câu hỏi
              quan trọng hơn: mỗi người còn bao lâu nữa thì đi mất.

              Luôn in dấu chấm than, không in số: hàng nút này toàn biểu tượng,
              nên một con số ở giữa đọc ra là một chỉ số chứ không phải một lời
              mời — và số lượng đã có sẵn ngay đầu danh sách. */}
          {(["npc", "intruder"] as const).map((kind) => {
            if (!meetings.some((one) => one.kind === kind)) return null;
            const showing = panel?.kind === "list" && panel.of === kind;
            return (
              <button
                key={kind}
                type="button"
                aria-label={kind === "intruder" ? "Xem kẻ xâm nhập" : "Xem nhiệm vụ"}
                title={kind === "intruder" ? "Kẻ xâm nhập" : "Có người cần giúp"}
                aria-expanded={showing}
                onClick={() => setPanel(showing ? null : { kind: "list", of: kind })}
                className={cx(
                  "grid h-6 w-6 place-items-center rounded font-data text-small font-bold transition-colors hover:bg-recess",
                  kind === "intruder" ? "text-alert" : "text-warn",
                  showing && "bg-recess",
                )}
              >
                !
              </button>
            );
          })}
          {/* Công cụ THỬ, chỉ admin thấy.
              Đường thật cố ý chậm — hai mươi phút cho một NPC, một giờ cho một
              kẻ xâm nhập, và lần đọc đầu của một tài khoản mới chỉ đặt mốc chứ
              không sinh ai. Không có nút này thì mỗi lần sửa một dòng trong hoạt
              cảnh chiến đấu là hai mươi phút ngồi đợi.

              Nó nằm ở ĐÂY chứ không ở `/admin/pet`, vì thứ nó tạo ra chỉ nhìn
              thấy được trên bản đồ này. Một nút ở trang khác nghĩa là mở tab thứ
              hai, bấm, rồi quay lại — mỗi vòng thử. */}
          {isAdmin && (
            <button
              type="button"
              aria-label="Gọi đủ NPC và kẻ xâm nhập (thử)"
              title="Gọi đủ khách — công cụ thử"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                void apiFetch(API_ROUTES.adminPetEncounterSpawn, { method: "POST", token })
                  .then(() => refreshMeetings.current())
                  .catch(() => {})
                  .finally(() => setBusy(false));
              }}
              className="grid h-6 w-6 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink disabled:opacity-45"
            >
              <PixelIcon name="spark" scale={1} />
            </button>
          )}
          <button
            type="button"
            aria-label={panel?.kind === "eggs" ? "Đóng màn trứng" : "Mở trứng"}
            title="Trứng"
            aria-expanded={panel?.kind === "eggs"}
            onClick={() => setPanel(panel?.kind === "eggs" ? null : { kind: "eggs" })}
            className={cx(
              "grid h-6 w-6 place-items-center rounded transition-colors hover:bg-recess hover:text-ink",
              panel?.kind === "eggs" ? "text-alert" : "text-ink-faint",
            )}
          >
            <Gem size={13} strokeWidth={2} aria-hidden />
          </button>
          <button
            type="button"
            aria-label={panel?.kind === "collection" ? "Đóng bộ sưu tập" : "Bộ sưu tập"}
            title="Bộ sưu tập"
            aria-expanded={panel?.kind === "collection"}
            onClick={() => setPanel(panel?.kind === "collection" ? null : { kind: "collection" })}
            className={cx(
              "grid h-6 w-6 place-items-center rounded transition-colors hover:bg-recess hover:text-ink",
              panel?.kind === "collection" ? "text-action" : "text-ink-faint",
            )}
          >
            <LayoutGrid size={13} strokeWidth={2} aria-hidden />
          </button>
          <button
            type="button"
            aria-label={full ? "Thu nhỏ khung nhìn" : "Xem toàn bản đồ"}
            title={full ? "Thu nhỏ" : "Toàn bản đồ"}
            onClick={() => {
              const next = full ? { w: VIEW_W, h: VIEW_H } : { w: FULL_W, h: FULL_H };
              setFull(!full);
              setSize(next);
              stageRef.current?.setView(next.w, next.h);
            }}
            className="grid h-6 w-6 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink"
          >
            {full ? (
              <Minimize2 size={13} strokeWidth={2} aria-hidden />
            ) : (
              <Maximize2 size={13} strokeWidth={2} aria-hidden />
            )}
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng góc thú cưng"
            className="grid h-6 w-6 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink"
          >
            <X size={14} strokeWidth={2} aria-hidden />
          </button>
        </span>
      </div>
      {/* Bản đồ và cột trứng nằm CẠNH nhau. Xếp dọc thì cột trứng đẩy chiều cao
          cả bảng, mà bảng nổi cố định nên phần lòi ra khỏi màn hình không cuộn
          theo trang được — hàng nút chăm thú cưng biến mất khỏi tầm với. Dưới
          `sm` thì xếp dọc trở lại, vì 448 + 288 rộng hơn màn hình điện thoại. */}
      <div className="flex max-sm:flex-col">
        {/* Khung bọc để những mẩu bay lên neo được theo pixel trong canvas.
            `overflow-hidden` để mẩu bay cao quá không tràn ra ngoài viền bảng —
            nó phải bay lên trong khung cảnh, không bay lên trên thanh tiêu đề.

            Mẩu là phần tử DOM ANH EM với canvas, không phải con của nó: Pixi tự
            gắn canvas vào `host` ngoài tầm biết của React, nên trộn con của
            React vào cùng một node là chỗ React và Pixi tranh nhau danh sách
            con. */}
        <div
          className="relative shrink-0 overflow-hidden"
          style={{ width: size.w * TILE * ZOOM, height: size.h * TILE * ZOOM }}
        >
          <div
            ref={host}
            tabIndex={0}
            role="application"
            aria-label="Bản đồ Petland. Bấm W A S D hoặc phím mũi tên để dắt thú cưng đi."
            // Bàn phím chỉ lái khi khung này đang được focus, mà "hãy bấm vào
            // bản đồ trước" thì không có chỗ nào trên màn hình nói ra được —
            // panel không còn một dòng trống nào. Tooltip là chỗ rẻ nhất còn lại.
            title="Bấm vào bản đồ rồi dùng W A S D (hoặc phím mũi tên) để dắt thú cưng đi"
            className={cx(
              "bg-recess",
              // Viền focus THẤY ĐƯỢC, vì bàn phím chỉ lái khi khung này đang
              // được focus: không có viền thì người dùng bấm phím, không có gì
              // xảy ra, và không có gì trên màn hình nói vì sao.
              "outline-none focus-visible:ring-2 focus-visible:ring-accent",
              // Chừa đúng chỗ cho canvas trước khi Pixi dựng xong, nếu không cả
              // góc màn hình nhảy một cái khi ảnh về.
              "block h-full w-full",
            )}
          />
          <PixelBits bits={bits} />
          {/* Bong bóng thoại: phần tử DOM, không vẽ trên canvas.

              Canvas cố ý không nạp phông chữ nào — cùng lý do dấu chấm than là
              hai hình chữ nhật — và chữ vẽ trên canvas thì trình đọc màn hình
              không đọc được. `-translate-x-1/2` để nó cân giữa trên đầu khách,
              còn vị trí thì vòng lặp ghi thẳng vào `style` mỗi khung. */}
          <div
            ref={bubble}
            aria-live="polite"
            className="pointer-events-none absolute z-10 max-w-[13rem] rounded border border-rule-strong bg-panel px-2 py-1 text-label leading-snug text-ink opacity-0 transition-opacity duration-200"
            style={{ left: -9999, top: -9999 }}
          >
            {speech}
          </div>
        </div>
        {shown?.kind === "list" && (
          <GuestList
            meetings={meetings}
            kind={shown.of}
            activeId={activeId}
            onPick={(id) => openQuestRef.current(id)}
            onClose={() => setPanel(null)}
          />
        )}
        {shown?.kind === "quest" && active && (
          <QuestCard
            /* Cuộc khác là thẻ khác: `key` làm nó dựng lại từ đầu, nên câu đã
               gõ dở của cuộc trước không nằm lại trong ô nhập của cuộc sau —
               và giờ chuyển qua lại giữa bốn vị khách là chuyện thường. */
            key={active.id}
            token={token}
            encounter={active}
            autoFocusInput={!quietOpen}
            onChange={(next) =>
              setMeetings((current) =>
                next === null
                  ? current.filter((one) => one.id !== active.id)
                  : current.map((one) => (one.id === active.id ? next : one)),
              )
            }
            onFight={(win) => {
              // `started: null` nghĩa là "chưa đánh, còn đang tới". Vòng lặp mới
              // là chỗ biết con thú đứng đâu, nên nó chốt mốc bắt đầu — đánh từ
              // nửa bản đồ bên kia thì cú lao tới chỉ là một cái nhích.
              fightRef.current = { id: active.id, started: null, win };
            }}
            onClose={() => setPanel(null)}
          />
        )}
        {shown?.kind === "eggs" && <EggScreen token={token} onClose={() => setPanel(null)} />}
        {shown?.kind === "collection" && (
          <CollectionScreen
            token={token}
            active={pet?.species ?? null}
            /*
             * Đổi con thì con trên bản đồ phải đổi hình NGAY, không đợi lần đọc
             * sau. `speciesRef` là đường duy nhất chạm tới được vòng vẽ: vòng đó
             * có danh sách phụ thuộc riêng và không dựng lại khi state đổi, nên
             * một closure giữ mãi ô của con cũ — đúng cái bẫy đã ghi cho
             * `mascot` ở bản trước.
             */
            onSwitched={(updated) => {
              setPet(updated);
              // Nhu cầu phải đổi theo, và đây chính là chỗ đã sót: thanh chỉ số
              // đọc từ `needs`, nên không đặt lại thì HUD in nhu cầu của con
              // VỪA CẤT trong khi trên bản đồ là con mới — hai con số cùng nói
              // về một con thú mà không khớp nhau, và không có gì báo.
              setNeeds(updated.needs);
              speciesRef.current = updated.tile;
              placeRef.current = {
                x: updated.tile_x,
                y: updated.tile_y,
                facing: updated.facing === "left" ? "left" : "right",
              };
              // Bỏ dở tư thế đang diễn: con vừa cất đi mới là con đang nhai.
              actionFx.current = null;
            }}
            onClose={() => setPanel(null)}
          />
        )}
      </div>
      {needs && (
        <div className="border-t border-rule">
          <PetHud
            needs={needs}
            condition={conditionOf(needs)}
            busy={busy}
            asleep={asleep}
            onAction={act}
            leading={<PetlandMusicToggle />}
          />
          {refused && <p className="px-3 pb-2 text-small text-warn">{refused}</p>}
          {/* Chạm trần phải NÓI RA. Không nói thì người dùng cho ăn tiếp và
              tưởng hệ thống hỏng khi con số đứng yên — cùng lý do khối việc
              hôm nay in câu tương tự. */}
          {pet && pet.xp_today >= pet.daily_cap && (
            <p className="px-3 pb-2 text-small text-ink-muted">
              Hôm nay thú cưng đã nhận đủ {pet.daily_cap} XP. Chăm tiếp vẫn có tác dụng, chỉ có điểm
              là dừng tới ngày mai.
            </p>
          )}
        </div>
      )}
      {error && <p className="px-3 py-2 text-small text-ink-muted">Chưa mở được góc thú cưng.</p>}
    </div>
  );
}
