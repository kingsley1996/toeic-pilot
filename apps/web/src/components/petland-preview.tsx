"use client";

import { API_ROUTES } from "@toeic-pilot/shared";
import { useEffect, useRef, useState } from "react";

import { parseMap, SHEET_COLS, TILE, type MapData } from "@/components/petland-map";

/**
 * Petland trên trang giới thiệu: bản đồ thật và vài con thú, cả hai vẽ ra từ
 * đúng nguồn mà trò chơi dùng.
 *
 * Nó KHÔNG nhập gì từ lớp trò chơi. Trang giới thiệu tải trước khi có ai đăng
 * nhập, nên kéo theo `petland-render` (và qua đó là Pixi) hay cảnh chơi là trả
 * giá bundle cho thứ hầu hết khách chưa dùng tới. Cái giá là hình học tấm ghép
 * chép lại ở dưới — hai bảng nhỏ, và cả hai chỉ đổi khi bộ art đổi.
 */

/* Hình học của `public/pet/creatures.png`, chép từ `petland-sprite.ts`: 160×288
   pixel, ô 16px, 10 cột. Đây là bản sao thứ hai và nó chỉ an toàn vì tấm ghép là
   một tệp tĩnh — đổi tấm ghép thì phải sửa cả hai chỗ. */
const SHEET_W = 160;
const SHEET_H = 288;
const CELL = 16;
const COLS = 10;

/*
 * Sáu con, mỗi bậc một con, chép chỉ số ô từ `DEFAULT_PET_SPECIES` bên API.
 *
 * Viết cứng ở đây là cố ý: không có endpoint công khai nào liệt kê loài (cả họ
 * `/pet/*` đều cần đăng nhập), và đây là một lựa chọn MINH HOẠ chứ không phải
 * một con số thống kê — trang này chỉ cấm đoán số liệu, không cấm chọn ảnh.
 *
 * Màu bậc lấy theo `TIER_TONE` ở `petland-creature.tsx`.
 */
const SHOWCASE = [
  { tile: 150, name: "Vịt", tier: "Thường", tone: "text-ink-muted" },
  { tile: 169, name: "Mèo", tier: "Ít gặp", tone: "text-ok" },
  { tile: 117, name: "Cú", tier: "Hiếm", tone: "text-action-ink" },
  { tile: 157, name: "Hổ", tier: "Sử thi", tone: "text-alert" },
  { tile: 33, name: "Rồng lửa", tier: "Huyền thoại", tone: "text-warn" },
  { tile: 48, name: "Thần Bão", tier: "Thần", tone: "text-myth" },
];

export function Creature({ tile, size }: { tile: number; size: number }) {
  const scale = size / CELL;
  return (
    <span
      aria-hidden
      className="block [image-rendering:pixelated]"
      style={{
        width: size,
        height: size,
        backgroundImage: "url(/pet/creatures.png)",
        backgroundSize: `${SHEET_W * scale}px ${SHEET_H * scale}px`,
        backgroundPosition: `-${(tile % COLS) * size}px -${Math.floor(tile / COLS) * size}px`,
      }}
    />
  );
}

/* `className` thay hẳn khung ngoài, không cộng thêm: trang giới thiệu đứng ngoài
   design system và bọc ảnh bằng khung bo 28px có bóng đổ của riêng nó. */
/*
 * Bản đồ THẬT, vẽ từ đúng nguồn mà trò chơi đọc.
 *
 * Trước đây chỗ này là `landscape/petland-1.jpg` — một bức tranh minh hoạ đẹp
 * nhưng KHÔNG phải Petland. Trang giới thiệu khoe một cảnh mà người dùng sẽ
 * không bao giờ thấy là nói sai về sản phẩm.
 *
 * Thứ tự nguồn giống hệt trò chơi (xem `.claude/rules/frontend.md`): hỏi máy chủ
 * trước, vì `petland_map` là bản GHI ĐÈ do admin sửa trên web; **204 nghĩa là
 * "chưa ai sửa"**, không phải lỗi, và lúc đó `public/pet/map.json` đã commit mới
 * là bản đang chạy. Lấy sai thứ tự thì trang này vẽ một bản đồ cũ.
 */

/* Hình học tấm nền và luật đọc bản đồ lấy THẲNG từ `petland-map.ts`, không chép
   lại. Chú thích cũ ở đầu tệp lo rằng nhập từ lớp trò chơi sẽ kéo Pixi theo —
   nhưng `petland-map` bị `check-petland-layers.mjs` CẤM nhập `pixi.js`, nên nó
   là số học thuần và nhập được. Bản chép tay trước đây là một nguồn sự thật thứ
   hai không cần thiết. */

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

