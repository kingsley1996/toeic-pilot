"use client";

import { API_ROUTES, type FeedbackPublic, type FeedbackType } from "@toeic-pilot/shared";
import { MessageSquarePlus, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Modal } from "@/components/modal";
import { Button, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useToast } from "@/lib/toast";
import { messageFor, uploadFeedbackScreenshot } from "@/lib/upload";

/**
 * Nút góp ý dán ở mép phải màn hình.
 *
 * Là một CỤM chứ không một nút đơn lẻ: chỗ này sẽ còn thêm đường dẫn mạng xã
 * hội, và dựng sẵn khung dọc thì lần sau chỉ thêm một hàng thay vì phải nghĩ
 * lại chỗ đặt.
 */

const TYPES: { value: FeedbackType; label: string }[] = [
  { value: "bug", label: "Lỗi" },
  { value: "feature", label: "Đề xuất" },
  { value: "content", label: "Sai nội dung" },
  { value: "other", label: "Khác" },
];

const MAX_BYTES = 5 * 1024 * 1024;
const MAX_SHOTS = 3;

// Màn ĐANG LÀM BÀI. `/learn/attempts/` nằm đây cho đủ nghĩa dù `bareLayout` đã
// chặn nó — một danh sách chỉ đúng nhờ một cơ chế ở tệp khác là danh sách sẽ
// sai lặng lẽ vào ngày cơ chế kia đổi.
const EXAM_ROUTES = ["/learn/attempts/", "/learn/parts/sessions/"];

export function FeedbackDock() {
  const { status, token } = useSession();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Chỉ hiện với người đã đăng nhập: hàng `feedback` có `user_id` NOT NULL, nên
  // mời khách gửi là mời họ vào một biểu mẫu chắc chắn bị 401 ở nút Gửi.
  if (status !== "authenticated") return null;
  // Và không hiện ở màn ĐANG LÀM BÀI. `/learn/attempts/**` đã đi qua nhánh
  // `bareLayout` nên không tới được đây, nhưng phiên luyện theo part thì GIỮ
  // sidebar — nên nó cần một phép lọc riêng. Cùng lý do màn làm bài chỉ có hai
  // đường ra: đồng hồ vẫn chạy ở máy chủ trong lúc người ta đi chỗ khác, và
  // một nút mời viết góp ý ngay lúc đó là mời họ mất bài.
  if (EXAM_ROUTES.some((prefix) => pathname.startsWith(prefix))) return null;

  return (
    <>
      <div className="fixed right-4 top-1/2 z-40 -translate-y-1/2">
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Gửi góp ý"
          aria-label="Gửi góp ý"
          className="grid h-11 w-11 place-items-center rounded border border-rule-strong bg-panel text-ink-muted transition-colors hover:border-action hover:text-action-ink"
        >
          <MessageSquarePlus size={18} strokeWidth={2} aria-hidden />
        </button>
      </div>

      {/* Chỉ mount khi MỞ: modal đóng vẫn nằm trong DOM (`<dialog>` giữ
          children), và chữ trong nó — "chưa đúng", "Gửi góp ý" — trở thành
          trùng khớp dôi cho mọi locator getByText trên mọi trang có dock. */}
      {open && <FeedbackModal onClose={() => setOpen(false)} token={token} />}
    </>
  );
}

