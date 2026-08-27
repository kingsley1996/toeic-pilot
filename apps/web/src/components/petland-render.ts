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
import {
  Application,
  Assets,
  Container,
  Graphics,
  Rectangle,
  Sprite,
  Texture,
  TextureSource,
} from "pixi.js";

import { MAP_LIVING } from "@/components/petland-bestiary";
import {
  SHEET_COLS,
  TILE,
  wanderStep,
  type MapData,
  type SheetId,
  type Tile,
} from "@/components/petland-map";

const SHEET_URL: Record<SheetId, string> = {
  town: "/pet/town.png",
  farm: "/pet/farm.png",
  water: "/pet/water.png",
  stone: "/pet/stone.png",
};
const CREATURES_URL = "/pet/creatures.png";

/** Số cột của tấm sinh vật. Số cột của các tấm nền nằm ở `SHEET_COLS`. */
const CREATURE_COLS = 10;

/**
 * Những ô trong lớp `objects` là SINH VẬT, không phải đồ vật.
 *
 * Chúng không được vẽ như một ô đứng yên: chúng tách ra thành sprite riêng biết
 * thở và biết đi lại quanh chỗ của mình. Trước đó bò, cừu, gà và bác nông dân
 * đứng bất động như cái hàng rào cạnh họ — trong một khung cảnh mà con thú vẫn
 * thở và vẫn đi, một cái làng đông cứng đọc ra là ảnh chụp chứ không phải nơi ở.
 *
 * Danh sách nằm ở `petland-bestiary.ts`, chỗ trả lời câu "ô nào là con gì" cho
 * cả tấm sinh vật lẫn hai tấm nền. Để hai bảng ở hai tệp là để chúng lệch nhau
 * vào ngày ai đó thêm một con vật vào bản đồ.
 */
const LIVING_TILES: Partial<Record<SheetId, ReadonlySet<number>>> = MAP_LIVING;

const WANDER_RADIUS = 2;
/** Giây cho mỗi ô — chậm hơn con thú, vì chúng là hậu cảnh chứ không phải nhân vật. */
const WANDER_STEP_SECONDS = 0.55;

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
  /**
   * Lớp phủ bầu trời theo giờ trong thế giới Petland.
   *
   * Màu và độ đậm tính ở `petland-clock.ts` — một hàm thuần trên đồng hồ — chứ
   * không quyết định ở đây: tệp này vẽ thứ nó được bảo vẽ, và ngày máy chủ cũng
   * cần biết ở Petland đang là mấy giờ thì phép tính ấy phải chép sang được.
   */
  sky: { color: number; alpha: number };
  /**
   * Vòng sáng dưới chân, theo HẠNG HIẾM của con đang nuôi.
   *
   * Màu và độ mạnh tính ở `petland.tsx` từ token thiết kế, không quyết định ở
   * đây: tệp này vẽ thứ nó được bảo vẽ, và bảng loài (kể cả hạng) là dữ liệu
   * admin sửa được — một bảng tra hạng→màu nằm trong tầng vẽ sẽ trôi khỏi nó.
   */
  glow: { color: number; strength: number };
  /**
   * Hành động đang diễn ra và tiến độ 0..1 của nó, hoặc `null` khi không có.
   *
   * Tư thế sinh LÚC VẼ từ một con số, đúng như nhịp thở và cái nhún: gói sprite
   * không có khung hoạt ảnh nào (xem `public/pet/CREDITS.md`), nên "nhai" và
   * "giật mình" phải là phép biến hình chứ không phải ảnh.
   */
  action: { kind: "feed" | "poke" | "walk"; t: number } | null;
};

/** Một sinh vật hậu cảnh: ô của nó, chỗ nó thuộc về, và nhịp đi của riêng nó. */
type Critter = {
  sprite: Sprite;
  home: Tile;
  tile: Tile;
  from: Tile;
  /** 0..1 giữa `from` và `tile`; 0 nghĩa là đang đứng. */
  progress: number;
  /** 1 quay phải, -1 quay trái. Mọi sprite trong gói đều vẽ quay phải. */
  facing: 1 | -1;
  /** Giây còn lại trước khi nghĩ tới bước tiếp theo. */
  wait: number;
  /** Lệch pha nhịp thở, để cả đàn không thở cùng nhau. */
  phase: number;
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
  /**
   * Chỗ con thú đang đứng, tính bằng pixel TRONG canvas.
   *
   * Để những mẩu bay lên (`PixelBits`) neo đúng đầu nó. Chúng là phần tử DOM chứ
   * không vẽ vào canvas, nên chúng cần một con số từ bên trong — và chỉ tệp này
   * biết camera đang lia tới đâu.
   */
  petScreen: () => { x: number; y: number };
  destroy: () => void;
};

