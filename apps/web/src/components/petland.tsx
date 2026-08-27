"use client";

import { API_ROUTES, type PetPublic } from "@toeic-pilot/shared";
import { GripHorizontal, Maximize2, Minimize2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { clamp, defaultPlace, readPlace, writePlace, type Place } from "@/components/petland-place";
import { PetHud } from "@/components/petland-ui";
import type { PetAction, PetNeeds } from "@/components/petland-pet";
import { tileForSpecies } from "@/components/petland-sprite";
import { cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import {
  findPath,
  nearestWalkable,
  parseMap,
  SHEET_COLS,
  TILE,
  type MapData,
  type Tile,
} from "@/components/petland-map";
import type { Stage } from "@/components/petland-render";

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
const STEP_SECONDS = 0.18;

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
            backgroundPosition: `-${(tileForSpecies("cat") % SHEET_COLS.town) * TILE * 2}px -${Math.floor(tileForSpecies("cat") / 10) * TILE * 2}px`,
            backgroundSize: `${10 * TILE * 2}px ${18 * TILE * 2}px`,
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
   * Giữ `Stage` ở ref để nút toàn-bản-đồ gọi được `setView`, còn hiệu ứng dựng
   * sân khấu thì KHÔNG phụ thuộc vào `full`. Cho `full` vào danh sách phụ thuộc
   * cũng chạy, nhưng nó tháo cả sân khấu ra dựng lại mỗi lần bấm — mất một WebGL
   * context mỗi lần, và con thú nhảy về chỗ cũ giữa lúc đang đi.
   */
  const stageRef = useRef<Stage | null>(null);
  const [size, setSize] = useState({ w: VIEW_W, h: VIEW_H });

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
      if (target) queue = findPath(map, tile, target);
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
        // Ô đã lưu có thể trỏ vào tường sau khi bản đồ được vẽ lại trong trình
        // sửa. Kéo con thú ra chỗ đứng được thay vì để nó kẹt trong hàng rào.
        tile = nearestWalkable(parsed, { x: pet.tile_x, y: pet.tile_y });
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
        const species = pet.tile;

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
          if (queue.length > 0) {
            progress += dt / STEP_SECONDS;
            while (progress >= 1 && queue.length > 0) {
              progress -= 1;
              from = tile;
              const next = queue.shift() as Tile;
              facing = next.x < tile.x ? "left" : next.x > tile.x ? "right" : facing;
              tile = next;
            }
            if (queue.length === 0) {
              progress = 0;
              save(tile, facing);
            }
          }
          made.draw({
            tile,
            from,
            progress: queue.length ? progress : 0,
            facing,
            species,
            clock: now / 1000,
          });
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
   * Hành động đi thẳng lên máy chủ và lấy nhu cầu MỚI về, không tự tính ở đây.
   *
   * Tự cộng trước rồi gửi sau ("ghi lạc quan") là đúng cho việc đổi con mascot —
   * thứ không có gì để mất nếu trượt. Ở đây thì khác: máy chủ mới biết con thú đã
   * đói bao lâu, và một con số client tự nghĩ ra sẽ bị đè ngay ở lần đọc kế tiếp,
   * nên người dùng thấy thanh chỉ số nhảy lên rồi tụt xuống.
   */
  const act = (action: PetAction) => {
    setBusy(true);
    setRefused(null);
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
    <div className="shadow-overlay w-fit rounded border border-rule-strong bg-panel">
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
        <span className="flex items-center gap-1" onPointerDown={(e) => e.stopPropagation()}>
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
      <div
        ref={host}
        className={cx(
          "bg-recess",
          // Chừa đúng chỗ cho canvas trước khi Pixi dựng xong, nếu không cả góc
          // màn hình nhảy một cái khi ảnh về.
          "block",
        )}
        style={{ width: size.w * TILE * ZOOM, height: size.h * TILE * ZOOM }}
      />
      {needs && (
        <div className="border-t border-rule">
          <PetHud needs={needs} busy={busy} onAction={act} />
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
