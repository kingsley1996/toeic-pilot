"use client";

import { API_ROUTES, type PetSpeciesPublic } from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import { Alert, Button, Input, Page, PageHeader, Panel, Select, cx } from "@/components/ui";
import { TILE } from "@/components/petland-map";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Bảng loài thú (ADR-010 §6.3).
 *
 * Mọi con số về loài là một HÀNG, không phải một hằng số trong mã — cùng khuôn
 * `/admin/progression`, và cùng lý do: thêm một loài không nên cần deploy.
 *
 * Không có nút xoá, chỉ có công tắc bật/tắt. Xoá một loài mà ai đó đang nuôi để
 * lại `pet_state.species` trỏ vào hư không; tắt thì loài biến khỏi gacha còn con
 * thú đang nuôi vẫn vẽ ra được.
 */

const TIERS = ["common", "uncommon", "rare", "epic"] as const;
const SHEET_ROWS_CREATURES = 18;
const CREATURE_COLS = 10;
const ZOOM = 2;

/** Ô sinh vật vẽ bằng CSS. Trang này không cần vòng lặp hình, chỉ cần ảnh đứng yên. */
function tileStyle(tile: number) {
  return {
    backgroundImage: "url(/pet/creatures.png)",
    backgroundPosition: `-${(tile % CREATURE_COLS) * TILE * ZOOM}px -${Math.floor(tile / CREATURE_COLS) * TILE * ZOOM}px`,
    backgroundSize: `${CREATURE_COLS * TILE * ZOOM}px ${SHEET_ROWS_CREATURES * TILE * ZOOM}px`,
    imageRendering: "pixelated" as const,
  };
}

export default function PetSpeciesAdminPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [rows, setRows] = useState<PetSpeciesPublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<PetSpeciesPublic[]>(API_ROUTES.adminPetSpecies, { token })
      .then(setRows)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load the species table."),
      );
  }, [token]);

  const patch = (code: string, changes: Partial<PetSpeciesPublic>) => {
    if (!token) return;
    setError(null);
    // Gửi ĐÚNG trường vừa đổi. `PATCH` phân biệt khoá vắng mặt với khoá null,
    // nên gửi cả hàng sẽ biến một lần sửa nhãn thành một lần ghi đè — và nếu
    // state cũ hơn database thì nó lặng lẽ khôi phục giá trị cũ.
    void apiFetch<PetSpeciesPublic>(API_ROUTES.adminPetSpeciesItem(code), {
      method: "PATCH",
      token,
      body: JSON.stringify(changes),
    })
      .then((updated) =>
        setRows((current) => (current ?? []).map((row) => (row.code === code ? updated : row))),
      )
      .catch((err) => setError(err instanceof ApiError ? err.message : "Save failed."));
  };

  if (status !== "authenticated") {
    return (
      <Page>
        <PageHeader eyebrow="Petland" title="Species" />
      </Page>
    );
  }

  return (
    <Page className="max-w-4xl">
      <PageHeader
        eyebrow="Petland"
        title="Species"
        description="Every number here is a row, not a constant. Tile indexes point into public/pet/creatures.png."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <div className="grid gap-2">
        {rows?.map((row) => (
          <Panel
            key={row.code}
            className={cx("flex flex-wrap items-center gap-3 p-3", !row.enabled && "opacity-60")}
          >
            {/* Nền ca-rô: ô sinh vật là PNG trong suốt, và trên nền panel ở chế
                độ tối chúng chỉ còn là những mảng đen. */}
            <span
              aria-hidden
              className="tile-checker relative h-9 w-9 shrink-0 rounded border border-rule"
            >
              <span className="absolute inset-0" style={tileStyle(row.tile)} />
            </span>

            <span className="w-28 shrink-0 font-data text-small text-ink-faint">{row.code}</span>

            <Input
              defaultValue={row.label}
              aria-label={`Label for ${row.code}`}
              className="w-40"
              onBlur={(event) => {
                const next = event.target.value.trim();
                if (next && next !== row.label) patch(row.code, { label: next });
              }}
            />

            <label className="flex items-center gap-1.5 text-small text-ink-muted">
              Tile
              <Input
                type="number"
                min={0}
                max={179}
                defaultValue={row.tile}
                aria-label={`Tile for ${row.code}`}
                className="w-20"
                onBlur={(event) => {
                  const next = Number(event.target.value);
                  if (Number.isInteger(next) && next !== row.tile) patch(row.code, { tile: next });
                }}
              />
            </label>

            <Select
              value={row.tier}
              aria-label={`Tier for ${row.code}`}
              className="w-32"
              onChange={(event) =>
                patch(row.code, { tier: event.target.value as PetSpeciesPublic["tier"] })
              }
            >
              {TIERS.map((tier) => (
                <option key={tier} value={tier}>
                  {tier}
                </option>
              ))}
            </Select>

            <Button
              size="sm"
              variant={row.enabled ? "secondary" : "primary"}
              className="ml-auto"
              onClick={() => patch(row.code, { enabled: !row.enabled })}
            >
              {row.enabled ? "Disable" : "Enable"}
            </Button>
          </Panel>
        ))}
      </div>

      <p className="mt-4 text-small text-ink-muted">
        {/* Nói ra hệ quả của việc gieo lười, vì nó bất ngờ: bảng rỗng không phải
            một cấu hình, nó là "chưa từng cấu hình". */}
        Disabling keeps a species out of gacha while whoever already owns one keeps it. Deleting
        every row is not a way to empty the table — the defaults seed themselves on the next read.
      </p>
    </Page>
  );
}
