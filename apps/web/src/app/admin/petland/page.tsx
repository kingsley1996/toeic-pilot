"use client";

import { Download, Eraser, Grid2x2, Layers, Redo2, Squircle, Undo2, Upload } from "lucide-react";
import { useEffect, useReducer, useRef, useState } from "react";

import { reduce } from "@/components/petland-history";

import { Button, Field, Input, Page, PageHeader, Panel, Select, cx } from "@/components/ui";
import {
  SHEET_COLS,
  SHEET_IDS,
  SHEET_ROWS,
  TILE,
  emptyMap,
  parseMap,
  type Cell,
  type MapData,
  type SheetId,
} from "@/components/petland-map";
import { useRequireSession } from "@/lib/session";

/**
 * Trình vẽ bản đồ cho góc thú cưng.
 *
 * Tồn tại vì vòng lặp cũ hỏng: người viết code đoán bố cục, dựng ảnh, hỏi lại,
 * sửa mù. Người có mắt thẩm mỹ và người gõ phím phải là một, hoặc ít nhất phải
 * ngồi cùng một màn hình — và đây là màn hình đó.
 *
 * **Không dùng Pixi ở đây.** Mỗi ô là một `<div>` với `background-position` trỏ
 * vào tấm ghép. Kéo Pixi vào khu quản trị là bắt mọi trang admin gánh 163 KB cho
 * một việc mà CSS làm được — và trình vẽ không cần vòng lặp hình, nó chỉ cần
 * ảnh đứng yên.
 *
 * **Xuất ra tệp, không ghi vào máy chủ.** Bản đồ là NỘI DUNG và nó thuộc về git,
 * cùng lối với manifest audio và tấm ghép ô: sửa ở đây, tải `map.json` về, chép
 * đè vào `public/pet/`, commit. Không có bảng, không có endpoint, không có
 * chuyện hai máy có hai bản đồ khác nhau mà không ai biết.
 */

const ZOOM = 2;
const PX = TILE * ZOOM;

type Tool = "ground" | "objects" | "erase" | "solid";

function sheetStyle(sheet: SheetId, index: number, zoom: number) {
  const cols = SHEET_COLS[sheet];
  const rows = SHEET_ROWS[sheet];
  return {
    backgroundImage: `url(/pet/${sheet}.png)`,
    backgroundPosition: `-${(index % cols) * TILE * zoom}px -${Math.floor(index / cols) * TILE * zoom}px`,
    backgroundSize: `${cols * TILE * zoom}px ${rows * TILE * zoom}px`,
    // Không có dòng này thì trình duyệt nội suy và pixel art nhoè hết.
    imageRendering: "pixelated" as const,
  };
}

function TileButton({
  sheet,
  index,
  active,
  onPick,
}: {
  sheet: SheetId;
  index: number;
  active: boolean;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onPick}
      aria-label={`${sheet} tile ${index}`}
      aria-pressed={active}
      className={cx(
        "tile-checker relative h-9 w-9 shrink-0 rounded border",
        active ? "border-2 border-action" : "border-rule hover:border-rule-strong",
      )}
    >
      <span className="absolute inset-0" style={sheetStyle(sheet, index, ZOOM)} />
    </button>
  );
}

