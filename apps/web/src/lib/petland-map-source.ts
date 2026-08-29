import { API_ROUTES, type PetlandMapPublic } from "@toeic-pilot/shared";

import { parseMap, type MapData } from "@/components/petland-map";
import { apiFetch } from "@/lib/api";

/**
 * Bản đồ đang chạy đến từ đâu.
 *
 * `bundled` là tệp đã commit ở `public/pet/map.json`; `server` là hàng đã lưu
 * qua trình vẽ. Trả về cả nguồn chứ không chỉ dữ liệu, vì thiết kế cũ cố ý
 * không có bảng để tránh "hai nơi hai bản đồ mà không ai biết" — giữ được điều
 * đó bằng cách nói ra đang chạy bản nào, thay vì cấm.
 */
export type MapSource = "server" | "bundled";

export type LoadedMap = { map: MapData; source: MapSource };

async function bundled(): Promise<MapData | null> {
  const res = await fetch("/pet/map.json");
  return parseMap(await res.json());
}

export async function loadPetlandMap(): Promise<LoadedMap | null> {
  try {
    // 204 = chưa ai sửa trên web. `apiFetch` trả null ở đó, và đó là đường đi
    // BÌNH THƯỜNG, không phải lỗi.
    const saved = await apiFetch<PetlandMapPublic | null>(API_ROUTES.petlandMap, {});
    const parsed = saved ? parseMap(saved) : null;
    if (parsed) return { map: parsed, source: "server" };
  } catch {
    /* API hỏng thì góc thú cưng vẫn phải mở được: rơi về tệp đã commit. */
  }
  const fallback = await bundled();
  return fallback ? { map: fallback, source: "bundled" } : null;
}
