"use client";

import { API_ROUTES, type PetPublic } from "@toeic-pilot/shared";
import { Pencil, Share2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Creature, TIER_LABEL, tierGlow } from "@/components/petland/petland-creature";
import { creatureSheet } from "@/components/petland/petland-sprite";
import { CONDITION_LABEL, conditionOf } from "@/components/petland/petland-pet";
import { Button } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { notifyPet } from "@/lib/pet-notice";
import { publishPet } from "@/lib/pet-state";

/**
 * Thẻ hồ sơ con thú: tên riêng, cân nặng, tuổi, level — và nút khoe.
 *
 * Nằm ở cột cạnh bản đồ như trứng/bộ sưu tập/nhiệm vụ, không phải một trang
 * riêng: profile là thứ ngắm trong lúc chơi với con thú, và một cú chuyển trang
 * cho việc đó thì ngắm xong phải tìm đường về.
 */

/** Gam thành chữ: dưới 10 kg in NGUYÊN gam, trên mới đổi sang kg.
 *
 * Cân động từng bữa ăn chỉ nhích vài chục gam — "2,5 kg" làm tròn một chữ số
 * thập phân sẽ đứng yên sau cú cho ăn, đọc ra là nút hỏng. "2525 g" thì nhích
 * thật. Ngưỡng 10 kg để số gam không dài quá 4 chữ số.
 *
 * Dấu phẩy theo thói quen Việt, và số nguyên không thêm ",0". `null` (loài
 * admin tự thêm mà chưa điền) thì là "?", cùng quy ước đã ghi ở API. */
export function formatWeight(grams: number | null | undefined): string {
  if (grams === null || grams === undefined) return "?";
  if (grams < 10_000) return `${grams} g`;
  const kg = grams / 1000;
  return `${Number.isInteger(kg) ? String(kg) : kg.toFixed(1).replace(".", ",")} kg`;
}

/** Tuổi tính từ mốc nở. Dưới một ngày là "hôm nay", không phải "0 ngày" —
 *  không ai gọi con vật mới nở là 0 ngày tuổi. */
export function petAge(hatchedAt: string, now: number): string {
  const days = Math.max(0, Math.floor((now - new Date(hatchedAt).getTime()) / 86_400_000));
  if (days <= 0) return "Nở hôm nay";
  return `${days} ngày tuổi`;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("tải ảnh sprite"));
    img.src = url;
  });
}

/**
 * Vẽ thẻ khoe ra PNG (720×960) để lưu hoặc share file.
 *
 * Vẽ tay trên canvas chứ không chụp DOM: không thêm dependency, và sprite
 * pixel vốn đã là ảnh — `drawImage` với smoothing tắt cho ra đúng con thú
 * đang thấy trên màn hình, phóng nguyên hệ số. Chữ dùng phông hệ thống vì
 * canvas không đọc được phông web đã nạp cho CSS.
 */
