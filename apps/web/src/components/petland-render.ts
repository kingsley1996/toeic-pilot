/**
 * Vẽ góc thú cưng bằng Pixi. **Đây là tệp DUY NHẤT được `import "pixi.js"`.**
 *
 * `scripts/check-petland-layers.mjs` giữ luật đó, và nó không phải chuyện gọn
 * gàng: không có ranh giới ấy thì sáu tháng nữa "đổi renderer" là một cuộc tìm
 * kiếm toàn dự án, và mỗi tệp lặng lẽ dính vào Pixi là một tệp phải đọc lại.
 *
 * Tệp này không giữ trạng thái trò chơi. Nó nhận một bản mô tả "vẽ cái gì ở đâu"
 * (`PetView`) và vẽ đúng thế. Vị trí, nhu cầu, tìm đường đều nằm ở
 * `petland-map.ts` và `petland-pet.ts`, nơi kiểm được mà không cần trình duyệt.
 */
import { Application, Assets, Container, Rectangle, Sprite, Texture, TextureSource } from "pixi.js";

import { SHEET_COLS, TILE, type MapData, type SheetId } from "@/components/petland-map";

const SHEET_URL: Record<SheetId, string> = {
  town: "/pet/town.png",
  farm: "/pet/farm.png",
  water: "/pet/water.png",
  stone: "/pet/stone.png",
};
const CREATURES_URL = "/pet/creatures.png";

/** Số cột của tấm sinh vật. Số cột của các tấm nền nằm ở `SHEET_COLS`. */
const CREATURE_COLS = 10;

export type PetView = {
  /** Ô đang đứng, và ô đang rời khỏi khi đang đi. */
  tile: { x: number; y: number };
  from: { x: number; y: number };
  /** 0..1 giữa `from` và `tile`. Bằng 0 khi đứng yên. */
  progress: number;
  facing: "left" | "right";
  /** Chỉ số ô trong `creatures.png`. */
  species: number;
  /** Đồng hồ giây, để sinh nhịp thở. */
  clock: number;
};

export type StageOptions = {
  zoom?: number;
  /** Khung nhìn tính bằng Ô. Nhỏ hơn bản đồ thì camera bám con thú. */
  viewW?: number;
  viewH?: number;
};

export type Stage = {
  draw: (view: PetView) => void;
  /**
   * Đổi khung nhìn tính bằng Ô — dùng cho nút xem toàn bản đồ.
   *
   * Đổi tại chỗ chứ không dựng lại sân khấu: mỗi lần `createStage` là một WebGL
   * context mới, và trình duyệt chỉ cho vài cái trước khi từ chối. Bật/tắt toàn
   * bản đồ dăm lần là chạm trần, và lỗi hiện ra rất xa nguyên nhân.
   */
  setView: (cols: number, rows: number) => void;
  /** Toạ độ con trỏ trong canvas → ô bản đồ, hoặc null nếu ra ngoài. */
  tileAt: (clientX: number, clientY: number) => { x: number; y: number } | null;
  destroy: () => void;
};

function slice(sheet: Texture, index: number, cols: number): Texture {
  const x = (index % cols) * TILE;
  const y = Math.floor(index / cols) * TILE;
  return new Texture({ source: sheet.source, frame: new Rectangle(x, y, TILE, TILE) });
}

/**
 * Dựng sân khấu. `zoom` phải là số nguyên — phóng 1,7× làm mỗi pixel nguồn phủ
 * 1,7 pixel màn hình, và hàng nào rơi vào ranh giới thì dày mỏng khác nhau: ảnh
 * trông "bẩn" theo kiểu không chỉ ra được nguyên nhân.
 */