/**
 * Vẽ bản đồ thật vào canvas MỘT LẦN, rồi thôi.
 *
 * Là hook để cảnh Remotion dùng lại được, và nó tự GIỮ ref chứ không nhận vào:
 * effect ghi `el.width`/`el.height`, mà ghi xuyên qua tham số của hook là thứ
 * bộ biên dịch React từ chối thẳng.
 *
 * Nó phải vẽ một lần chứ không vẽ theo
 * khung hình: bản đồ 18×13 với hai lớp là hơn bốn trăm lượt `drawImage`, và làm
 * việc đó ba mươi lần mỗi giây cho một hình KHÔNG đổi là cách chắc chắn nhất để
 * một trang giới thiệu làm nóng máy người xem. Thứ động duy nhất là con thú, và
 * nó là một phần tử DOM dịch chuyển bằng `transform`.
 */
export function usePetlandMapCanvas() {
  const canvas = useRef<HTMLCanvasElement>(null);
  /* Bản đồ đã đọc, để cảnh động hỏi ô nào đi được. State chứ không ref: đường
     đi lang thang được dựng bằng `useMemo` từ nó, mà `useMemo` cần một lần
     render mới sau khi bản đồ về. Đặt state ở đây không đụng luật
     `react-hooks/set-state-in-effect` vì nó nằm sau `await`, không phải trong
     thân effect. */
  const [map, setMap] = useState<MapData | null>(null);

  useEffect(() => {
    // Effect này chỉ VẼ, không đặt state — không đụng tới luật
    // `react-hooks/set-state-in-effect`.
    let alive = true;

    void (async () => {
      const live = await fetch(API_ROUTES.petlandMap).catch(() => null);
      const raw =
        live && live.status === 200
          ? await live.json().catch(() => null)
          : await fetch("/pet/map.json")
              .then((r) => r.json())
              .catch(() => null);
      const parsed = parseMap(raw);
      if (!alive || parsed === null) return;
      setMap(parsed);

      const map = parsed;
      const sheets = Object.fromEntries(
        await Promise.all(
          Object.keys(SHEET_COLS).map(async (id) => [id, await loadImage(`/pet/${id}.png`)]),
        ),
      ) as Record<string, HTMLImageElement>;
      if (!alive) return;

      const el = canvas.current;
      if (el === null) return;
      el.width = map.w * TILE;
      el.height = map.h * TILE;
      const ctx = el.getContext("2d");
      if (ctx === null) return;
      ctx.imageSmoothingEnabled = false;

      for (const layer of [map.ground, map.objects]) {
        layer.forEach((cell, i) => {
          if (cell === null) return;
          const cols = SHEET_COLS[cell.sheet];
          const sheet = sheets[cell.sheet];
          if (cols === undefined || sheet === undefined) return;
          ctx.drawImage(
            sheet,
            (cell.index % cols) * TILE,
            Math.floor(cell.index / cols) * TILE,
            TILE,
            TILE,
            (i % map.w) * TILE,
            Math.floor(i / map.w) * TILE,
            TILE,
            TILE,
          );
        });
      }
    })();

    return () => {
      alive = false;
    };
  }, []);

  return { canvas, map };
}

export function PetlandMap({ className }: { className?: string }) {
  const { canvas } = usePetlandMapCanvas();

  return (
    <div className={className}>
      <canvas
        ref={canvas}
        className="block w-full [image-rendering:pixelated]"
        role="img"
        aria-label="Bản đồ Petland: khu nhà, bãi cỏ và con suối mà con thú đi lại trên đó"
      />
    </div>
  );
}

/** Một con duy nhất, vẽ theo tên loài trong `SHOWCASE`. */
export function PetlandCreature({ name, size = 64 }: { name: string; size?: number }) {
  const found = SHOWCASE.find((c) => c.name === name);
  if (!found) return null;
  return <Creature tile={found.tile} size={size} />;
}

export function PetlandSpecies() {
  return (
    <ul className="grid grid-cols-3 gap-x-4 gap-y-7 sm:grid-cols-6">
      {SHOWCASE.map((c) => (
        <li key={c.name} className="flex flex-col items-center gap-2 text-center">
          <Creature tile={c.tile} size={64} />
          <span className="text-small font-semibold leading-none">{c.name}</span>
          <span className={`font-data text-label uppercase tracking-wider ${c.tone}`}>
            {c.tier}
          </span>
        </li>
      ))}
    </ul>
  );
}