export default function PetlandEditorPage() {
  const { status } = useRequireSession({ canEdit: true });
  const [history, dispatch] = useReducer(reduce, null);
  const map = history?.present ?? null;
  const [sheet, setSheet] = useState<SheetId>("town");
  const [picked, setPicked] = useState<number>(0);
  const [tool, setTool] = useState<Tool>("ground");
  const [showSolid, setShowSolid] = useState(true);
  const painting = useRef(false);

  useEffect(() => {
    void fetch("/pet/map.json")
      .then((res) => res.json())
      .then((raw) => dispatch({ type: "load", map: parseMap(raw) ?? emptyMap(18, 13) }))
      .catch(() => dispatch({ type: "load", map: emptyMap(18, 13) }));
  }, []);

  /*
   * Ctrl+Z / Cmd+Z, và **cả hai** phải có: máy này là macOS, nơi Ctrl+Z không
   * phải phím hoàn tác — chỉ nghe `ctrlKey` là làm ra một tính năng không chạy
   * trên chính máy đang dùng nó.
   *
   * Bỏ qua khi con trỏ đang ở trong ô nhập: hai ô rộng/cao là `<input>`, và
   * trình duyệt đã có hoàn tác riêng cho chữ. Cướp phím ở đó nghĩa là gõ nhầm
   * một chữ số rồi bấm Ctrl+Z lại hoàn tác cả một nét vẽ.
   */
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "z") return;
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      event.preventDefault();
      dispatch({ type: event.shiftKey ? "redo" : "undo" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // `history === null` kiểm tường minh dù `map` suy ra từ nó: TypeScript không
  // thu hẹp được kiểu của `history` qua một biến dẫn xuất.
  if (status !== "authenticated" || history === null || !map) {
    return (
      <Page>
        <PageHeader eyebrow="Petland" title="Map editor" />
      </Page>
    );
  }

  const paint = (at: number) => {
    dispatch({
      type: "apply",
      fn: (current) => {
        const next: MapData = {
          ...current,
          ground: [...current.ground],
          objects: [...current.objects],
          solid: [...current.solid],
        };
        const cell: Cell = { sheet, index: picked };
        if (tool === "ground") next.ground[at] = cell;
        if (tool === "objects") next.objects[at] = cell;
        if (tool === "erase") {
          next.objects[at] = null;
          next.ground[at] = null;
        }
        if (tool === "solid") next.solid[at] = !current.solid[at];
        return next;
      },
    });
  };

  const resize = (w: number, h: number) => {
    dispatch({
      type: "commit",
      fn: (current) => {
        const next = emptyMap(w, h);
        // Giữ lại phần chồng lấn thay vì xoá sạch: đổi cỡ là thao tác người ta làm
        // GIỮA CHỪNG lúc thiết kế, và mất hết công vì gõ nhầm một con số là thứ
        // khiến người ta không dám đụng vào ô nhập nữa.
        for (let y = 0; y < Math.min(h, current.h); y += 1) {
          for (let x = 0; x < Math.min(w, current.w); x += 1) {
            next.ground[y * w + x] = current.ground[y * current.w + x];
            next.objects[y * w + x] = current.objects[y * current.w + x];
            next.solid[y * w + x] = current.solid[y * current.w + x];
          }
        }
        return next;
      },
    });
  };

  const download = () => {
    const blob = new Blob([JSON.stringify(map)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "map.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  const load = (file: File) => {
    void file.text().then((text) => {
      try {
        const parsed = parseMap(JSON.parse(text));
        if (parsed) dispatch({ type: "commit", fn: () => parsed });
      } catch {
        /* tệp hỏng thì giữ nguyên bản đang sửa — mất công vẽ vì chọn nhầm tệp
           là cái giá không đáng. */
      }
    });
  };

  const tools: Array<{ id: Tool; label: string; Icon: typeof Layers }> = [
    { id: "ground", label: "Ground", Icon: Grid2x2 },
    { id: "objects", label: "Objects", Icon: Layers },
    { id: "erase", label: "Erase", Icon: Eraser },
    { id: "solid", label: "Blocking", Icon: Squircle },
  ];

  return (
    <Page className="max-w-none">
      <PageHeader
        eyebrow="Petland"
        title="Map editor"
        description="Paint the pet corner. Export map.json and commit it to apps/web/public/pet/."
      />

      {/*
       * `flex` KHÔNG có `flex-wrap`, và bảng chọn `shrink-0`.
       *
       * Bản trước dùng `flex-wrap`: khung vẽ rộng theo số ô, nên chỉ cần bản đồ
       * quá vài chục ô là bảng chọn bị đẩy xuống DƯỚI map — và lúc đó người vẽ
       * phải cuộn lên chọn ô rồi cuộn xuống đặt, cho mỗi ô một lần. Cái vòng đó
       * làm hỏng đúng thứ trình vẽ sinh ra để có.
       *
       * Thay vào đó khung vẽ tự cuộn NGANG trong ô của nó, còn bảng chọn dính
       * bên trái và cuộn theo trang.
       */}
      <div className="flex gap-4">
        {/* --- bảng chọn ô --- */}
        <Panel className="sticky top-4 h-fit w-64 shrink-0 p-4">
          <Select value={sheet} onChange={(e) => setSheet(e.target.value as SheetId)}>
            {SHEET_IDS.map((id) => (
              <option key={id} value={id}>
                {id}.png
              </option>
            ))}
          </Select>
          <div className="mt-3 flex max-h-[30rem] flex-wrap gap-1 overflow-y-auto pr-1">
            {Array.from({ length: SHEET_COLS[sheet] * SHEET_ROWS[sheet] }, (_, i) => (
              <TileButton
                key={i}
                sheet={sheet}
                index={i}
                active={picked === i}
                onPick={() => setPicked(i)}
              />
            ))}
          </div>
          <p className="mt-3 font-data text-small text-ink-faint">
            {sheet} · tile {picked}
          </p>
        </Panel>

        {/* --- khung vẽ --- */}
        <div className="min-w-0 flex-1">
          <div className="mb-3 flex flex-wrap items-end gap-2">
            {tools.map(({ id, label, Icon }) => (
              <Button
                key={id}
                size="sm"
                variant={tool === id ? "primary" : "secondary"}
                onClick={() => setTool(id)}
              >
                <Icon size={14} strokeWidth={2} aria-hidden />
                {label}
              </Button>
            ))}
            <Button
              size="sm"
              variant={showSolid ? "primary" : "secondary"}
              onClick={() => setShowSolid((v) => !v)}
            >
              Show blocking
            </Button>
            {/* Có nút chứ không chỉ có phím: một phím tắt không hiện ở đâu cả là
                tính năng chỉ người viết nó biết. Nút mờ đi khi không còn gì để
                hoàn tác — đó là chỗ duy nhất nói ra chiều sâu lịch sử. */}
            <Button
              size="sm"
              variant="secondary"
              disabled={history.past.length === 0}
              title="Undo (Ctrl/Cmd+Z)"
              onClick={() => dispatch({ type: "undo" })}
            >
              <Undo2 size={14} strokeWidth={2} aria-hidden />
              Undo
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={history.future.length === 0}
              title="Redo (Ctrl/Cmd+Shift+Z)"
              onClick={() => dispatch({ type: "redo" })}
            >
              <Redo2 size={14} strokeWidth={2} aria-hidden />
              Redo
            </Button>
            <div className="w-20">
              <Field label="Width">
                <Input
                  type="number"
                  value={map.w}
                  min={4}
                  max={48}
                  onChange={(e) => resize(Number(e.target.value) || map.w, map.h)}
                />
              </Field>
            </div>
            <div className="w-20">
              <Field label="Height">
                <Input
                  type="number"
                  value={map.h}
                  min={4}
                  max={48}
                  onChange={(e) => resize(map.w, Number(e.target.value) || map.h)}
                />
              </Field>
            </div>
            <Button size="sm" variant="secondary" onClick={download}>
              <Download size={14} strokeWidth={2} aria-hidden />
              Export
            </Button>
            <label className="inline-flex">
              <input
                type="file"
                accept="application/json"
                className="sr-only"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) load(file);
                }}
              />
              <span className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded border border-rule-strong bg-panel px-2.5 text-small font-semibold text-ink hover:bg-recess">
                <Upload size={14} strokeWidth={2} aria-hidden />
                Import
              </span>
            </label>
          </div>

          <div className="overflow-x-auto">
            <div
              className="w-fit select-none border border-rule-strong bg-recess"
              style={{ display: "grid", gridTemplateColumns: `repeat(${map.w}, ${PX}px)` }}
              onPointerUp={() => (painting.current = false)}
              onPointerLeave={() => (painting.current = false)}
            >
              {map.ground.map((groundCell, at) => {
                const objectCell = map.objects[at];
                return (
                  <div
                    key={at}
                    role="button"
                    tabIndex={-1}
                    aria-label={`cell ${at % map.w},${Math.floor(at / map.w)}`}
                    onPointerDown={() => {
                      // Mốc lịch sử đặt ở đây, MỘT lần cho cả nét — không phải
                      // ở mỗi ô. Xem chú thích của `reduce`.
                      dispatch({ type: "begin" });
                      painting.current = true;
                      paint(at);
                    }}
                    /* Vẽ khi RÊ chuột, không chỉ khi bấm: lát một sân gạch bằng
                     cách bấm hai trăm lần là thứ không ai làm tới lần thứ hai. */
                    onPointerEnter={() => painting.current && paint(at)}
                    className="relative"
                    style={{ width: PX, height: PX }}
                  >
                    {groundCell && (
                      <span
                        className="absolute inset-0"
                        style={sheetStyle(groundCell.sheet, groundCell.index, ZOOM)}
                      />
                    )}
                    {objectCell && (
                      <span
                        className="absolute inset-0"
                        style={sheetStyle(objectCell.sheet, objectCell.index, ZOOM)}
                      />
                    )}
                    {showSolid && map.solid[at] && (
                      <span className="absolute inset-0 bg-alert/35" aria-hidden />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </Page>
  );
}
