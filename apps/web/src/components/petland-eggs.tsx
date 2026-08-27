"use client";

import { API_ROUTES, type EggPublic, type EggResult } from "@toeic-pilot/shared";
import { Gem, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Creature, TIER_LABEL, TIER_TONE } from "@/components/petland-creature";
import { PixelIcon } from "@/components/pixel-icon";
import { Button, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useToast } from "@/lib/toast";

/**
 * Màn mở trứng (ADR-010 §6).
 *
 * Nằm ở tệp riêng chứ không trong `petland-ui.tsx`, và lý do là luật tầng:
 * `petland-ui` phải sống sót qua việc đổi mascot và đổi bối cảnh, nên nó không
 * được biết ô nào trong tấm ghép vẽ ra con gì — mà màn này thì phải vẽ đúng con
 * vừa nở. `scripts/check-petland-layers.mjs` giữ ranh giới đó.
 *
 * Ba thứ ở đây là quyết định, không phải trang trí:
 *
 *   · **Tỉ lệ in ra màn hình, luôn luôn** (§6.4). Nhiều nơi đã luật hoá việc
 *     này, và kể cả không có luật thì đây là sản phẩm học cho học sinh. Con số
 *     tính ở máy chủ từ chính bảng trọng số mà phép quay dùng, nên màn hình
 *     không thể nói khác máy.
 *   · **Quay ở máy chủ.** Ở đây không có `Math.random()` nào cả — chỉ có một
 *     `POST` và một kết quả để diễn hoạt.
 *   · **Bộ đếm an ủi hiện thành một câu**, không phải một con số trần. "Còn 3
 *     quả nữa là chắc chắn ra hạng hiếm" nói cho người ta biết nên làm gì tiếp;
 *     "7/10" thì không.
 */

/**
 * Bề rộng cột trứng, tính bằng pixel.
 *
 * Xuất ra vì `petland.tsx` phải cộng đúng con số này vào chặn trên chiều rộng
 * của bảng — bảng dùng `w-fit`, nên nếu chặn trên không biết về cột này thì cột
 * bị ép hẹp lại và chữ tràn ra ngoài viền.
 */
export const EGG_PANEL_W = 288;

/** Quả trứng rung ít nhất chừng này trước khi lộ ra con gì. */
const HATCH_MS = 900;

/**
 * Câu chúc mừng theo hạng, cho con CHƯA TỪNG sở hữu.
 *
 * Càng hiếm càng nói to hơn: một dòng "Con mới!" giống hệt nhau cho cả con vịt
 * lẫn con rồng là cách chắc chắn nhất để lần đầu ra huyền thoại trôi qua như một
 * lần mở trứng bình thường — mà đúng khoảnh khắc ấy mới là thứ cả hệ gacha tồn
 * tại để tạo ra.
 */
const TIER_CHEER: Record<string, string> = {
  common: "Con mới!",
  uncommon: "Con mới!",
  rare: "Hiếm đấy!",
  epic: "Cực hiếm!",
  legendary: "HUYỀN THOẠI!",
};

