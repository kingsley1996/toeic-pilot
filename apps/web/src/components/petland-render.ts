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
   * Con thú đang ngủ: nằm bẹp xuống và thở chậm, sâu hơn.
   *
   * Là một TRẠNG THÁI chứ không phải một hành động có tiến độ như `action`: giấc
   * ngủ kéo dài hàng giờ, nên nó không có `t` nào để chạy tới 1.
   */
  sleeping: boolean;
  /**
   * Những cuộc chạm mặt đang đứng trên bản đồ. Rỗng nghĩa là không có ai.
   *
   * Vẽ trong canvas chứ không phải một lớp DOM đè lên: chúng phải bị camera lia
   * theo, phải bị bầu trời đêm phủ lên, và phải đứng sau con thú khi con thú đi
   * qua trước mặt. Một thẻ DOM nổi trên canvas thì không có ba tính chất nào.
   *
   * Một MẢNG chứ không phải một cái: tối đa hai NPC và hai kẻ xâm nhập cùng
   * lúc, và một cuộc mới không bao giờ đẩy cuộc đang diễn ra đi. `id` đi kèm vì
   * trận đánh phải chỉ đích danh một trong số họ.
   */
  encounters: readonly { id: string; tile: number; x: number; y: number; danger: boolean }[];
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
  action: { kind: "feed" | "poke" | "walk" | "sleep" | "wake"; t: number } | null;
  /**
   * Trận đánh với kẻ xâm nhập: tiến độ 0..1, và có hạ gục được không.
   *
   * Sinh lúc vẽ như mọi chuyển động khác ở đây — không có khung hoạt ảnh nào để
   * mà chiếu. Tách khỏi `action` chứ không thêm một `kind` nữa vào đó, vì trận
   * đánh cần biết KẺ KIA đứng đâu: nó là chuyển động của hai thân, còn `action`
   * chỉ tả một thân.
   *
   * `win` quyết định đoạn kết: đúng một bước thì kẻ kia loạng choạng rồi đứng
   * lại, còn bước cuối thì nó văng ra và mờ đi.
   */
  fight: { id: string; t: number; win: boolean } | null;
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
  /**
   * Chỗ ĐẦU vị khách trong canvas, hoặc `null` khi không có ai.
   *
   * Bong bóng thoại là một phần tử DOM chứ không vẽ trên canvas: canvas này cố
   * ý không nạp phông chữ nào (cùng lý do dấu chấm than là hai hình chữ nhật),
   * và nạp một bộ phông cho vài câu tiếng Việt là kéo cả một tầng phụ thuộc —
   * chưa kể chữ vẽ trên canvas thì trình đọc màn hình không đọc được.
   *
   * Trả về toạ độ MÀN HÌNH, tính lại mỗi khung: máy quay xê dịch khi con thú đi
   * tới chỗ vị khách, nên một chỗ chốt lúc bấm sẽ trôi khỏi cái đầu nó đang chỉ.
   *
   * Tra theo `id` chứ không trả "vị khách": bốn người có thể cùng đứng đó, và
   * bong bóng thoại phải mọc trên đầu đúng người vừa nói.
   */
  guestScreen: (id: string) => { x: number; y: number } | null;
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
  if (action === null || action.kind === "walk" || action.kind === "wake") {
    return { dx: 0, lift: 0, squashX: 1, squashY: 1 };
  }
  if (action.kind === "sleep") {
    // Nằm xuống: bẹp dần theo chiều dọc rồi GIỮ NGUYÊN ở cuối, chứ không bật
    // lại — vì ngay sau đó `sleeping` tiếp quản và giữ đúng tư thế ấy. Bật lại
    // rồi mới nằm là một cú giật ngay giữa động tác nằm.
    const lie = Math.sin(Math.min(1, Math.max(0, action.t)) * Math.PI * 0.5);
    return { dx: 0, lift: 0, squashX: 1 + 0.12 * lie, squashY: 1 - 0.18 * lie };
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

  /*
   * Nhân vật của cuộc chạm mặt, cộng dấu hiệu trên đầu.
   *
   * Thêm TRƯỚC con thú nên con thú đi qua sẽ che nó — đúng thứ tự của một khung
   * cảnh nhìn nghiêng, và cũng là thứ giữ cho con thú luôn là nhân vật chính.
   *
   * Dấu hiệu vẽ bằng hai hình chữ nhật chứ không phải một ký tự: canvas này
   * không nạp phông chữ nào, và nạp một bộ phông cho đúng một dấu chấm than là
   * kéo cả một tầng phụ thuộc vào chỗ chỉ cần bốn chục pixel.
   */
  /**
   * Một chỗ đứng cho khách: sprite của họ và dấu hiệu trên đầu.
   *
   * Cấp phát DẦN và không bao giờ trả lại. Số khách bị chặn cứng ở bốn (hai mỗi
   * loại), nên "rò rỉ" ở đây có trần là bốn đối tượng cho cả phiên; đổi lại,
   * không có lúc nào một sprite bị huỷ trong khi vòng vẽ còn cầm nó — đúng loại
   * lỗi mà một khung hình lệch nhịp sẽ dựng ra.
   */
  type GuestSlot = { sprite: Sprite; mark: Graphics; tile: number; danger: boolean | null };
  const slots: GuestSlot[] = [];

  function slotAt(index: number): GuestSlot {
    while (slots.length <= index) {
      const sprite = new Sprite();
      sprite.anchor.set(0.5, 1);
      sprite.visible = false;
      const mark = new Graphics();
      mark.visible = false;
      /*
       * Chèn NGAY TRƯỚC con thú, không phải ở đầu danh sách.
       *
       * `addChildAt(…, 0)` đẩy vị khách xuống dưới CẢ tấm nền: mỗi ô cỏ là một
       * sprite được thêm vào từ lúc dựng sân khấu, nên đứng ở chỉ số 0 là đứng
       * sau chúng. Triệu chứng lại không giống nguyên nhân chút nào — dấu hiệu
       * vẫn hiện (nó nổi lên hai ô phía trên, thường rơi vào ô trống, mà ô trống
       * thì không có sprite nào để che) còn nhân vật thì biến mất hẳn.
       *
       * Trước con thú vì con thú đi qua thì phải che họ, đúng thứ tự của một
       * khung cảnh nhìn nghiêng.
       */
      const front = world.getChildIndex(pet);
      world.addChildAt(sprite, front);
      world.addChildAt(mark, front + 1);
      slots.push({ sprite, mark, tile: -1, danger: null });
    }
    return slots[index];
  }

  /*
   * Hai dấu hiệu, KHÁC HÌNH chứ không chỉ khác màu.
   *
   * Chỉ đổi màu là chỗ dựa vào thứ khoảng 8% đàn ông không phân biệt được — và
   * ở đây hai màu ấy đúng là cặp vàng/đỏ khó nhất. Việc và nguy hiểm phải đọc
   * ra được từ hình: một chấm than đứng một mình, và một chấm than nằm trong
   * khung tam giác.
   *
   * Vẽ trên nền một khối tối, vì cả hai đứng trước một bản đồ nhiều màu: một nét
   * 3px màu vàng trên mái nhà vàng là một nét không tồn tại. Bản trước đúng là
   * như thế — 3px, không viền — và người dùng báo là "không có dấu chấm than".
   */
  function drawMark(target: Graphics, danger: boolean): void {
    // Màu vẽ THẲNG vào hình, không qua `tint`: `tint` nhân lên MỌI lớp, nên nền
    // tối — thứ giữ cho dấu hiệu đọc được trên một bản đồ nhiều màu — cũng ngả
    // vàng theo và biến mất đúng chỗ nó phải làm việc.
    // Vàng cho việc, đỏ cho kẻ xâm nhập: cùng cặp `warn`/`alert` mà cả app đang
    // dùng, nên không ai phải học một bảng màu mới.
    const ink = danger ? 0xf87a82 : 0xe8a93c;
    target.clear();
    if (danger) {
      target
        .poly([0, -1.5, 5, 7, -5, 7])
        .fill({ color: 0x1a1416, alpha: 0.9 })
        .poly([0, -1.5, 5, 7, -5, 7])
        .stroke({ color: ink, width: 0.75 });
    } else {
      target
        .roundRect(-2.5, -1, 5, 9.5, 1.5)
        .fill({ color: 0x1a1416, alpha: 0.9 })
        .roundRect(-2.5, -1, 5, 9.5, 1.5)
        .stroke({ color: ink, width: 0.5 });
    }
    const top = danger ? 1.5 : 0.5;
    target.rect(-0.75, top, 1.5, 4).fill({ color: ink });
    target.rect(-0.75, top + 5, 1.5, 1.5).fill({ color: ink });
  }

  /*
   * Tia va chạm: bốn vạch toả ra, vẽ MỘT LẦN rồi chỉ bật/tắt và phóng to.
   *
   * Vẽ lại mỗi khung sẽ dựng lại hình học sáu chục lần một giây cho một thứ
   * chớp trong hai phần mười giây. Bốn vạch chứ không phải một vòng tròn: vòng
   * tròn ở cỡ này đọc ra là một chấm.
   */
  const spark = new Graphics();
  for (const [dx, dy] of [
    [1, 0],
    [-1, 0],
    [0.7, -0.7],
    [-0.7, -0.7],
  ]) {
    spark.moveTo(dx * 2, dy * 2).lineTo(dx * 7, dy * 7);
  }
  spark.stroke({ color: 0xfff2c4, width: 1.5 });
  spark.visible = false;

  const pet = new Sprite();
  // Neo ở ĐÁY và giữa: con thú "đứng trên" ô của nó, nên khi nhún hay thở thì
  // chân ở yên còn người nhấp nhô. Neo ở tâm làm nó lún xuống đất mỗi nhịp thở.
  pet.anchor.set(0.5, 1);
  world.addChild(pet);
  // Sau con thú: tia va chạm phải nằm TRÊN cả hai thân, nếu không nó chớp ở
  // đâu đó sau lưng và đọc ra là một lỗi vẽ.
  world.addChild(spark);

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
  /** Chỗ ĐẦU từng vị khách trong canvas, làm mới mỗi khung, tra theo id. */
  const guestScreens = new Map<string, { x: number; y: number }>();

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
      // Ngủ thì nhịp thở chậm còn một phần ba và sâu gấp đôi — đó là thứ đọc ra
      // "đang ngủ" ngay cả khi mẩu Zzz đã bay hết.
      const breathe = view.sleeping
        ? 1 + Math.sin(view.clock * 1.3) * 0.08
        : 1 + Math.sin(view.clock * 3.9) * 0.04;
      const lying = view.sleeping ? { x: 1.12, y: 0.82 } : { x: 1, y: 1 };
      const hop = t > 0 ? Math.abs(Math.sin(t * Math.PI)) : 0;
      /*
       * Chốt vị trí con thú vào LƯỚI PIXEL của thế giới, đúng như máy quay.
       *
       * `world.scale = zoom`, và máy quay đã tự làm tròn về pixel-thế-giới
       * (`Math.round(camX * TILE) * zoom`). Con thú thì không, nên toạ độ màn
       * hình của nó rơi vào giữa hai pixel: `roundPixels` của renderer kéo nó về
       * pixel màn hình gần nhất, mà pixel ấy KHÔNG phải bội của `zoom` — tức là
       * lưới pixel của con thú lệch khỏi lưới của tấm nền, và cứ vài khung hình
       * nó lại nhảy một cái. Mắt đọc ra là "đi không mượt", trong khi tốc độ thì
       * hoàn toàn đều.
       *
       * Làm tròn ở đây khiến bước đi rời rạc theo từng pixel-thế-giới (1/16 ô,
       * khoảng 53 lần mỗi giây ở nhịp 0,3 giây một ô) — đó chính là cách một
       * khung cảnh pixel art phải chuyển động, và nó khớp nhịp với tấm nền thay
       * vì trượt so với nó.
       */
      const pose = poseFor(view.action);
      pet.x = Math.round(pet.x + pose.dx);
      pet.y = Math.round((y + 1) * TILE - hop * 2 - pose.lift);
      pet.scale.set(
        (view.facing === "left" ? -1 : 1) * pose.squashX * lying.x,
        breathe * pose.squashY * lying.y,
      );

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
      // Cùng lưới pixel với con thú, nếu không thì vòng sáng trượt dưới chân nó
      // đúng một pixel mỗi lúc con thú vừa được làm tròn về phía kia.
      const footY = Math.round((y + 1) * TILE - 1);

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

      /*
       * Khách và dấu hiệu.
       *
       * Dấu hiệu nhấp nhô nhẹ và KHÔNG nhấp nháy: nhấp nháy là thứ mắt không bỏ
       * qua được, và một góc học có một chấm nhấp nháy thường trực sẽ bị đóng
       * lại. Nó chỉ cần đủ để nói "ở đây có việc".
       */
      const guests = view.encounters;
      guestScreens.clear();

      for (let i = 0; i < slots.length; i += 1) {
        const slot = slots[i];
        slot.sprite.visible = false;
        slot.mark.visible = false;
      }

      for (let i = 0; i < guests.length; i += 1) {
        const guest = guests[i];
        const slot = slotAt(i);
        const { sprite, mark } = slot;
        sprite.visible = true;
        mark.visible = true;

        if (guest.tile !== slot.tile) {
          sprite.texture = slice(creatures, guest.tile, CREATURE_COLS);
          slot.tile = guest.tile;
        }
        if (slot.danger !== guest.danger) {
          drawMark(mark, guest.danger);
          slot.danger = guest.danger;
        }

        // Lệch pha theo chỉ số: cả bốn nhấp nhô cùng nhịp thì đọc ra là một cơ
        // cấu máy móc, đúng lý do mỗi sinh vật hậu cảnh có `phase` riêng.
        const bob = Math.sin(view.clock * 2.4 + i * 1.7) * 1.2;
        sprite.x = guest.x * TILE + TILE / 2;
        sprite.y = (guest.y + 1) * TILE;
        sprite.scale.set(1, 1 + Math.sin(view.clock * 3.1 + i * 1.1) * 0.03);
        sprite.alpha = 1;
        sprite.rotation = 0;
        sprite.tint = 0xffffff;
        mark.x = sprite.x;
        mark.y = sprite.y - TILE - 12 + bob;

        /*
         * Trận đánh, dựng ở ĐÂY vì đây là chỗ duy nhất biết cả hai thân đứng đâu.
         *
         * Chỉ đánh vào ĐÚNG kẻ được chỉ đích danh (`fight.id`): bốn vị khách có
         * thể cùng đứng trên bản đồ, và đánh vào "cái đầu tiên" là đánh nhầm
         * người — một hoạt cảnh hoàn toàn trơn tru diễn tả sai chuyện vừa xảy ra.
         *
         * Ba nhịp lao tới: `|sin(3πt)|` cho đúng ba lần chạm, và số nhịp LẺ có
         * chủ ý — số chẵn kết thúc lúc con thú đang ở giữa đà lao và nó búng về
         * chỗ cũ, đúng cái lỗi mà nhịp nhai của "cho ăn" đã phải sửa.
         */
        const bout = view.fight;
        if (bout !== null && bout.id === guest.id) {
          const dir = Math.sign(sprite.x - pet.x) || 1;
          const swing = Math.abs(Math.sin(Math.min(1, bout.t) * Math.PI * 3));
          const hit = swing > 0.82;

          // Con thú quay MẶT về phía kẻ kia suốt trận, đè lên hướng đi thường:
          // đánh nhau mà mặt quay đi chỗ khác đọc ra là hỏng hoạt ảnh.
          pet.x += dir * TILE * 0.5 * swing;
          pet.y -= TILE * 0.12 * swing;
          pet.scale.x = Math.abs(pet.scale.x) * dir;
          pet.rotation = dir * 0.22 * swing;

          // Kẻ kia giật lùi và ửng đỏ đúng lúc chạm, không ửng suốt: một thân
          // đỏ liên tục đọc ra là "con này màu đỏ", không phải "con này ăn đòn".
          sprite.x += dir * 2.5 * swing;
          if (hit) sprite.tint = 0xf87a82;

          spark.visible = hit;
          spark.x = (pet.x + sprite.x) / 2;
          spark.y = pet.y - TILE * 0.45;
          spark.scale.set(0.8 + swing * 0.5);

          if (bout.win) {
            // Đoạn kết chỉ chiếm 30% cuối: hạ gục phải tới SAU mấy nhịp đánh,
            // nếu không thì nó là "chạm nhẹ rồi ngã" chứ không phải một trận.
            const fall = Math.max(0, (bout.t - 0.7) / 0.3);
            sprite.x += dir * TILE * 1.8 * fall;
            sprite.y -= TILE * 0.5 * Math.sin(fall * Math.PI);
            sprite.rotation = dir * fall * 1.9;
            sprite.alpha = 1 - fall;
            // Dấu hiệu tắt ngay khi bắt đầu ngã: một chấm than lơ lửng trên đầu
            // cái xác đang bay là thứ không ai định vẽ.
            if (fall > 0) mark.visible = false;
          }
        }

        guestScreens.set(guest.id, {
          x: (sprite.x - camX * TILE) * zoom,
          y: (sprite.y - TILE - camY * TILE) * zoom,
        });
      }

      sky.tint = view.sky.color;
      sky.alpha = view.sky.alpha;
      sky.width = cols * TILE * zoom;
      sky.height = rows * TILE * zoom;

      const dt = lastClock === 0 ? 0 : Math.min(0.1, view.clock - lastClock);
      lastClock = view.clock;
      for (const critter of critters) stepCritter(critter, dt, view.clock);
    },

    guestScreen(id) {
      return guestScreens.get(id) ?? null;
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
