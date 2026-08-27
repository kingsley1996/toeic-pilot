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
import { PetHud, PixelBits, type Bit } from "@/components/petland-ui";
import { PixelIcon } from "@/components/pixel-icon";
import { STEP_SECONDS, type PetAction, type PetNeeds } from "@/components/petland-pet";
import { CREATURE_COLS, CREATURE_ROWS, tileForSpecies } from "@/components/petland-sprite";
import { cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import {
  findPath,
  nearestWalkable,
  neighbourOf,
  parseMap,
  spotNear,
  strollTarget,
  TILE,
  type MapData,
  type Tile,
} from "@/components/petland-map";
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

/** Bong bóng thoại đứng bao lâu. Đủ đọc một câu, rồi nhường lại khung cảnh. */
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
    const next = clamp(
      place.current ??
        readPlace() ??
        defaultPlace(panel, screen, window.innerWidth >= 1024 ? 240 : 0),
      panel,
      screen,
    );
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
      {open ? (
        <PetPanel token={token} onDrag={onDragStart} onClose={() => setOpen(false)} />
      ) : (
        <PetLauncher onOpen={() => setOpen(true)} onDrag={onDragStart} />
      )}
    </div>
  );
}

/**
 * Nút thu gọn. Vẽ con thú bằng CSS chứ không bằng Pixi — mở một context WebGL
 * chỉ để hiện một ô 16px là trả giá đúng thứ nhánh `open` sinh ra để tránh.
 */