function slice(sheet: Texture, index: number, cols: number): Texture {
  const x = (index % cols) * TILE;
  const y = Math.floor(index / cols) * TILE;
  return new Texture({ source: sheet.source, frame: new Rectangle(x, y, TILE, TILE) });
}

/**
 * Tư thế của con thú trong lúc một hành động đang diễn ra.
 *
 * Sinh bằng phép biến hình chứ không bằng khung ảnh — gói sprite chỉ có MỘT
 * khung cho mỗi loài (`public/pet/CREDITS.md`), và đó là đánh đổi có chủ ý: thêm
 * một loài tốn một con số, không tốn 26 khung vẽ tay. Cái giá là mọi chuyển động
 * phải diễn tả được bằng vị trí, tỉ lệ và một chút xoay.
 *
 * Ba hành động phải TRÔNG khác nhau, không chỉ khác số:
 *
 *   · **Cho ăn** — cúi xuống rồi nhai: bốn nhịp bẹp theo chiều dọc. Cúi trước
 *     rồi mới nhai, vì một con thú nhai giữa không trung không đọc ra là đang ăn.
 *   · **Chọc** — giật mình: bật lên một nhịp và lùi lại, rồi trở về. Cùng biên
 *     độ với nhún khi đi thì nó lẫn vào bước chân, nên nó cao gấp ba.
 *   · **Đi dạo** — KHÔNG có tư thế riêng ở đây. Con thú đi thật, và cái đi thật
 *     ấy chính là hoạt ảnh; thêm một tư thế nữa lên trên là hai chuyển động cãi
 *     nhau trên cùng một thân.
 */