function FeedbackModal({ onClose, token }: { onClose: () => void; token: string | null }) {
  const { show } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"send" | "mine">("send");
  const [mine, setMine] = useState<FeedbackPublic[] | null>(null);
  const [reward, setReward] = useState(0);
  const [type, setType] = useState<FeedbackType>("bug");
  const [description, setDescription] = useState("");
  const [shots, setShots] = useState<{ key: string; preview: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMine = useCallback(
    () => apiFetch<FeedbackPublic[]>(API_ROUTES.feedbackMine, { token: token ?? "" }),
    [token],
  );

  // Mức thưởng đọc từ máy chủ, KHÔNG viết cứng vào giao diện: nó là một hàng
  // admin sửa được ở `/admin/ruby` mà không cần deploy, và một số viết thẳng
  // vào đây sẽ lệch ngay lần chỉnh đầu tiên — lệch theo hướng tệ nhất, là hứa
  // nhiều hơn thứ thật sự trao. Trả 0 nghĩa là nguồn đang tắt, và câu hứa biến
  // mất theo.
  useEffect(() => {
    if (!token) return;
    apiFetch<{ amount: number }>(API_ROUTES.feedbackReward, { token })
      .then((row) => setReward(row.amount))
      .catch(() => setReward(0));
  }, [open, token]);

  // `setState` trong `.then`, không trong thân effect — `react-hooks/set-state-in-effect`
  // cấm vế sau. Nạp LẠI mỗi lần mở tab chứ không nhớ: trạng thái đổi ở phía
  // admin, và một danh sách nhớ từ lần mở trước sẽ nói "chờ xử lý" về một góp ý
  // đã được duyệt xong.
  useEffect(() => {
    if (tab !== "mine" || !token) return;
    fetchMine()
      .then(setMine)
      .catch(() => setMine([]));
  }, [fetchMine, open, tab, token]);

  function reset() {
    setType("bug");
    setDescription("");
    setShots([]);
    setError(null);
  }

  async function pick(files: FileList | null) {
    if (!files?.length || !token) return;
    // Cắt theo chỗ CÒN LẠI, không theo tổng số vừa chọn: người dùng đã có hai
    // ảnh rồi chọn thêm ba thì lấy một, chứ không phải từ chối cả lượt.
    const room = MAX_SHOTS - shots.length;
    if (room <= 0) {
      setError(`Tối đa ${MAX_SHOTS} ảnh.`);
      return;
    }
    const chosen = Array.from(files).slice(0, room);
    // Chặn cỡ ở đây RỒI mới xin vé: vé đã ký mang sẵn `max_bytes`, nên file quá
    // cỡ vẫn bị nhà cung cấp từ chối — nhưng lúc đó người dùng đã chờ một vòng
    // mạng để nhận một thông báo lỗi bằng tiếng Anh của bên thứ ba.
    if (chosen.some((file) => file.size > MAX_BYTES)) {
      setError("Mỗi ảnh tối đa 5 MB.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      // Tuần tự chứ không `Promise.all`: mỗi vé là một lượt gọi tính vào hạn
      // mức, và bắn ba lượt cùng lúc là cách nhanh nhất để chạm trần rồi nhận
      // một lỗi khó hiểu ở giữa chừng.
      for (const file of chosen) {
        const key = await uploadFeedbackScreenshot(file, token);
        setShots((current) => [...current, { key, preview: URL.createObjectURL(file) }]);
      }
    } catch (uploadError) {
      setError(messageFor(uploadError, "Không tải được ảnh lên."));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!token || !description.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(API_ROUTES.feedback, {
        method: "POST",
        token,
        body: JSON.stringify({
          type,
          description: description.trim(),
          screenshot_keys: shots.map((shot) => shot.key),
        }),
      });
      show({ tone: "ok", title: "Cảm ơn bạn", description: "Góp ý đã được gửi tới đội ngũ." });
      reset();
      // Danh sách vừa cũ đi. Xoá chứ không nạp lại ngay: người dùng đang đóng
      // modal, và một lượt gọi mạng cho màn hình sắp biến mất là lãng phí — lần
      // mở tab sau sẽ tự nạp.
      setMine(null);
      onClose();
    } catch (sendError) {
      setError(messageFor(sendError, "Không gửi được góp ý."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Gửi góp ý"
      description={
        <>
          Báo lỗi, đề xuất tính năng, hoặc chỉ ra chỗ nội dung chưa đúng.
          {reward > 0 && (
            <>
              {" "}
              Góp ý được duyệt sẽ nhận{" "}
              <span className="font-semibold text-action-ink">{reward} ruby</span>.
            </>
          )}
        </>
      }
    >
      <div className="mb-4 flex gap-2 border-b border-rule">
        {(
          [
            ["send", "Gửi góp ý"],
            ["mine", "Góp ý của tôi"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            aria-pressed={tab === value}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-small font-semibold transition-colors",
              tab === value
                ? "border-action text-action-ink"
                : "border-transparent text-ink-muted hover:text-ink",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "mine" ? (
        <MyFeedbackList rows={mine} />
      ) : (
        <div className="space-y-4">
          <div>
            <p className="mb-1.5 text-label font-semibold uppercase text-ink-muted">Loại góp ý</p>
            <div className="flex flex-wrap gap-2">
              {TYPES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setType(option.value)}
                  aria-pressed={type === option.value}
                  className={cx(
                    "rounded border px-3 py-1.5 text-small font-medium transition-colors",
                    type === option.value
                      ? "border-action bg-action-tint text-action-ink"
                      : "border-rule bg-panel hover:border-rule-strong",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label
              htmlFor="feedback-description"
              className="mb-1.5 block text-label font-semibold uppercase text-ink-muted"
            >
              Mô tả
            </label>
            <textarea
              id="feedback-description"
              rows={5}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={4000}
              placeholder="Bạn gặp chuyện gì? Nếu là lỗi, cho biết bạn đang ở màn nào."
              className="w-full rounded border border-rule bg-panel p-3 leading-relaxed focus:border-rule-strong focus:outline-none"
            />
          </div>

          <div>
            <p className="mb-1.5 text-label font-semibold uppercase text-ink-muted">
              Ảnh minh hoạ{" "}
              <span className="font-normal normal-case">— tối đa {MAX_SHOTS}, không bắt buộc</span>
            </p>
            {shots.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {shots.map((shot) => (
                  <div key={shot.key} className="relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={shot.preview}
                      alt="Ảnh đính kèm"
                      className="h-24 w-24 rounded border border-rule object-cover"
                    />
                    <button
                      type="button"
                      aria-label="Gỡ ảnh này"
                      onClick={() =>
                        setShots((current) => current.filter((item) => item.key !== shot.key))
                      }
                      className="absolute -right-1.5 -top-1.5 grid h-6 w-6 place-items-center rounded border border-rule-strong bg-panel text-ink-muted hover:border-alert hover:text-alert"
                    >
                      <X size={12} strokeWidth={2.5} aria-hidden />
                    </button>
                  </div>
                ))}
              </div>
            )}
            {shots.length < MAX_SHOTS && (
              <>
                {/* Input ẩn, nút thật. Để `<input type="file">` hiện ra thì CẢ
                  chiều rộng của nó là vùng bấm — bấm vào khoảng trống bên phải
                  chữ "chưa chọn tệp" cũng mở cửa sổ chọn file. Một nút thật cho
                  vùng bấm đúng bằng cái nhìn thấy, và đi qua primitive của
                  design system thay vì `file:` pseudo-element. */}
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={(event) => {
                    void pick(event.target.files);
                    // Xoá giá trị để lần sau chọn LẠI đúng file đó vẫn kích hoạt
                    // `change` — trình duyệt im lặng khi giá trị không đổi, và
                    // người dùng tưởng nút hỏng.
                    event.target.value = "";
                  }}
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => fileRef.current?.click()}
                >
                  {shots.length ? `Thêm ảnh (${shots.length}/${MAX_SHOTS})` : "Chọn ảnh"}
                </Button>
              </>
            )}
          </div>

          {error && <p className="text-small text-alert">{error}</p>}

          <div className="flex justify-end gap-2">
            <Button variant="quiet" onClick={onClose} disabled={busy}>
              Huỷ
            </Button>
            <Button onClick={() => void submit()} disabled={busy || !description.trim()}>
              {busy ? "Đang gửi…" : "Gửi góp ý"}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  pending: { label: "Chờ xử lý", tone: "border-rule-strong text-ink-muted" },
  approved: { label: "Đã duyệt", tone: "border-ok text-ok" },
  rejected: { label: "Không tiếp nhận", tone: "border-alert text-alert" },
};

/**
 * Góp ý của chính mình.
 *
 * Không có trang riêng và không có thông báo đẩy khi admin xử lý — người học tự
 * mở lại đây để xem. Một tính năng góp ý mà người gửi không bao giờ biết chuyện
 * gì xảy ra tiếp theo thì lần sau họ không gửi nữa, nên trạng thái phải nhìn
 * thấy được ở ĐÂU ĐÓ; chỗ rẻ nhất là ngay cạnh ô gửi.
 */
function MyFeedbackList({ rows }: { rows: FeedbackPublic[] | null }) {
  if (rows === null) return <p className="text-small text-ink-muted">Đang tải…</p>;
  if (rows.length === 0) {
    return <p className="text-small text-ink-muted">Bạn chưa gửi góp ý nào.</p>;
  }

  return (
    <div className="max-h-[26rem] space-y-3 overflow-y-auto">
      {rows.map((row) => {
        const chip = STATUS_LABEL[row.status] ?? STATUS_LABEL.pending;
        return (
          <div key={row.id} className="rounded border border-rule bg-panel p-3">
            <div className="flex items-center justify-between gap-2">
              <span
                className={cx("rounded border px-2 py-0.5 text-label font-semibold", chip.tone)}
              >
                {chip.label}
              </span>
              <span className="text-label text-ink-faint">
                {new Date(row.created_at).toLocaleDateString("vi-VN")}
              </span>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-small leading-relaxed">{row.description}</p>
            {row.admin_note && (
              /* Lý do từ chối phải hiện ra. Người gửi thấy "không tiếp nhận" mà
                 không có lời nào thì đọc ra là bị bỏ qua, chứ không phải được
                 xem xét rồi quyết định. */
              <p className="mt-2 rounded border border-rule bg-recess p-2 text-small text-ink-muted">
                {row.admin_note}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