async function paintCard(pet: PetPublic, now: number): Promise<Blob> {
  const W = 720;
  const H = 960;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas");

  const hex = `#${tierGlow(pet.tier).color.toString(16).padStart(6, "0")}`;
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, "#232833");
  bg.addColorStop(1, "#12151b");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // Vệt sáng chéo như thẻ DOM.
  const shine = ctx.createLinearGradient(0, 0, W, H);
  shine.addColorStop(0.3, "rgba(255,255,255,0)");
  shine.addColorStop(0.45, "rgba(255,255,255,0.10)");
  shine.addColorStop(0.6, "rgba(255,255,255,0)");
  ctx.fillStyle = shine;
  ctx.fillRect(0, 0, W, H);

  // Viền màu hạng.
  ctx.strokeStyle = hex;
  ctx.lineWidth = 10;
  ctx.strokeRect(10, 10, W - 20, H - 20);

  // Sprite: cắt đúng ô rồi phóng nguyên hệ số, smoothing tắt để pixel không nhoè.
  const sheet = creatureSheet(pet.sheet);
  const img = await loadImage(sheet.url);
  const cell = img.naturalWidth / sheet.cols;
  const sx = (pet.tile % sheet.cols) * cell;
  const sy = Math.floor(pet.tile / sheet.cols) * cell;
  const size = 288;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(img, sx, sy, cell, cell, (W - size) / 2, 190, size, size);

  const name = pet.nickname ?? pet.label;
  ctx.textAlign = "center";
  ctx.fillStyle = "#ffffff";
  ctx.font = "700 60px system-ui, sans-serif";
  ctx.fillText(name, W / 2, 610);
  ctx.fillStyle = "#a7b0bd";
  ctx.font = "400 30px system-ui, sans-serif";
  ctx.fillText(`${pet.label} · ${TIER_LABEL[pet.tier] ?? pet.tier} · Lv ${pet.level}`, W / 2, 660);
  ctx.fillStyle = "#ffffff";
  ctx.fillText(
    `${formatWeight(pet.weight_grams)} · ${petAge(pet.hatched_at, now)} · ${CONDITION_LABEL[conditionOf(pet.needs)]}`,
    W / 2,
    720,
  );
  ctx.fillStyle = "#6b7482";
  ctx.font = "400 26px system-ui, sans-serif";
  ctx.fillText("TOEIC Pilot — học cùng thú cưng", W / 2, 890);

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("xuất ảnh");
  return blob;
}