function poseFor(action: PetView["action"]): {
  dx: number;
  lift: number;
  squashX: number;
  squashY: number;
} {
  if (action === null || action.kind === "walk") {
    return { dx: 0, lift: 0, squashX: 1, squashY: 1 };
  }
  const t = Math.min(1, Math.max(0, action.t));
  if (action.kind === "feed") {
    // Nửa đầu cúi xuống, nửa sau nhai. `ease` kéo cái cúi mượt vào chỗ, còn
    // `chew` là bốn nhịp bẹp — số nhịp lẻ sẽ kết thúc ở giữa một nhịp và con
    // thú búng về tư thế đứng.
    const bow = Math.sin(Math.min(1, t * 2) * Math.PI * 0.5);
    const chew = t > 0.35 ? Math.sin((t - 0.35) * Math.PI * 8) : 0;
    return {
      dx: 0,
      lift: -1.5 * bow,
      squashX: 1 + 0.06 * bow,
      squashY: 1 - 0.1 * bow + 0.05 * chew,
    };
  }
  // Chọc: bật lên rồi rơi xuống trong một nhịp, kèm lùi lại nửa ô rồi về.
  const jump = Math.sin(t * Math.PI);
  return {
    dx: -2.5 * Math.sin(t * Math.PI * 2),
    lift: 5 * jump,
    squashX: 1 - 0.08 * jump,
    squashY: 1 + 0.12 * jump,
  };
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
  //
  // Trừ SINH VẬT: bò, cừu, gà và người tách ra thành sprite riêng ở dưới, vì
  // chúng phải thở và phải đi lại. Chúng vẫn đứng đúng ô mà bản đồ đặt — bản đồ
  // không phải sửa gì, và tắt hiệu ứng này đi thì chúng lại thành ô tĩnh.
  const critters: Critter[] = [];
  for (const layer of [map.ground, map.objects]) {
    for (let i = 0; i < layer.length; i += 1) {
      const cell = layer[i];
      if (cell === null) continue;
      const home = { x: i % map.w, y: Math.floor(i / map.w) };
      if (layer === map.objects && LIVING_TILES[cell.sheet]?.has(cell.index)) {
        const sprite = new Sprite(slice(sheets[cell.sheet], cell.index, SHEET_COLS[cell.sheet]));
        // Neo đáy-giữa như con thú, để nhịp thở nhấp nhô ở lưng chứ không làm
        // con vật lún xuống đất.
        sprite.anchor.set(0.5, 1);
        world.addChild(sprite);
        critters.push({
          sprite,
          home,
          tile: home,
          from: home,
          progress: 0,
          facing: 1,
          // Mỗi con một nhịp nghỉ khác nhau: cùng nhịp thì cả đàn bước cùng lúc
          // và đọc ra là một cơ cấu máy móc, không phải mấy con vật.
          wait: 1 + Math.random() * 5,
          phase: Math.random() * Math.PI * 2,
        });
        continue;
      }
      const sprite = new Sprite(slice(sheets[cell.sheet], cell.index, SHEET_COLS[cell.sheet]));
      sprite.x = home.x * TILE;
      sprite.y = home.y * TILE;
      world.addChild(sprite);
    }
  }

  /*
   * Vòng sáng dưới chân, để phân biệt hạng hiếm ngay trên bản đồ.
   *
   * BA lớp chứ không một, và đó là khác biệt giữa "cái bóng mờ" với "con này có
   * đẳng cấp": một hình bầu dục 22% độ đậm nằm dưới chân đọc ra là bóng đổ, vì
   * bóng đổ đúng là như thế. Quầng rộng cho ra vùng sáng, lõi đặc cho ra điểm
   * chói, và vòng lan toả ra ngoài rồi tắt là thứ mắt đọc thành "đang phát ra
   * cái gì đó" — không lớp nào trong ba lớp ấy tự nó làm được việc đó.
   *
   * Thêm vào TRƯỚC sprite con thú nên cả ba nằm dưới — Pixi vẽ theo thứ tự thêm
   * vào, không có z-index nào ở đây.
   *
   * Vẽ MỘT lần rồi đổi màu bằng `tint`: vẽ lại hình mỗi khung hình là dựng lại
   * hình học 60 lần mỗi giây cho ba hình không đổi.
   *
   * Bầu dục DẸT chứ không tròn: nó nằm trên mặt đất nhìn nghiêng, và một vòng
   * tròn đều đọc ra là quả bóng dựng đứng dưới chân.
   *
   * Cỡ đo theo CON THÚ, không theo ô bản đồ: sprite rộng 16px, nên quầng lớn
   * nhất (bán kính ~10,6) vừa quá vai nó một chút. Bản trước rộng gấp rưỡi thế
   * và tràn sang hai ô bên cạnh — lúc đó nó thôi là vòng sáng của con thú và
   * thành một vũng sáng trên bản đồ, đúng thứ kéo mắt ra khỏi chính con thú.
   */
  const halo = new Graphics();
  halo.ellipse(0, 0, 9, 4).fill({ color: 0xffffff });
  const core = new Graphics();
  core.ellipse(0, 0, 5, 2.2).fill({ color: 0xffffff });
  const wave = new Graphics();
  wave.ellipse(0, 0, 7, 3).stroke({ color: 0xffffff, width: 1.25 });
  world.addChild(halo, wave, core);

  const pet = new Sprite();
  // Neo ở ĐÁY và giữa: con thú "đứng trên" ô của nó, nên khi nhún hay thở thì
  // chân ở yên còn người nhấp nhô. Neo ở tâm làm nó lún xuống đất mỗi nhịp thở.
  pet.anchor.set(0.5, 1);
  world.addChild(pet);

  /**
   * Một nhịp của một sinh vật hậu cảnh: chờ, chọn ô, đi, rồi chờ tiếp.
   *
   * Nằm trong `createStage` để đọc được `map` — tách ra ngoài thì phải truyền
   * bản đồ vào mỗi khung hình cho từng con, và đó là một tham số chỉ để lách
   * closure.
   *
   * Chúng đi CHẬM hơn con thú và nghỉ lâu, có chủ ý: đây là hậu cảnh. Một cái
   * làng mà mọi thứ đều nhúc nhích cùng tốc độ với nhân vật chính thì mắt không
   * biết nhìn vào đâu.
   */
  function stepCritter(critter: Critter, dt: number, clock: number): void {
    if (critter.progress > 0) {
      critter.progress += dt / WANDER_STEP_SECONDS;
      if (critter.progress >= 1) {
        critter.progress = 0;
        critter.from = critter.tile;
        critter.wait = 1.5 + Math.random() * 6;
      }
    } else {
      critter.wait -= dt;
      if (critter.wait <= 0) {
        const next = wanderStep(map, critter.tile, critter.home, WANDER_RADIUS, Math.random);
        if (next === null) {
          // Bị vây kín: nghỉ thêm rồi thử lại. Đứng im vẫn đúng hơn là nhảy qua
          // hàng rào, và cái hàng rào ấy là thứ giải thích vì sao nó ở đây.
          critter.wait = 3;
        } else {
          critter.from = critter.tile;
          critter.facing =
            next.x < critter.tile.x ? -1 : next.x > critter.tile.x ? 1 : critter.facing;
          critter.tile = next;
          critter.progress = 0.0001;
        }
      }
    }

    const t = critter.progress;
    const x = critter.from.x + (critter.tile.x - critter.from.x) * t;
    const y = critter.from.y + (critter.tile.y - critter.from.y) * t;
    const hop = t > 0 ? Math.abs(Math.sin(t * Math.PI)) : 0;
    critter.sprite.x = x * TILE + TILE / 2;
    critter.sprite.y = (y + 1) * TILE - hop * 1.5;
    critter.sprite.scale.set(critter.facing, 1 + Math.sin(clock * 2.6 + critter.phase) * 0.03);
  }

  /*
   * Lớp phủ bầu trời, thêm SAU con thú nên nó nằm trên tất cả.
   *
   * Vào `app.stage` chứ không vào `world`: `world` bị camera lia và bị phóng
   * `zoom`, nên một hình chữ nhật nằm trong đó sẽ trôi theo bản đồ và để lộ một
   * góc chưa phủ mỗi khi con thú đi. Bầu trời thì phủ cả KHUNG NHÌN, và khung
   * nhìn là chuyện của sân khấu.
   *
   * Vẽ một hình 1×1 rồi kéo bằng `scale`: `resize` mỗi lần đổi khung nhìn sẽ
   * phải dựng lại hình học, còn thế này chỉ là hai phép nhân.
   */
  const sky = new Graphics();
  sky.rect(0, 0, 1, 1).fill({ color: 0xffffff });
  sky.eventMode = "none";
  app.stage.addChild(sky);

  let currentSpecies = -1;
  let camX = 0;
  let camY = 0;
  // `dt` suy ra từ chính `clock` của khung hình thay vì thêm một tham số: người
  // gọi đã có sẵn đồng hồ, và hai nguồn thời gian trong một vòng vẽ là hai thứ
  // trôi khỏi nhau.
  let lastClock = 0;
  let petScreenX = 0;
  let petScreenY = 0;

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
      const pose = poseFor(view.action);
      pet.x += pose.dx;
      pet.y = (y + 1) * TILE - hop * 2 - pose.lift;
      pet.scale.set((view.facing === "left" ? -1 : 1) * pose.squashX, breathe * pose.squashY);

      /*
       * Vòng sáng bám ĐẤT, không bám con thú.
       *
       * Nó dùng `y` chưa trừ cái nhún, nên lúc con thú nhảy lên thì vòng sáng ở
       * lại dưới đất — chính chỗ đó làm mắt đọc ra "cái bóng phát sáng trên mặt
       * đất" thay vì "một vòng dính vào bụng con thú". Cùng lý do nó không nhận
       * `pose.lift`.
       *
       * Nhịp thở của vòng sáng nhanh gấp đôi nhịp thở con thú và LỆCH PHA: cùng
       * nhịp thì hai thứ phồng lên cùng lúc và trông như một khối.
       */
      const strength = view.glow.strength;
      const breath = 0.5 + 0.5 * Math.sin(view.clock * 2.2 + 1.1);
      const footY = (y + 1) * TILE - 1;

      halo.x = core.x = wave.x = pet.x;
      halo.y = core.y = wave.y = footY;
      halo.tint = core.tint = wave.tint = view.glow.color;

      // Quầng: rộng ra và đậm lên theo hạng. Ngay cả hạng thường cũng đủ thấy —
      // 0,3 là ngưỡng mà mắt còn đọc ra "có màu" chứ không phải "hơi bẩn".
      halo.alpha = 0.3 + 0.34 * strength + 0.12 * strength * breath;
      halo.scale.set(0.8 + 0.3 * strength + 0.08 * strength * breath);

      // Lõi: điểm chói dưới chân, gần như đặc ở hạng cực hiếm.
      core.alpha = 0.55 + 0.4 * strength;
      core.scale.set(0.9 + 0.2 * strength);

      /*
       * Vòng lan toả, CHỈ cho hai hạng cao.
       *
       * Nó là thứ tốn chú ý nhất, nên cho hạng nào cũng có thì không còn phân
       * biệt được gì — thứ hiếm phải hiếm cả trong cách nó chiếm mắt người nhìn.
       * Chu kỳ ~1,8 giây, lan từ lõi ra quá quầng rồi tắt hẳn.
       */
      if (strength >= 0.55) {
        const t = (view.clock / 1.8) % 1;
        wave.visible = true;
        wave.alpha = (1 - t) * 0.55 * strength;
        wave.scale.set(0.6 + t * 0.95);
      } else {
        wave.visible = false;
      }

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

      // Chỗ đầu con thú, tính bằng pixel trong canvas — để những mẩu bay lên
      // (phần tử DOM) neo đúng chỗ. Trừ đi camera vì `pet.x` là toạ độ THẾ GIỚI.
      petScreenX = (pet.x - camX * TILE) * zoom;
      petScreenY = (pet.y - TILE - camY * TILE) * zoom;

      sky.tint = view.sky.color;
      sky.alpha = view.sky.alpha;
      sky.width = cols * TILE * zoom;
      sky.height = rows * TILE * zoom;

      const dt = lastClock === 0 ? 0 : Math.min(0.1, view.clock - lastClock);
      lastClock = view.clock;
      for (const critter of critters) stepCritter(critter, dt, view.clock);
    },

    petScreen() {
      return { x: petScreenX, y: petScreenY };
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
