"use client";

import { API_ROUTES, type CreatureEdit, type CreaturePublic } from "@toeic-pilot/shared";
import Link from "next/link";
import { Pencil, PawPrint } from "lucide-react";
import { useEffect, useState } from "react";

import { Creature } from "@/components/petland-creature";
import { Alert, Button, Input, Page, PageHeader, Panel, Select, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Bảng phân vai ô sinh vật — `petland-bestiary.ts` xuống database (migration 071).
 *
 * Mỗi ô của `creatures.png` là MỘT ô vuông, xếp vào bốn bảng theo vai. Bấm ô để
 * đổi vai — ô tự nhảy sang bảng khác — hoặc đặt tên. "Chuyển thành thú nuôi"
 * tạo hàng loài tại đúng ô đó: membership gacha thuộc về `pet_species`, nên
 * đây là TẠO loài chứ không phải đổi vai, và ô nhảy sang bảng thú nuôi ngay.
 */

const ROLES = ["npc", "wildlife", "intruder"] as const;
type Role = (typeof ROLES)[number];

const TIERS = ["common", "uncommon", "rare", "epic", "legendary", "god"] as const;

/* Trọng số mặc định theo hạng — khớp `CreaturePromote.TIER_WEIGHTS` ở server.
   Để trống nghĩa là "dùng mặc định của hạng", con số gợi ý nói điều đó. */
const TIER_WEIGHTS: Record<(typeof TIERS)[number], number> = {
  common: 40,
  uncommon: 25,
  rare: 10,
  epic: 4,
  legendary: 2,
  god: 1,
};

const ROLE_BOARDS: ReadonlyArray<{ role: Role; title: string; hint: string }> = [
  { role: "npc", title: "Dân làng (NPC)", hint: "Đứng trong làng, giao việc nhẹ, thưởng nhỏ." },
  {
    role: "intruder",
    title: "Kẻ xâm nhập",
    hint: "Xuất hiện ở rìa bản đồ, nhiều bước, thưởng lớn — đổi vai vào đây là mở thêm đối thủ.",
  },
  { role: "wildlife", title: "Hoang dã", hint: "Cảnh sống, không nói chuyện, không đánh nhau." },
];

export default function CreatureBoardPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [rows, setRows] = useState<CreaturePublic[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [draftRole, setDraftRole] = useState<Role>("npc");
  const [draftLabel, setDraftLabel] = useState("");
  const [promoteCode, setPromoteCode] = useState("");
  const [promoteTier, setPromoteTier] = useState<(typeof TIERS)[number]>("common");
  const [promoteWeight, setPromoteWeight] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<CreaturePublic[]>(API_ROUTES.adminPetlandCreatures, { token })
      .then(setRows)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Không tải được bảng phân vai."),
      );
  }, [token]);

  const select = (row: CreaturePublic) => {
    setSelected(row.tile);
    setDraftRole(row.role as Role);
    setDraftLabel(row.label ?? "");
    setPromoteCode("");
    setPromoteTier("common");
    setPromoteWeight("");
    setError(null);
  };

  const save = () => {
    const tile = selected;
    if (tile === null || !token) return;
    setSaving(true);
    setError(null);
    // `label` luôn đi cùng: "" nghĩa là XOÁ tên, không phải bỏ qua.
    const body: CreatureEdit = {
      role: draftRole,
      label: draftLabel.trim(),
    };
    void apiFetch<CreaturePublic>(API_ROUTES.adminPetlandCreature(tile), {
      method: "PATCH",
      token,
      body: JSON.stringify(body),
    })
      .then((fresh) => {
        setRows((current) =>
          current === null ? current : current.map((row) => (row.tile === tile ? fresh : row)),
        );
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không lưu được ô này."))
      .finally(() => setSaving(false));
  };

  const promote = () => {
    const tile = selected;
    const code = promoteCode.trim();
    if (tile === null || !code || !token) return;
    setSaving(true);
    setError(null);
    void apiFetch<CreaturePublic>(API_ROUTES.adminPetlandCreaturePromote(tile), {
      method: "POST",
      token,
      body: JSON.stringify({
        code,
        label: draftLabel.trim() || null,
        tier: promoteTier,
        drop_weight: promoteWeight.trim() ? Number(promoteWeight) : null,
      }),
    })
      .then((fresh) => {
        setRows((current) =>
          current === null ? current : current.map((row) => (row.tile === tile ? fresh : row)),
        );
        setSelected(null);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Không chuyển được ô này thành thú nuôi."),
      )
      .finally(() => setSaving(false));
  };

  if (status !== "authenticated" || rows === null) {
    return (
      <Page className="max-w-6xl">
        <p className="text-ink-muted">Đang tải bảng phân vai…</p>
      </Page>
    );
  }

  const petRows = rows.filter((row) => row.species_code !== null);
  const editing = rows.find((row) => row.tile === selected) ?? null;

  return (
    <Page className="max-w-6xl">
      <PageHeader
        eyebrow="Petland"
        title="Phân vai sinh vật"
        description="180 ô của tấm ghép, xếp theo vai. Đổi vai một ô là đổi hành vi của nó ở thế giới chơi — kẻ xâm nhập thành dân làng và ngược lại, không cần deploy."
      />

      {error && (
        <div className="mt-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      {editing && !editing.species_code && (
        <Panel className="mt-4 border-rule-strong p-4">
          <div className="flex flex-wrap items-end gap-4">
            <Creature tile={editing.tile} size={64} />
            <div className="w-40">
              <p className="text-label font-semibold uppercase text-ink-faint">Ô {editing.tile}</p>
              <Input
                className="mt-1"
                value={draftLabel}
                placeholder="Tên (để trống = xoá)"
                onChange={(event) => setDraftLabel(event.target.value)}
              />
            </div>
            <div className="w-44">
              <p className="text-label font-semibold uppercase text-ink-faint">Vai</p>
              <Select
                className="mt-1"
                value={draftRole}
                onChange={(event) => setDraftRole(event.target.value as Role)}
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </Select>
            </div>
            <Button onClick={save} disabled={saving}>
              <Pencil size={14} strokeWidth={2} aria-hidden />
              Lưu
            </Button>
          </div>

          {/* Chuyển thành thú nuôi = TẠO loài tại ô này (`pet_species`), không
              phải một vai thứ tư: membership gacha thuộc bảng loài. Vai cũ được
              giữ làm vai phụ trong hàng creature. */}
          <div className="mt-4 flex flex-wrap items-end gap-4 border-t border-rule pt-4">
            <div className="w-40">
              <p className="text-label font-semibold uppercase text-ink-faint">
                Chuyển thành thú nuôi — mã loài
              </p>
              <Input
                className="mt-1"
                value={promoteCode}
                placeholder="vd: eye-bat"
                onChange={(event) => setPromoteCode(event.target.value)}
              />
            </div>
            <div className="w-44">
              <p className="text-label font-semibold uppercase text-ink-faint">Hạng hiếm</p>
              <Select
                className="mt-1"
                value={promoteTier}
                onChange={(event) => setPromoteTier(event.target.value as (typeof TIERS)[number])}
              >
                {TIERS.map((tier) => (
                  <option key={tier} value={tier}>
                    {tier}
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-32">
              <p className="text-label font-semibold uppercase text-ink-faint">Trọng số rơi</p>
              <Input
                className="mt-1"
                value={promoteWeight}
                placeholder={String(TIER_WEIGHTS[promoteTier])}
                inputMode="numeric"
                onChange={(event) => setPromoteWeight(event.target.value)}
              />
            </div>
            <Button onClick={promote} disabled={saving || !promoteCode.trim()}>
              <PawPrint size={14} strokeWidth={2} aria-hidden />
              Chuyển thành thú nuôi
            </Button>
            <p className="w-full text-small text-ink-muted">
              Loài mới vào gacha ở màn{" "}
              <Link href="/admin/pet" className="underline hover:text-ink">
                /admin/pet
              </Link>{" "}
              — chỉnh trọng số rơi, bật/tắt ở đó.
            </p>
          </div>
        </Panel>
      )}

      <Panel className="mt-4 p-4">
        <h2 className="text-subtitle font-semibold">Thú nuôi ({petRows.length})</h2>
        <p className="mt-1 text-small text-ink-muted">
          Vai của những ô này do bảng loài quyết — sửa loài ở{" "}
          <Link href="/admin/pet" className="underline hover:text-ink">
            /admin/pet
          </Link>
          .
        </p>
        <TileGrid rows={petRows} muted />
      </Panel>

      {ROLE_BOARDS.map((board) => {
        const boardRows = rows.filter(
          (row) => row.role === board.role && row.species_code === null,
        );
        return (
          <Panel key={board.role} className="mt-4 p-4">
            <h2 className="text-subtitle font-semibold">
              {board.title} ({boardRows.length})
            </h2>
            <p className="mt-1 text-small text-ink-muted">{board.hint}</p>
            <TileGrid rows={boardRows} onSelect={select} selected={selected} />
          </Panel>
        );
      })}
    </Page>
  );
}

function TileGrid({
  rows,
  onSelect,
  selected,
  muted,
}: {
  rows: CreaturePublic[];
  onSelect?: (row: CreaturePublic) => void;
  selected?: number | null;
  muted?: boolean;
}) {
  return (
    <div className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(56px,1fr))] gap-1.5">
      {rows.map((row) => (
        <button
          key={row.tile}
          type="button"
          onClick={() => onSelect?.(row)}
          disabled={muted}
          title={row.label ?? undefined}
          className={cx(
            "flex flex-col items-center gap-1 rounded p-1.5 transition-colors",
            !muted && "hover:bg-recess cursor-pointer",
            muted && "cursor-default opacity-70",
            selected === row.tile && "ring-2 ring-action",
          )}
        >
          <Creature tile={row.tile} size={48} />
          <span className="w-full truncate text-label text-ink-faint">
            {row.label ?? row.species_code ?? `#${row.tile}`}
          </span>
        </button>
      ))}
      {rows.length === 0 && <p className="text-small text-ink-muted">Trống.</p>}
    </div>
  );
}
