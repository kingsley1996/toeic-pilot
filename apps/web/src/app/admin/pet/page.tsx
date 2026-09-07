"use client";

import {
  API_ROUTES,
  type EggSettingPublic,
  type EncounterSettingPublic,
  type PetSpeciesPublic,
} from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import { Creature, TIER_LABEL, byCommonness } from "@/components/petland-creature";
import { CREATURE_SHEETS, creatureSheet } from "@/components/petland-sprite";
import { Modal } from "@/components/modal";
import { Alert, Button, Input, Page, PageHeader, Panel, Select, Tag, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Bảng loài thú (ADR-010 §6.3).
 *
 * Mọi con số về loài là một HÀNG, không phải một hằng số trong mã — cùng khuôn
 * `/admin/progression`, và cùng lý do: thêm một loài không nên cần deploy.
 *
 * Danh sách là GRID ô vuông xếp theo hạng (thường trước, hiếm sau) — bảng loài
 * chỉ cần trả lời "có những con gì", còn từng con số nằm trong modal sửa. Không
 * có nút xoá, chỉ có công tắc bật/tắt: xoá một loài mà ai đó đang nuôi để lại
 * `pet_state.species` trỏ vào hư không.
 */

/* Khớp `ck_pet_species_tier` ở database. Thiếu một hạng ở đây thì màn quản trị
   không đặt được hạng đó, dù hàng dữ liệu hoàn toàn hợp lệ — và cách duy nhất
   nhận ra là mở bảng loài lên thấy một ô chọn không có lựa chọn đang dùng. */
const TIERS = ["common", "uncommon", "rare", "epic", "legendary", "god"] as const;

/**
 * Tên hiển thị → mã.
 *
 * `code` là KHOÁ CHÍNH và là thứ `pet_state.species` trỏ tới, nên nó phải là
 * slug `^[a-z0-9_-]+$`. Bắt người vận hành tự nghĩ ra slug ấy là chuyển một luật
 * của database thành việc của họ, và cái giá là một lỗi 422 ở đúng lúc họ vừa gõ
 * xong mọi thứ khác.
 *
 * Bỏ dấu tiếng Việt là bắt buộc chứ không phải tiện nghi: tên loài viết bằng
 * tiếng Việt ("Phượng hoàng"), và `NFD` tách dấu ra thành ký tự tổ hợp riêng để
 * xoá. `đ`/`Đ` không có dạng tổ hợp nên phải thay tay — bỏ sót nó thì "Rồng đỏ"
 * ra `rng-` thay vì `rong-do`.
 */
function slugify(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

export default function PetSpeciesAdminPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [rows, setRows] = useState<PetSpeciesPublic[] | null>(null);
  const [egg, setEgg] = useState<EggSettingPublic | null>(null);
  const [meet, setMeet] = useState<EncounterSettingPublic | null>(null);
  const [editing, setEditing] = useState<PetSpeciesPublic | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<PetSpeciesPublic[]>(API_ROUTES.adminPetSpecies, { token })
      .then(setRows)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load the species table."),
      );
    apiFetch<EggSettingPublic>(API_ROUTES.adminPetEggs, { token })
      .then(setEgg)
      .catch(() => {});
    apiFetch<EncounterSettingPublic>(API_ROUTES.adminPetEncounters, { token })
      .then(setMeet)
      .catch(() => {});
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
      .then((updated) => {
        setRows((current) => (current ?? []).map((row) => (row.code === code ? updated : row)));
        setEditing((current) => (current?.code === code ? updated : current));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Save failed."));
  };

  const patchMeet = (changes: Partial<EncounterSettingPublic>) => {
    if (!token) return;
    setError(null);
    void apiFetch<EncounterSettingPublic>(API_ROUTES.adminPetEncounters, {
      method: "PATCH",
      token,
      body: JSON.stringify(changes),
    })
      .then(setMeet)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Save failed."));
  };

  const patchEgg = (changes: Partial<EggSettingPublic>) => {
    if (!token) return;
    setError(null);
    void apiFetch<EggSettingPublic>(API_ROUTES.adminPetEggs, {
      method: "PATCH",
      token,
      body: JSON.stringify(changes),
    })
      .then(setEgg)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Save failed."));
  };

  if (status !== "authenticated") {
    return (
      <Page>
        <PageHeader eyebrow="Petland" title="Species" />
      </Page>
    );
  }

  const sorted = [...(rows ?? [])].sort(byCommonness);
  const tiers = TIERS.map((tier) => ({
    tier,
    species: sorted.filter((row) => row.tier === tier),
  }));

  return (
    <Page className="max-w-5xl">
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

      {egg && (
        <Panel className="mb-4 flex flex-wrap items-end gap-4 p-4">
          <div>
            <h2 className="text-subtitle">Eggs</h2>
            <p className="mt-1 max-w-md text-small text-ink-muted">
              Paid for in ruby, rolled on the server. The refund must stay below the price —
              otherwise opening duplicates prints ruby out of nothing.
            </p>
          </div>
          <label className="flex items-center gap-1.5 text-small text-ink-muted">
            Price
            <Input
              type="number"
              min={1}
              max={1000}
              defaultValue={egg.ruby_cost}
              aria-label="Egg price in ruby"
              className="w-24"
              onBlur={(event) => {
                const next = Number(event.target.value);
                if (Number.isInteger(next) && next > 0 && next !== egg.ruby_cost) {
                  patchEgg({ ruby_cost: next });
                }
              }}
            />
          </label>
          <label className="flex items-center gap-1.5 text-small text-ink-muted">
            {/* Sau N quả không ra hạng hiếm thì quả sau chắc chắn ra. Ngẫu nhiên
                thuần cho ra những chuỗi xui mà người chơi đọc là "hỏng". */}
            Pity
            <Input
              type="number"
              min={1}
              max={100}
              defaultValue={egg.pity_rolls}
              aria-label="Rolls before a guaranteed rare"
              className="w-24"
              onBlur={(event) => {
                const next = Number(event.target.value);
                if (Number.isInteger(next) && next > 0 && next !== egg.pity_rolls) {
                  patchEgg({ pity_rolls: next });
                }
              }}
            />
          </label>
          <label className="flex items-center gap-1.5 text-small text-ink-muted">
            Duplicate refund
            <Input
              type="number"
              min={0}
              max={999}
              defaultValue={egg.duplicate_refund}
              aria-label="Ruby refunded for a duplicate"
              className="w-24"
              onBlur={(event) => {
                const next = Number(event.target.value);
                if (Number.isInteger(next) && next >= 0 && next !== egg.duplicate_refund) {
                  patchEgg({ duplicate_refund: next });
                }
              }}
            />
          </label>
        </Panel>
      )}

      {meet && (
        <Panel className="mb-4 p-4">
          <h2 className="text-subtitle">Encounters</h2>
          <p className="mt-1 max-w-2xl text-small text-ink-muted">
            Spawned on read, never by a background job — nobody can miss something that was never
            created while they were away. Lifetime must stay below the gap: only one encounter
            exists at a time, so a longer-lived one occupies the slot and later spawns silently
            never happen.
          </p>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {(["npc", "intruder"] as const).map((kind) => (
              <div key={kind} className="rounded border border-rule-strong p-3">
                <h3 className="font-data text-label uppercase text-ink-faint">{kind}</h3>
                <div className="mt-2 flex flex-wrap gap-3">
                  <NumberField
                    label="Gap (s)"
                    value={meet[`${kind}_gap_seconds`]}
                    min={60}
                    max={86400}
                    onCommit={(next) => patchMeet({ [`${kind}_gap_seconds`]: next })}
                  />
                  <NumberField
                    label="Lifetime (s)"
                    value={meet[`${kind}_life_seconds`]}
                    min={30}
                    max={86400}
                    onCommit={(next) => patchMeet({ [`${kind}_life_seconds`]: next })}
                  />
                  <NumberField
                    label="Reward"
                    value={meet[`${kind}_reward`]}
                    min={0}
                    max={500}
                    onCommit={(next) => patchMeet({ [`${kind}_reward`]: next })}
                  />
                  {kind === "intruder" && (
                    <NumberField
                      label="Steps"
                      value={meet.intruder_steps}
                      min={1}
                      max={10}
                      onCommit={(next) => patchMeet({ intruder_steps: next })}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {tiers.map(({ tier, species }) =>
        species.length === 0 ? null : (
          <Panel key={tier} className="mb-4 p-4">
            <h2 className="flex items-center gap-2 text-subtitle font-semibold">
              {TIER_LABEL[tier] ?? tier}
              <span className="font-data text-small font-normal text-ink-faint">
                {species.length}
              </span>
            </h2>
            <div className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(88px,1fr))] gap-2">
              {species.map((row) => (
                <button
                  key={row.code}
                  type="button"
                  onClick={() => setEditing(row)}
                  className={cx(
                    "flex cursor-pointer flex-col items-center gap-1 rounded p-2 transition-colors hover:bg-recess",
                    !row.enabled && "opacity-45",
                  )}
                >
                  <Creature tile={row.tile} sheet={row.sheet} size={48} tier={row.tier} />
                  <span className="w-full truncate text-small font-medium">{row.label}</span>
                  {/* Tắt phải ĐỌC ra được ngay trên lưới, không phải đoán qua
                      độ mờ — độ mờ dễ bị coi là trạng thái hover. */}
                  {!row.enabled && <Tag tone="alert">tắt</Tag>}
                </button>
              ))}
            </div>
          </Panel>
        ),
      )}

      <div className="mt-4">
        <Button onClick={() => setAdding(true)}>Thêm loài</Button>
      </div>

      <p className="mt-4 text-small text-ink-muted">
        {/* Nói ra hệ quả của việc gieo lười, vì nó bất ngờ: bảng rỗng không phải
            một cấu hình, nó là "chưa từng cấu hình". */}
        Disabling keeps a species out of gacha while whoever already owns one keeps it. Deleting
        every row is not a way to empty the table — the defaults seed themselves on the next read.
      </p>

      {adding && (
        <AddSpecies
          onDone={(made) => {
            setRows((current) => (current ? [...current, made] : [made]));
            setAdding(false);
          }}
          onFail={setError}
          onClose={() => setAdding(false)}
        />
      )}
      {editing && <SpeciesModal row={editing} onPatch={patch} onClose={() => setEditing(null)} />}
    </Page>
  );
}

function SpeciesModal({
  row,
  onPatch,
  onClose,
}: {
  row: PetSpeciesPublic;
  onPatch: (code: string, changes: Partial<PetSpeciesPublic>) => void;
  onClose: () => void;
}) {
  return (
    <Modal open onClose={onClose} title={row.label} description={`Mã: ${row.code}`}>
      <div className="flex items-start gap-5">
        <Creature tile={row.tile} sheet={row.sheet} size={96} tier={row.tier} />
        <div className="grid flex-1 gap-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-small text-ink-muted">
            Tên
            <Input
              defaultValue={row.label}
              aria-label={`Label for ${row.code}`}
              className="flex-1"
              onBlur={(event) => {
                const next = event.target.value.trim();
                if (next && next !== row.label) onPatch(row.code, { label: next });
              }}
            />
          </label>
          {/* Tấm đứng TRƯỚC ô, và thứ tự ấy có lý do: `tile` chỉ có nghĩa khi
              biết tấm, nên đọc theo thứ tự này thì hai ô nhập tự giải thích
              nhau. Đổi tấm mà ô hiện tại vượt trần tấm mới thì máy chủ trả 422
              nói rõ tấm nào bao nhiêu ô. */}
          <label className="flex items-center gap-2 text-small text-ink-muted">
            Tấm
            <Select
              value={row.sheet}
              aria-label={`Sheet for ${row.code}`}
              className="flex-1"
              onChange={(event) =>
                onPatch(row.code, { sheet: event.target.value as PetSpeciesPublic["sheet"] })
              }
            >
              {Object.keys(CREATURE_SHEETS).map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex items-center gap-2 text-small text-ink-muted">
            Hạng
            <Select
              value={row.tier}
              aria-label={`Tier for ${row.code}`}
              className="flex-1"
              onChange={(event) =>
                onPatch(row.code, { tier: event.target.value as PetSpeciesPublic["tier"] })
              }
            >
              {TIERS.map((tier) => (
                <option key={tier} value={tier}>
                  {tier}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex items-center gap-2 text-small text-ink-muted">
            {/* Trọng số, không phải phần trăm. Phần trăm phải cộng lại đúng
                100, nên tắt hay thêm một loài biến cả bảng thành sai và ai đó
                phải chỉnh tay từng hàng. Tỉ lệ hiện cho người chơi được chuẩn
                hoá từ tổng của các loài đang bật. */}
            Trọng số rơi
            <Input
              type="number"
              min={0}
              max={1000}
              defaultValue={row.drop_weight}
              aria-label={`Drop weight for ${row.code}`}
              className="w-20"
              onBlur={(event) => {
                const next = Number(event.target.value);
                if (Number.isInteger(next) && next >= 0 && next !== row.drop_weight) {
                  onPatch(row.code, { drop_weight: next });
                }
              }}
            />
          </label>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between gap-2 border-t border-rule pt-4">
        {/* Công tắc bật/tắt nằm TRONG modal: lưới không cần một nút hành động
            trên mỗi ô, và tắt là hành động đáng một lượt xác nhận bằng mắt. */}
        <Button
          variant={row.enabled ? "destructive" : "primary"}
          onClick={() => onPatch(row.code, { enabled: !row.enabled })}
        >
          {row.enabled ? "Tắt khỏi gacha" : "Bật lại"}
        </Button>
        <Button variant="secondary" onClick={onClose}>
          Đóng
        </Button>
      </div>
      {!row.enabled && (
        <p className="mt-3 text-small text-ink-muted">
          Loài tắt biến khỏi gacha và khỏi bộ sưu tập của người học — ai đang nuôi vẫn giữ con thú,
          nhưng nó không hiện trong tủ sưu tập nữa.
        </p>
      )}
      <div className="mt-4 border-t border-rule pt-4">
        <TilePicker
          sheet={row.sheet}
          tile={row.tile}
          onPick={(next) => next !== row.tile && onPatch(row.code, { tile: next })}
        />
      </div>
    </Modal>
  );
}

/**
 * Một ô số ghi lại khi rời ô, không ghi theo từng phím.
 *
 * `key={value}` là phần load-bearing: `defaultValue` chỉ đọc ở lần dựng đầu, nên
 * khi máy chủ trả về một giá trị khác cái vừa gõ — nó từ chối vì "life >= gap" —
 * ô số sẽ đứng yên ở con số sai và màn hình nói dối về trạng thái đã lưu.
 */
function NumberField({
  label,
  value,
  min,
  max,
  onCommit,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onCommit: (next: number) => void;
}) {
  return (
    <label className="flex items-center gap-1.5 text-small text-ink-muted">
      {label}
      <Input
        key={value}
        type="number"
        min={min}
        max={max}
        defaultValue={value}
        aria-label={label}
        className="w-24"
        onBlur={(event) => {
          const next = Number(event.target.value);
          if (Number.isInteger(next) && next >= min && next <= max && next !== value) {
            onCommit(next);
          }
        }}
      />
    </label>
  );
}

/**
 * Thêm một loài, và đó là **cửa duy nhất** để dùng một tấm ghép mới.
 *
 * Trước màn này, đường tạo loài duy nhất trong giao diện là nút "promote" ở
 * `/admin/petland/creatures` — mà màn ấy là bảng PHÂN VAI của `creatures.png`,
 * đánh số 0–179 và không có khái niệm tấm. Nên thêm một tấm mới xong thì ảnh
 * nằm trong `public/pet/` mà không cách nào trỏ tới: không lỗi nào, chỉ là
 * không có gì xuất hiện.
 *
 * Ô xem trước cập nhật theo tấm và số ô đang gõ, vì đó là phép kiểm duy nhất
 * đáng tin ở đây: một chỉ số hợp lệ nhưng sai vẫn vẽ ra một con vật, chỉ là con
 * khác. Ô trống nghĩa là gõ ra ngoài vùng có vẽ.
 */
function AddSpecies({
  onDone,
  onFail,
  onClose,
}: {
  onDone: (made: PetSpeciesPublic) => void;
  onFail: (message: string) => void;
  onClose: () => void;
}) {
  const { token } = useRequireSession({ canEdit: true });
  const [sheet, setSheet] = useState<PetSpeciesPublic["sheet"]>("myth");
  const [tile, setTile] = useState(0);
  const [code, setCode] = useState("");
  // Mã tự chạy theo tên cho tới khi người dùng tự sửa mã. Sau đó thì thôi —
  // gõ lại tên không được xoá mất một mã người ta đã cố ý đặt.
  const [codeTouched, setCodeTouched] = useState(false);
  const [label, setLabel] = useState("");
  const [tier, setTier] = useState<PetSpeciesPublic["tier"]>("legendary");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!token || busy) return;
    setBusy(true);
    try {
      const made = await apiFetch<PetSpeciesPublic>(API_ROUTES.adminPetSpecies, {
        method: "POST",
        token,
        body: JSON.stringify({ code: code.trim(), label: label.trim(), sheet, tile, tier }),
      });
      onDone(made);
    } catch (bad) {
      onFail(bad instanceof ApiError ? bad.message : "Không thêm được loài.");
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Thêm loài" description="Chọn tấm rồi chọn ô.">
      <div className="flex items-start gap-5">
        <Creature tile={tile} sheet={sheet} size={96} tier={tier} />
        <div className="grid flex-1 gap-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-small text-ink-muted">
            Tấm
            <Select
              value={sheet}
              aria-label="Sheet"
              className="flex-1"
              onChange={(event) => setSheet(event.target.value as PetSpeciesPublic["sheet"])}
            >
              {Object.keys(CREATURE_SHEETS).map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </Select>
          </label>
          {/* TÊN trước, MÃ sau: mã suy ra từ tên, nên đọc ngược lại thì ô thứ
              hai trông như một thứ phải tự nghĩ. */}
          <label className="flex items-center gap-2 text-small text-ink-muted">
            Tên
            <Input
              value={label}
              aria-label="Label"
              className="flex-1"
              placeholder="Phượng hoàng"
              onChange={(event) => {
                setLabel(event.target.value);
                if (!codeTouched) setCode(slugify(event.target.value));
              }}
            />
          </label>
          <label className="flex items-center gap-2 text-small text-ink-muted">
            Mã
            <Input
              value={code}
              aria-label="Code"
              className="flex-1"
              placeholder="phuong-hoang"
              onChange={(event) => {
                setCodeTouched(true);
                // Chuẩn hoá NGAY khi gõ, không đợi máy chủ từ chối: chữ hoa và
                // dấu cách là hai thứ người ta gõ vào đây nhiều nhất.
                setCode(slugify(event.target.value));
              }}
            />
          </label>
          <label className="flex items-center gap-2 text-small text-ink-muted">
            Hạng
            <Select
              value={tier}
              aria-label="Tier"
              className="flex-1"
              onChange={(event) => setTier(event.target.value as PetSpeciesPublic["tier"])}
            >
              {TIERS.map((one) => (
                <option key={one} value={one}>
                  {one}
                </option>
              ))}
            </Select>
          </label>
        </div>
      </div>

      <div className="mt-4 border-t border-rule pt-4">
        <TilePicker sheet={sheet} tile={tile} onPick={setTile} />
      </div>

      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Huỷ
        </Button>
        <Button disabled={busy || !code.trim() || !label.trim()} onClick={() => void save()}>
          {busy ? "Đang thêm…" : "Thêm"}
        </Button>
      </div>
    </Modal>
  );
}

/**
 * Chọn ô bằng MẮT, cho cả màn thêm lẫn màn sửa.
 *
 * Trước đây chỗ này là một ô nhập số. Nó đúng về mặt dữ liệu và vô dụng về mặt
 * sử dụng: `tile` là chỉ số trong tấm ghép, nên muốn biết ô 13 là con gì thì
 * phải gõ 13 rồi nhìn ô xem trước, rồi gõ 14, rồi 15. Với `creatures.png` 180 ô
 * thì đó không phải một thao tác, đó là một buổi chiều.
 *
 * Tệ hơn: một chỉ số sai vẫn hợp lệ và vẫn vẽ ra một con vật, chỉ là con khác.
 * Không có gì báo. Bấm thẳng vào con mình muốn thì lỗi ấy không tồn tại.
 */
function TilePicker({
  sheet,
  tile,
  onPick,
}: {
  sheet: PetSpeciesPublic["sheet"];
  tile: number;
  onPick: (next: number) => void;
}) {
  const art = creatureSheet(sheet);
  return (
    <div>
      <p className="text-label font-semibold uppercase tracking-wide text-ink-faint">
        Chọn ô — tấm {sheet}, {art.tiles} ô
      </p>
      {/* Cao tối đa rồi cuộn: `creatures.png` có 180 ô, và một lưới 180 ô đẩy
          hai nút ở chân hộp thoại ra ngoài màn hình. */}
      <div className="mt-2 max-h-64 overflow-y-auto rounded border border-rule p-1">
        <div className="flex flex-wrap gap-1">
          {Array.from({ length: art.tiles }, (_, index) => (
            <button
              key={index}
              type="button"
              title={`Ô ${index}`}
              aria-label={`Ô ${index}`}
              aria-pressed={index === tile}
              onClick={() => onPick(index)}
              className={cx(
                "cursor-pointer rounded border p-0.5 transition-colors hover:bg-recess",
                index === tile ? "border-rule-strong bg-recess" : "border-transparent",
              )}
            >
              <Creature tile={index} sheet={sheet} size={32} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