export async function createStage(
  host: HTMLElement,
  map: MapData,
  { zoom = 2, viewW = map.w, viewH = map.h }: StageOptions = {},
): Promise<Stage> {
  let cols = Math.min(viewW, map.w);
  let rows = Math.min(viewH, map.h);
  /*
   * `nearest` PHẢI đặt trước khi nạp texture đầu tiên.
   *
   * Mặc định của Pixi là `linear`, thứ nội suy giữa các pixel — đúng cho ảnh
   * chụp và sai hoàn toàn cho pixel art: viền một ô cỏ sẽ nhoè sang ô bên cạnh.
   * Đặt sau khi nạp thì texture đầu tiên đã mang chế độ cũ, và nó là tấm nền —
   * tức đúng thứ chiếm nhiều diện tích nhất.
   */
  TextureSource.defaultOptions.scaleMode = "nearest";

  const app = new Application();
  await app.init({
    width: cols * TILE * zoom,
    height: rows * TILE * zoom,
    backgroundAlpha: 0,
    antialias: false,
    // Sprite luôn nằm trên toạ độ nguyên: nửa pixel làm ảnh rung khi camera đi.
    roundPixels: true,
  });
  host.appendChild(app.canvas);

  const [town, farm, water, stone, creatures] = await Promise.all([
    Assets.load<Texture>(SHEET_URL.town),
    Assets.load<Texture>(SHEET_URL.farm),
    Assets.load<Texture>(SHEET_URL.water),
    Assets.load<Texture>(SHEET_URL.stone),
    Assets.load<Texture>(CREATURES_URL),
  ]);
  const sheets: Record<SheetId, Texture> = { town, farm, water, stone };

  const world = new Container();
  world.scale.set(zoom);
  app.stage.addChild(world);

  // Nền và vật thể vẽ MỘT LẦN. Chúng không đổi giữa các khung hình, nên dựng lại
  // mỗi khung là trả tiền 600 lần mỗi giây cho một bức ảnh đứng yên.
  for (const layer of [map.ground, map.objects]) {
    for (let i = 0; i < layer.length; i += 1) {
      const cell = layer[i];
      if (cell === null) continue;
      const sprite = new Sprite(slice(sheets[cell.sheet], cell.index, SHEET_COLS[cell.sheet]));
      sprite.x = (i % map.w) * TILE;
      sprite.y = Math.floor(i / map.w) * TILE;
      world.addChild(sprite);
    }
  }

  const pet = new Sprite();
  // Neo ở ĐÁY và giữa: con thú "đứng trên" ô của nó, nên khi nhún hay thở thì
  // chân ở yên còn người nhấp nhô. Neo ở tâm làm nó lún xuống đất mỗi nhịp thở.
  pet.anchor.set(0.5, 1);
  world.addChild(pet);

  let currentSpecies = -1;
  let camX = 0;
  let camY = 0;

  return {
    setView(nextCols, nextRows) {
      cols = Math.max(1, Math.min(Math.round(nextCols), map.w));
      rows = Math.max(1, Math.min(Math.round(nextRows), map.h));
      app.renderer.resize(cols * TILE * zoom, rows * TILE * zoom);
      // Kẹp lại ngay: mở rộng khung nhìn khi camera đang ở sát mép phải sẽ để lộ
      // một dải trống bên ngoài bản đồ cho tới khung hình sau.
      camX = Math.max(0, Math.min(map.w - cols, camX));
      camY = Math.max(0, Math.min(map.h - rows, camY));
      world.x = -Math.round(camX * TILE) * zoom;
      world.y = -Math.round(camY * TILE) * zoom;
    },

    draw(view) {
      if (view.species !== currentSpecies) {
        pet.texture = slice(creatures, view.species, CREATURE_COLS);
        currentSpecies = view.species;
      }

      // Nội suy giữa hai ô: đây là chỗ "mượt" đến từ, chứ không phải từ việc bỏ
      // lưới. Con thú LUÔN ở một ô về mặt logic.
      const t = view.progress;
      const x = view.from.x + (view.tile.x - view.from.x) * t;
      const y = view.from.y + (view.tile.y - view.from.y) * t;
      pet.x = x * TILE + TILE / 2;

      /*
       * Hai chuyển động, cả hai sinh lúc vẽ chứ không có khung ảnh nào (§14.5).
       *
       * Thở: nhấp nhô ±4% chiều cao, chu kỳ ~1,6 giây.
       * Nhún khi đi: một nhịp lên xuống trọn vẹn cho mỗi ô đi qua, nên bước chân
       * khớp với ô — nhún theo đồng hồ thay vì theo tiến độ sẽ trôi khỏi lưới và
       * đọc ra là trượt.
       */
      const breathe = 1 + Math.sin(view.clock * 3.9) * 0.04;
      const hop = t > 0 ? Math.abs(Math.sin(t * Math.PI)) : 0;
      pet.y = (y + 1) * TILE - hop * 2;
      pet.scale.set(view.facing === "left" ? -1 : 1, breathe);

      /*
       * Camera bám theo Ô, có VÙNG CHẾT ở giữa: chỉ cuộn khi con thú ra khỏi
       * khung 4x3 ô trung tâm. Bám từng pixel làm cả bản đồ rung nhẹ suốt lúc
       * con thú đi, và mắt đọc ra là NỀN đang trôi chứ không phải con thú đang
       * đi.
       *
       * Kẹp vào trong lòng bản đồ, nếu không camera lia ra ngoài mép và để lộ
       * một dải trống — thứ trông như bản đồ bị thủng.
       */
      const halfW = cols / 2;
      const halfH = rows / 2;
      const deadW = 2;
      const deadH = 1.5;
      if (x < camX + halfW - deadW) camX = x - halfW + deadW;
      if (x > camX + halfW + deadW) camX = x - halfW - deadW;
      if (y < camY + halfH - deadH) camY = y - halfH + deadH;
      if (y > camY + halfH + deadH) camY = y - halfH - deadH;
      camX = Math.max(0, Math.min(map.w - cols, camX));
      camY = Math.max(0, Math.min(map.h - rows, camY));
      world.x = -Math.round(camX * TILE) * zoom;
      world.y = -Math.round(camY * TILE) * zoom;
    },

    tileAt(clientX, clientY) {
      const box = app.canvas.getBoundingClientRect();
      // Cộng lại phần camera đã lia, nếu không mọi cú bấm đều trỏ vào ô ở góc
      // trên trái của KHUNG NHÌN thay vì ô thật dưới con trỏ.
      const x = Math.floor((clientX - box.left) / (TILE * zoom) + camX);
      const y = Math.floor((clientY - box.top) / (TILE * zoom) + camY);
      if (x < 0 || y < 0 || x >= map.w || y >= map.h) return null;
      return { x, y };
    },

    destroy() {
      // `destroy(true)` gỡ cả canvas lẫn texture khỏi GPU. Không gọi thì mỗi lần
      // mở lại bảng là một context WebGL nữa, và trình duyệt chỉ cho vài cái.
      app.destroy(true, { children: true });
    },
  };
}