export function PetProfileScreen({
  token,
  pet,
  onChanged,
  onClose,
}: {
  token: string;
  pet: PetPublic;
  /** Con thú mới sau khi đổi tên — bảng và sidebar cùng nhận, cùng luật `act`. */
  onChanged: (next: PetPublic) => void;
  onClose: () => void;
}) {
  // Tuổi chốt lúc mở thẻ, không nhích theo từng giây: một con số đứng yên
  // trong lúc ngắm, và `Date.now()` chỉ sống trong khởi tạo state (luật purity).
  const [openedAt] = useState(() => Date.now());
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(pet.nickname ?? "");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  /* Xem trước thẻ khoe trước khi share: người ta muốn biết thứ bay lên mạng
     xã hội trông thế nào, và một nút share bấm là đi ngay thì không cho họ cơ
     hội đó. Popup nằm gọn trong cột profile, không đè cả bảng. */
  const [preview, setPreview] = useState(false);
  /* Đang vẽ/tải ảnh: ảnh vẽ bất đồng bộ (chờ sprite), bấm dồn hai lần là hai
     lần tải — khoá nút trong lúc làm. */
  const [shotBusy, setShotBusy] = useState(false);

  async function saveName() {
    if (busy) return;
    setBusy(true);
    setFailed(null);
    try {
      const updated = await apiFetch<PetPublic>(API_ROUTES.petNickname, {
        method: "PATCH",
        token,
        body: JSON.stringify({ nickname: draft }),
      });
      onChanged(updated);
      // Sidebar giữ một bản riêng qua bus, không đọc lại — không đẩy qua đây
      // thì thẻ ngoài kia vẫn gọi tên cũ.
      publishPet(updated);
      setEditing(false);
    } catch (err) {
      setFailed(err instanceof ApiError ? err.message : "Chưa đổi được tên.");
    } finally {
      setBusy(false);
    }
  }

  /* Nút Chia sẻ TẠM ẨN (đường share file ảnh chưa đúng trên một số máy):
     `share()` + `shareLines()` bên dưới đã dọn để eslint khỏi warning — cần thì
     mở lại từ git, logic share file→chữ→clipboard vẫn còn nguyên trong lịch sử. */

  async function saveImage() {
    if (shotBusy) return;
    setShotBusy(true);
    try {
      const blob = await paintCard(pet, Date.now());
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `thu-cung-${pet.species}.png`;
      link.click();
      URL.revokeObjectURL(url);
      notifyPet({ tone: "ok", title: "Đã lưu ảnh thẻ — đăng TikTok/Facebook tuỳ thích." });
    } catch {
      notifyPet({ tone: "warn", title: "Chưa lưu được ảnh, thử lại nhé." });
    } finally {
      setShotBusy(false);
    }
  }

  return (
    <div className="w-full shrink-0 overflow-y-auto border-t border-rule p-3 sm:h-[var(--pet-map-h)] sm:w-[var(--pet-egg-w)] sm:border-l sm:border-t-0">
      {" "}
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-small font-semibold">Hồ sơ thú cưng</h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Đóng hồ sơ"
          className="grid h-6 w-6 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink"
        >
          <X size={14} strokeWidth={2} aria-hidden />
        </button>
      </div>
      {/* Chân dung lớn, đeo khung theo hạng — cùng component màn trứng dùng, nên
          con rồng ở đây và con rồng trong tủ không bao giờ vẽ khác nhau. */}
      <div className="mt-3 flex justify-center">
        <Creature tile={pet.tile} sheet={pet.sheet} tier={pet.tier} size={72} />
      </div>
      {/* Tên riêng sửa ngay tại chỗ: đây là con CỦA người ta, và bắt họ sang
          màn khác để đặt tên cho nó là bắt họ đi xa khỏi nó. */}
      <div className="mt-2 text-center">
        {editing ? (
          <div className="flex items-center justify-center gap-2">
            <input
              value={draft}
              autoFocus
              maxLength={40}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void saveName();
                if (event.key === "Escape") setEditing(false);
              }}
              placeholder={pet.label}
              aria-label="Tên riêng của thú cưng"
              className="w-36 rounded border border-rule-strong bg-surface px-2 py-1 text-center text-body font-semibold text-ink outline-none focus-visible:border-accent"
            />
            <Button size="sm" disabled={busy} onClick={() => void saveName()}>
              Lưu
            </Button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => {
              setDraft(pet.nickname ?? "");
              setEditing(true);
            }}
            title="Đặt tên riêng"
            className="group inline-flex items-center gap-1.5 text-title font-bold text-ink hover:text-action-ink"
          >
            {pet.nickname ?? pet.label}
            <Pencil
              size={13}
              strokeWidth={2}
              aria-hidden
              className="text-ink-faint opacity-0 transition-opacity group-hover:opacity-100"
            />
          </button>
        )}
        <p className="mt-0.5 text-small text-ink-muted">
          {pet.label} · {TIER_LABEL[pet.tier] ?? pet.tier}
        </p>
        {failed && <p className="mt-1 text-small text-warn">{failed}</p>}
      </div>
      {/* Level dùng đúng luật thanh ở tiêu đề bảng: kịch bảng thì mất thanh. */}
      <div className="mt-3 flex items-center gap-2">
        <span className="font-data text-small font-bold tabular-nums">Lv {pet.level}</span>
        {pet.xp_for_next > 0 && (
          <span
            role="progressbar"
            aria-valuenow={pet.xp_into_level}
            aria-valuemin={0}
            aria-valuemax={pet.xp_for_next}
            aria-label="Tiến độ level của thú cưng"
            className="block h-1.5 flex-1 overflow-hidden rounded bg-recess"
          >
            <span
              className="block h-full bg-action"
              style={{ width: `${Math.round((pet.xp_into_level / pet.xp_for_next) * 100)}%` }}
            />
          </span>
        )}
      </div>
      <dl className="mt-3 space-y-1.5 text-small">
        <div className="flex items-baseline justify-between gap-2">
          <dt className="text-ink-muted">Cân nặng</dt>
          <dd className="font-data font-semibold tabular-nums">{formatWeight(pet.weight_grams)}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <dt className="text-ink-muted">Tuổi</dt>
          <dd className="font-semibold">{petAge(pet.hatched_at, openedAt)}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <dt className="text-ink-muted">Tình trạng</dt>
          <dd className="font-semibold">{CONDITION_LABEL[conditionOf(pet.needs)]}</dd>
        </div>
      </dl>
      <Button
        size="sm"
        variant="secondary"
        className="mt-4 w-full"
        onClick={() => setPreview(true)}
      >
        <Share2 size={14} strokeWidth={2} aria-hidden />
        Khoe lên mạng xã hội
      </Button>
      {preview && (
        <SharePreview
          pet={pet}
          openedAt={openedAt}
          shotBusy={shotBusy}
          onSave={() => void saveImage()}
          onClose={() => setPreview(false)}
        />
      )}
    </div>
  );
}

