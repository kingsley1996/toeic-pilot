import type { MapData } from "@/components/petland-map";

/**
 * Lịch sử sửa, kiểu quá khứ · hiện tại · tương lai.
 *
 * Dùng `useReducer` chứ không ba `useState`: hoàn tác phải đọc cả ba rồi ghi cả
 * ba trong MỘT lần, và ba `setState` lồng nhau thì hàm cập nhật không còn thuần
 * — đúng loại lỗi chỉ hiện ra khi React chạy lại một lần dựng.
 *
 * **Một lần hoàn tác = một NÉT, không phải một ô.** Rê chuột qua ba mươi ô sinh
 * ba mươi lần ghi; nếu mỗi lần là một mốc thì Ctrl+Z ba mươi lần mới xoá xong
 * một nét kẻ, và không ai dùng nút đó nữa. Mốc chỉ được đẩy vào lúc BẮT ĐẦU nét
 * (`begin`), còn các ô sau trong cùng nét chỉ `apply`.
 */
export const HISTORY_LIMIT = 60;

export type History = { past: MapData[]; present: MapData; future: MapData[] };

export type Action =
  | { type: "load"; map: MapData }
  | { type: "begin" }
  | { type: "apply"; fn: (map: MapData) => MapData }
  | { type: "commit"; fn: (map: MapData) => MapData }
  | { type: "undo" }
  | { type: "redo" };

export function reduce(state: History | null, action: Action): History | null {
  if (action.type === "load") return { past: [], present: action.map, future: [] };
  if (state === null) return state;
  switch (action.type) {
    case "begin":
      // Mở một nét: đẩy hiện tại vào quá khứ và **xoá tương lai**. Vẽ tiếp sau
      // khi hoàn tác thì nhánh cũ không còn nghĩa gì; giữ nó lại sẽ cho Ctrl+Y
      // dán một bản đồ thuộc về một dòng lịch sử khác.
      return {
        past: [...state.past, state.present].slice(-HISTORY_LIMIT),
        present: state.present,
        future: [],
      };
    case "apply":
      return { ...state, present: action.fn(state.present) };
    case "commit":
      // Thao tác rời rạc (đổi cỡ, nạp tệp): vừa đặt mốc vừa đổi, trong một bước.
      return {
        past: [...state.past, state.present].slice(-HISTORY_LIMIT),
        present: action.fn(state.present),
        future: [],
      };
    case "undo": {
      const prev = state.past.at(-1);
      if (!prev) return state;
      return {
        past: state.past.slice(0, -1),
        present: prev,
        future: [state.present, ...state.future].slice(0, HISTORY_LIMIT),
      };
    }
    case "redo": {
      const [next, ...rest] = state.future;
      if (!next) return state;
      return {
        past: [...state.past, state.present].slice(-HISTORY_LIMIT),
        present: next,
        future: rest,
      };
    }
  }
}