export function EggScreen({ token, onClose }: { token: string; onClose: () => void }) {
  const [egg, setEgg] = useState<EggPublic | null>(null);
  const [result, setResult] = useState<EggResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [hatching, setHatching] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [showOdds, setShowOdds] = useState(false);
  const { show } = useToast();

  useEffect(() => {
    let alive = true;
    apiFetch<EggPublic>(API_ROUTES.petEggs, { token })
      .then((data) => {
        if (alive) setEgg(data);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token]);

  async function open() {
    if (busy) return;
    setBusy(true);
    setRefused(null);
    setResult(null);
    setHatching(true);
    const started = performance.now();
    try {
      const hatched = await apiFetch<EggResult>(API_ROUTES.petEggOpen, { method: "POST", token });
      // Chờ cho ĐỦ nhịp rung, kể cả khi máy chủ trả lời trong 20ms.
      //
      // Không có nó thì trên máy nội bộ quả trứng chớp một cái rồi biến mất, và
      // thứ duy nhất người ta nhớ ở gacha — đúng khoảnh khắc chưa biết mình được
      // gì — bị nuốt mất. Chậm THÊM chứ không bao giờ chậm hơn: mạng chậm hơn
      // nhịp rung thì không đợi thêm giây nào.
      const owed = HATCH_MS - (performance.now() - started);
      if (owed > 0) await new Promise((done) => window.setTimeout(done, owed));
      setResult(hatched);

      /*
       * Chúc mừng CHỈ khi là con chưa từng có.
       *
       * Trùng thì thẻ kết quả đã nói ra và đã hoàn ruby rồi; một thông báo nữa
       * để báo tin không vui là tiếng ồn, và tiếng ồn làm mất giá đúng những lần
       * đáng ăn mừng.
       *
       * Đây là một trong số ít chỗ được phép XIN TIẾNG: nó bắn ra ngay sau một
       * cú bấm, nên trình duyệt cho phát — khác hẳn thông báo huy hiệu hay việc
       * hôm nay, vốn bắn ra từ lần `fetch` lúc mở trang và sẽ im lặng dù có xin.
       */
      if (!hatched.duplicate) {
        show({
          tone: "ok",
          title: TIER_CHEER[hatched.species.tier] ?? "Con mới!",
          description: `${hatched.species.label} — ${
            TIER_LABEL[hatched.species.tier] ?? hatched.species.tier
          }, tỉ lệ ${hatched.species.percent}%`,
          sound: "complete",
          // Một con chỉ "mới" được đúng một lần, nên khoá theo mã loài không bao
          // giờ nuốt mất một tin thật — nó chỉ chặn thẻ nhân đôi khi StrictMode
          // của bản dev chạy đường này hai lần.
          dedupeKey: `egg-new-${hatched.species.code}`,
        });
      }
      // Đọc lại cả màn hình từ máy chủ thay vì tự sửa state: số dư, bộ sưu tập
      // và bộ đếm an ủi đều vừa đổi, và ba phép cộng ở client là ba chỗ để lệch.
      setEgg(await apiFetch<EggPublic>(API_ROUTES.petEggs, { token }));
    } catch (err) {
      // Lời từ chối của máy chủ đã nói ra con số ("Cần 25 ruby, hiện có 8"), nên
      // in nguyên văn thay vì tự dựng lại một câu có thể sai.
      setRefused(err instanceof ApiError ? err.message : "Chưa mở được trứng.");
    } finally {
      setHatching(false);
      setBusy(false);
    }
  }

  if (!egg) return null;

  const left = Math.max(0, egg.pity_rolls - egg.rolls_since_rare);

  return (
    /*
     * Một CỘT bên phải bản đồ, không phải một khối nằm dưới.
     *
     * Nằm dưới thì nó đẩy chiều cao cả bảng — mà bảng này nổi cố định, nên phần
     * lòi ra khỏi màn hình không cuộn theo trang được: hàng nút cho ăn/chọc/đi
     * dạo đơn giản là không tới được nữa. Đứng cạnh thì chiều cao do bản đồ
     * quyết định và phần thừa cuộn bên trong chính cột này.
     *
     * Chiều rộng và chiều cao đọc từ hai biến CSS mà `petland.tsx` đặt
     * (`--pet-egg-w`, `--pet-map-h`), KHÔNG đặt bằng `style` ở đây: `style` nội
     * tuyến thắng mọi lớp, nên nó sẽ chặn luôn cả nhánh "dưới `sm` thì rộng hết
     * bảng". Bề rộng gốc là `EGG_PANEL_W` xuất ra dưới đây, vì bảng còn phải
     * cộng đúng con số ấy vào chặn trên chiều rộng của nó.
     *
     * Dưới `sm` thì quay về nằm dưới: 448 + 288 là 736px, rộng hơn cả màn hình
     * điện thoại, và bảng thú cưng ở đó vốn đã bị thu 0,7 lần.
     */
    <div className="max-h-[35vh] w-full shrink-0 overflow-y-auto border-t border-rule p-3 sm:h-[var(--pet-map-h)] sm:max-h-none sm:w-[var(--pet-egg-w)] sm:border-l sm:border-t-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-small font-semibold text-ink">
          <Gem size={14} strokeWidth={1.75} aria-hidden className="text-alert" />
          Trứng
          <span className="font-data font-normal tabular-nums text-ink-muted">
            {egg.ruby_cost} ruby
          </span>
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Đóng màn trứng"
          className="grid h-6 w-6 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink"
        >
          <X size={14} strokeWidth={2} aria-hidden />
        </button>
      </div>

      {hatching ? (
        /* Quả trứng rung, chưa biết trong đó là gì. Đây là toàn bộ khoảnh khắc
           mà một hệ gacha bán: bỏ nó đi thì mở trứng chỉ là một dòng chữ đổi
           giá trị. */
        <div className="mt-3 flex items-center gap-3 rounded border border-rule-strong p-3">
          <span className="pet-egg-shake grid h-12 w-12 place-items-center" aria-hidden>
            <PixelIcon name="egg" scale={5} />
          </span>
          <p className="text-small text-ink-muted" role="status">
            Trứng đang nứt…
          </p>
        </div>
      ) : result ? (
        <div className="mt-3 flex items-center gap-3 rounded border border-rule-strong p-3">
          {/* `key` theo mã loài + số dư: cùng một con nở hai lần liên tiếp vẫn
              phải bật ra lại, mà React thì tái dùng node khi khoá không đổi —
              không có khoá này thì lần thứ hai hiện ra lặng lẽ. */}
          <Creature
            key={`${result.species.code}-${result.balance}`}
            tile={result.species.tile}
            size={48}
            className="pet-hatch-pop"
          />
          <div className="min-w-0">
            <p className="font-semibold text-ink">
              {result.species.label}{" "}
              <span className={cx("text-small", TIER_TONE[result.species.tier])}>
                {TIER_LABEL[result.species.tier] ?? result.species.tier} · {result.species.percent}%
              </span>
            </p>
            {/* Trùng thì NÓI RA là trùng và hoàn bao nhiêu. Giấu đi thì người
                chơi thấy một con đã có và không hiểu vì sao số dư lại nhích. */}
            <p className="text-small text-ink-muted">
              {result.duplicate
                ? `Đã có rồi — hoàn lại ${result.refund} ruby.`
                : "Con mới! Đã vào bộ sưu tập."}
              {result.forced_rare && " Bộ đếm an ủi đã ép ra hạng hiếm."}
            </p>
          </div>
        </div>
      ) : (
        <p className="mt-2 text-small text-ink-muted">
          Ruby kiếm được từ việc học xong một bài, một chủ đề hay một đề.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={open} disabled={busy || !egg.can_open}>
          {result ? "Mở quả nữa" : "Mở trứng"}
        </Button>
        <span className="font-data text-small tabular-nums text-ink-muted">
          còn {egg.balance} ruby
        </span>
        {/* Bộ đếm an ủi thành một câu, không phải "7/10". */}
        {left > 0 ? (
          <span className="text-small text-ink-faint">
            còn {left} quả nữa là chắc chắn ra hạng hiếm
          </span>
        ) : (
          <span className="text-small text-action">quả sau chắc chắn ra hạng hiếm</span>
        )}
      </div>

      {refused && <p className="mt-2 text-small text-warn">{refused}</p>}

      <button
        type="button"
        onClick={() => setShowOdds(!showOdds)}
        aria-expanded={showOdds}
        className="mt-3 text-small text-ink-muted underline underline-offset-2 hover:text-ink"
      >
        {showOdds ? "Ẩn tỉ lệ" : `Xem tỉ lệ (${egg.chances.length} loài)`}
      </button>

      {showOdds && (
        <ul className="mt-2 grid gap-1">
          {egg.chances.map((row) => {
            const owned = egg.owned.includes(row.code);
            return (
              <li key={row.code} className="flex items-center gap-2 text-small">
                <Creature tile={row.tile} size={24} />
                <span className={cx("flex-1 truncate", owned ? "text-ink" : "text-ink-muted")}>
                  {row.label}
                  {owned && <span className="ml-1 text-ink-faint">· đã có</span>}
                </span>
                <span className={cx("text-label", TIER_TONE[row.tier])}>
                  {TIER_LABEL[row.tier] ?? row.tier}
                </span>
                <span className="font-data tabular-nums text-ink-muted">{row.percent}%</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