/* Góc nghiêng tối đa của thẻ (độ). Đủ để thấy khối 3D, chưa đủ để chữ khó đọc
   khi nghiêng — nghiêng sâu hơn là khoe hiệu ứng thay vì khoe con thú. */
const TILT_MAX_X = 10;
const TILT_MAX_Y = 14;

/**
 * Popup xem trước thẻ khoe: overlay RIÊNG ngoài bảng, giữa màn hình.
 *
 * Cố ý không nằm trong cột profile: thẻ khoe là thứ đáng được ngắm to, và một
 * popup 288px kẹp trong cột thì chân dung, chữ và nút cùng chen nhau. Overlay
 * `fixed` nên nó cũng không bị bảng nổi (kéo đi đâu cũng được) kéo theo.
 *
 * Thẻ nghiêng 3D theo chuột + viền gradient màu hạng (lấy từ `tierGlow`, cùng
 * màu vòng sáng dưới chân con thú trên bản đồ). `prefers-reduced-motion` thì
 * đứng yên — hiệu ứng là trang trí, không phải thông tin.
 */
function SharePreview({
  pet,
  openedAt,
  shotBusy,
  onSave,
  onClose,
}: {
  pet: PetPublic;
  openedAt: number;
  shotBusy: boolean;
  onSave: () => void;
  onClose: () => void;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  /* Đứng yên khi người dùng xin giảm chuyển động. Đọc trong khởi tạo state
     (popup chỉ mở sau một cú bấm nên `window` chắc chắn có) chứ không trong
     effect — luật `set-state-in-effect` cấm đúng cái đó. */
  const [still] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  const hex = `#${tierGlow(pet.tier).color.toString(16).padStart(6, "0")}`;

  function tilt(event: React.PointerEvent) {
    if (still) return;
    const el = cardRef.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    const px = (event.clientX - box.left) / box.width - 0.5;
    const py = (event.clientY - box.top) / box.height - 0.5;
    el.style.transform =
      `perspective(900px) rotateX(${(-py * TILT_MAX_X).toFixed(2)}deg) ` +
      `rotateY(${(px * TILT_MAX_Y).toFixed(2)}deg)`;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Xem trước thẻ khoe thú cưng"
      className="fixed inset-0 z-[70] grid place-items-center overflow-y-auto bg-black/60 p-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {/* Viền gradient: nền thang màu hạng, thẻ thật nằm trong với một lớp lót.
          `p-[3px]` là độ dày viền — không dùng `border-image` vì nó không theo
          `border-radius` mà cắt góc vuông. */}
      {/* Vào nhẹ bằng animation ở LỚP NGOÀI, nghiêng 3D ở lớp trong: keyframe
          `settle` fill `both` nên `transform: none` của nó còn hiệu lực mãi sau
          khi animation xong — để chung một node thì nó đè chết transform inline
          của tilt, và thẻ không bao giờ nghiêng. */}
      {/* Viền gradient đặc toàn vòng, KHÔNG khoảng trong suốt: bản trước để
          giữa thang trong suốt nên hai góc trên-phải/dưới-trái (điểm giữa của
          thang chéo) nhìn như bị phai. Hai đầu chỉ khác alpha nhẹ để còn hướng
          sáng, không đầu nào mờ hẳn. */}
      <div className="animate-settle w-full max-w-xs">
        {/* Khung tối bao ngoài viền gradient: màu hạng nhạt (thường, thần)
            chìm hẳn trên nền sáng ở light mode — một vòng tối ôm ngoài thì viền
            nổi ở cả hai theme. Màu cứng, không token. */}
        <div className="rounded bg-[#0e1116] p-[2px]">
          <div
            ref={cardRef}
            onPointerMove={tilt}
            onPointerLeave={() => {
              if (cardRef.current) cardRef.current.style.transform = "";
            }}
            style={{
              background: `linear-gradient(135deg, ${hex} 0%, ${hex}99 100%)`,
            }}
            className="rounded-[2px] p-[3px] transition-transform duration-150 ease-out motion-reduce:transform-none"
          >
            <div className="relative overflow-hidden rounded-[2px] bg-[#171b23] p-5 text-center">
              {/* MÀU CỐ ĐỊNH, không ăn theo dark/light mode: thẻ khoe phải trông
                giống hệt nhau dù máy đang theme nào — cũng để khớp file PNG vẽ
                bằng canvas. Token `text-ink`/`bg-panel` ở đây là hỏng im lặng
                theo theme. */}
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0"
                style={{
                  background:
                    "linear-gradient(115deg, transparent 30%, rgba(255,255,255,0.12) 45%, transparent 60%)",
                }}
              />
              <p className="relative text-label font-semibold uppercase tracking-widest text-[#7d8694]">
                Thú cưng của tôi
              </p>
              <div className="relative mt-3 flex justify-center">
                <Creature tile={pet.tile} sheet={pet.sheet} tier={pet.tier} size={104} />
              </div>
              {/* Tên màu hạng bằng mã hex (cùng `tierGlow` vòng sáng bản đồ), không
                qua `TIER_TONE`: token chữ đổi theo theme, hex thì không. */}
              <p className="relative mt-2 text-title font-bold" style={{ color: hex }}>
                {pet.nickname ?? pet.label}
              </p>
              <p className="relative mt-0.5 text-small text-[#a7b0bd]">
                {pet.label} · {TIER_LABEL[pet.tier] ?? pet.tier} · Lv {pet.level}
              </p>
              <div className="relative mx-auto mt-3 grid max-w-[13rem] grid-cols-3 gap-2 text-center text-[#f2f4f8]">
                <div>
                  <p className="font-data text-small font-bold tabular-nums">
                    {formatWeight(pet.weight_grams)}
                  </p>
                  <p className="text-label text-[#7d8694]">Cân nặng</p>
                </div>
                <div>
                  <p className="text-small font-bold">{petAge(pet.hatched_at, openedAt)}</p>
                  <p className="text-label text-[#7d8694]">Tuổi</p>
                </div>
                <div>
                  <p className="text-small font-bold">{CONDITION_LABEL[conditionOf(pet.needs)]}</p>
                  <p className="text-label text-[#7d8694]">Tình trạng</p>
                </div>
              </div>
              <p className="relative mt-3 text-label text-[#7d8694]">
                TOEIC Pilot — học cùng thú cưng
              </p>
              <div className="relative mt-3 flex gap-2">
                {/* Nút Chia sẻ TẠM ẨN (đường share file ảnh chưa đúng trên một số
                  máy) — logic share còn nguyên trong git, bật lại khi sửa xong. */}
                <Button
                  size="sm"
                  variant="secondary"
                  className="flex-1"
                  disabled={shotBusy}
                  onClick={onSave}
                >
                  {shotBusy ? "Đang vẽ…" : "Lưu ảnh"}
                </Button>
                <Button size="sm" variant="secondary" className="flex-1" onClick={onClose}>
                  Đóng
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