function PetLauncher({
  onOpen,
  onDrag,
}: {
  onOpen: () => void;
  onDrag: (event: React.PointerEvent) => void;
}) {
  return (
    <span className="inline-flex items-stretch">
      {/* Tay cầm kéo tách khỏi nút mở: nếu cả cái nút vừa kéo được vừa bấm được
          thì một cú kéo nhẹ vẫn kết thúc bằng `click` và bảng bật mở ngoài ý
          muốn — người dùng đọc ra là nút tự nhảy. */}
      <span
        onPointerDown={onDrag}
        role="presentation"
        title="Kéo để đổi chỗ"
        className="grid w-6 cursor-grab place-items-center rounded-l border border-r-0 border-rule-strong bg-panel text-ink-faint active:cursor-grabbing"
      >
        <GripHorizontal size={12} strokeWidth={2} aria-hidden />
      </span>
      <button
        type="button"
        onClick={onOpen}
        className="inline-flex items-center gap-2 rounded-r border border-rule-strong bg-panel py-1.5 pl-1.5 pr-3 text-small font-semibold text-ink transition-colors hover:bg-recess"
      >
        <span
          aria-hidden
          className="block h-8 w-8 shrink-0"
          style={{
            backgroundImage: "url(/pet/creatures.png)",
            // Số cột lấy từ `petland-sprite`, không từ `SHEET_COLS.town`: đó là
            // số cột của tấm NỀN (12), còn tấm sinh vật có 10 — nên nút này vốn
            // đang cắt ra một mảnh của con khác, đủ giống một con thú để không
            // ai nhận ra là sai.
            backgroundPosition: `-${(tileForSpecies("cat") % CREATURE_COLS) * TILE * 2}px -${Math.floor(tileForSpecies("cat") / CREATURE_COLS) * TILE * 2}px`,
            backgroundSize: `${CREATURE_COLS * TILE * 2}px ${CREATURE_ROWS * TILE * 2}px`,
            imageRendering: "pixelated",
          }}
        />
        Thú cưng
      </button>
    </span>
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
  const [error, setError] = useState(false);
  const [full, setFull] = useState(false);
  /*
   * Nhu cầu là STATE (thanh chỉ số phải vẽ lại), còn vị trí con thú là ref
   * (vòng lặp ghi 60 lần/giây). Hai thứ đổi ở hai nhịp khác hẳn nhau nên không
   * dùng chung một cơ chế: cho nhu cầu vào ref thì thanh không nhích, cho vị trí
   * vào state thì cả bảng dựng lại mỗi khung hình.
   */
  const [needs, setNeeds] = useState<PetNeeds | null>(null);
  const [pet, setPet] = useState<PetPublic | null>(null);
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
  const openQuestRef = useRef<(id: string) => void>(() => {});
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
    let tile: Tile = { x: 0, y: 0 };
    let from: Tile = tile;
    let progress = 0;
    let facing: "left" | "right" = "right";
    let queue: Tile[] = [];
    let last = performance.now();
    let saved: Tile = tile;

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
          const spot = neighbourOf(map, { x: guest.x, y: guest.y }, tile);
          if (spot) queue = findPath(map, tile, spot);
        }
        return;
      }
      if (asleepRef.current) return;
      queue = findPath(map, tile, target);
    };

    void Promise.all([
      fetch("/pet/map.json").then((res) => res.json()),
      apiFetch<PetPublic>(API_ROUTES.pet, { token }),
      import("@/components/petland-render"),
    ])
      .then(async ([rawMap, pet, render]) => {
        const parsed = parseMap(rawMap);
        if (!parsed || !alive) return;
        map = parsed;
        mapRef.current = parsed;
        setMapReady(true);
        // Ô đã lưu có thể trỏ vào tường sau khi bản đồ được vẽ lại trong trình
        // sửa. Kéo con thú ra chỗ đứng được thay vì để nó kẹt trong hàng rào.
        tile = nearestWalkable(parsed, { x: pet.tile_x, y: pet.tile_y });
        // Chỗ chọn chỗ đứng cho khách đo khoảng cách tới con thú, nên nó cần ô
        // này — và nó sống ngoài effect này.
        petTileRef.current = tile;
        from = tile;
        saved = tile;
        facing = pet.facing === "left" ? "left" : "right";
        setNeeds(pet.needs);
        setPet(pet);
        /*
         * Ô lấy TỪ MÁY CHỦ, không tra ở đây.
         *
         * Bảng loài là dữ liệu admin sửa được (`pet_species`), nên một bảng tra
         * thứ hai phía frontend sẽ trôi khỏi nó vào đúng ngày ai đó đổi ô của
         * một loài — và hậu quả là con thú vẽ nhầm hình, không phải một lỗi.
         * `tileForSpecies` chỉ còn là phương án rơi về cho nút thu gọn, vốn vẽ
         * trước khi có lượt gọi nào.
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

        const loop = (now: number) => {
          const dt = Math.min(0.1, (now - last) / 1000);
          last = now;

          // Đổi con: đặt lại chỗ đứng TRƯỚC khi xử lý bước đi, nếu không con
          // mới sẽ đi nốt quãng đường mà con cũ đang đi dở.
          const jump = placeRef.current;
          if (jump && map) {
            placeRef.current = null;
            queue = [];
            progress = 0;
            // Ô đã lưu có thể trỏ vào tường sau khi bản đồ được vẽ lại trong
            // trình sửa — cùng lý do lần nạp đầu cũng gọi `nearestWalkable`.
            tile = nearestWalkable(map, { x: jump.x, y: jump.y });
            petTileRef.current = tile;
            from = tile;
            saved = tile;
            facing = jump.facing;
          }

          // "Đi dạo" đặt cờ; chỗ BIẾT bản đồ mới dựng được đường đi. Bấm lúc
          // đang đi thì bỏ qua — một tuyến mới đè lên tuyến cũ làm con thú quay
          // ngoắt giữa đường, đọc ra là giật chứ không phải đổi ý.
          // Đang ngủ thì không nhận đường đi mới, và bỏ luôn đường đang đi dở:
          // một con thú vừa ngủ vừa băng qua bản đồ đọc ra là hỏng.
          if (asleepRef.current) {
            strollRef.current = false;
            queue = [];
            progress = 0;
          }

          if (strollRef.current) {
            strollRef.current = false;
            if (map && queue.length === 0) {
              const target = strollTarget(map, tile, STROLL_MIN_TILES, Math.random);
              if (target) queue = findPath(map, tile, target);
            }
          }

          if (queue.length > 0) {
            progress += dt / STEP_SECONDS;
            while (progress >= 1 && queue.length > 0) {
              progress -= 1;
              from = tile;
              const next = queue.shift() as Tile;
              facing = next.x < tile.x ? "left" : next.x > tile.x ? "right" : facing;
              tile = next;
              petTileRef.current = next;
            }
            if (queue.length === 0) {
              progress = 0;
              save(tile, facing);
            }
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
            const near = foe !== null && Math.abs(foe.x - tile.x) + Math.abs(foe.y - tile.y) <= 1;
            if (foe === null || asleepRef.current || (near && queue.length === 0)) {
              brawl.started = now;
            } else if (queue.length === 0 && map) {
              const spot = neighbourOf(map, { x: foe.x, y: foe.y }, tile);
              queue = spot ? findPath(map, tile, spot) : [];
              if (queue.length === 0) brawl.started = now;
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
            tile,
            from,
            progress: queue.length ? progress : 0,
            facing,
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
        raf = requestAnimationFrame(loop);
      })
      .catch(() => alive && setError(true));

    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      el.removeEventListener("click", onClick);
      // `destroy` gỡ cả canvas lẫn texture khỏi GPU. Không gọi thì mỗi lần mở
      // lại bảng là một context WebGL nữa, và trình duyệt chỉ cho vài cái.
      stageRef.current = null;
      stage?.destroy();
    };
  }, [token]);

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

  const asleep = pet?.sleep_until != null && new Date(pet.sleep_until).getTime() > clock.at;
  // Ghi ref trong EFFECT, không trong lúc dựng: `react-hooks` chặn thẳng việc
  // chạm ref lúc render, và luật đó đúng — một lượt dựng bị bỏ đi vẫn kịp để
  // lại dấu vết trong ref. Trễ một khung hình ở đây không ai thấy.
  useEffect(() => {
    asleepRef.current = asleep;
  }, [asleep]);

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
    return () => {
      alive = false;
      window.clearInterval(tick);
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
    openQuestRef.current = (id: string) => {
      const guest = meetings.find((one) => one.id === id);
      if (!guest) return;
      setActiveId(id);
      setPanel({ kind: "quest" });
      setSpeech(speechFor(guest.id, guest.kind === "intruder", guest.steps_done));
      speakingRef.current = id;
      // Bong bóng tự tắt; thẻ nhiệm vụ ở bên cạnh mới là chỗ làm việc. Để nó
      // đứng mãi thì nó che mất chính con vật vừa nói.
      speechUntil.current = performance.now() + SPEECH_MS;
    };
  }, [meetings]);

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
  const spawnBits = useCallback((action: PetAction, count = 4) => {
    const stage = stageRef.current;
    if (!stage) return;
    const at = stage.petScreen();
    const icon = BIT_ICON[action];
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
    spawnBits("sleep", 1);
    const tick = window.setInterval(() => spawnBits("sleep", 1), 2500);
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
    else spawnBits(action);

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
            className={cx(
              "bg-recess",
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
          <PetHud needs={needs} busy={busy} asleep={asleep} onAction={act} />
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
