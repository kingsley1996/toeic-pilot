"use client";

import { API_ROUTES, type RubyClaimResult, type RubyWallet } from "@toeic-pilot/shared";
import { Gem, Gift } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, Panel, Skeleton, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useToast } from "@/lib/toast";

/**
 * Ví ruby, đặt ở `/dashboard` — chỗ người ta HỌC, không phải góc thú cưng
 * (ADR-011 §7).
 *
 * Một hệ điểm mà người ta không thấy mình vừa kiếm được thì không kích thích gì
 * cả, và đặt số dư trong góc chơi nghĩa là chỉ người đã vào chơi mới thấy nó —
 * tức là đúng những người không cần được mời.
 *
 * Ba điều dễ làm hỏng khi sửa:
 *
 *   · **Nút quà chỉ sáng SAU khi hôm nay đã học gì đó.** Ba trạng thái, không
 *     phải hai: chưa mở được, mở được, đã nhận. Câu chữ của trạng thái đầu là
 *     một lời mời — nó là toàn bộ lý do quà không sáng sẵn lúc mở app.
 *   · **Số dư đọc lại từ phản hồi của `POST`, không tự cộng ở client.** Máy chủ
 *     trả về số dư sau khi ghi; tự cộng 3 vào state là dựng một bộ đếm thứ hai
 *     cạnh sổ cái, đúng thứ cả ADR-011 tồn tại để tránh.
 *   · **Ruby không bao giờ được nói bằng cùng một câu với XP.** Hai đơn vị đo
 *     hai thứ khác nhau — XP thưởng khối lượng, ruby thưởng việc làm xong — và
 *     một dòng gộp là chỗ người dùng thôi phân biệt được chúng.
 */
export function RubyWalletPanel({ token }: { token: string | null }) {
  const { canPublish } = useSession();
  const [wallet, setWallet] = useState<RubyWallet | null>(null);
  const [claiming, setClaiming] = useState(false);
  const { show } = useToast();

  useEffect(() => {
    if (!token) return;
    let alive = true;
    apiFetch<RubyWallet>(API_ROUTES.ruby, { token })
      .then((data) => {
        if (alive) setWallet(data);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token]);

  if (!token) return null;
  if (!wallet) {
    return (
      <Panel className="mb-4 p-5" aria-busy>
        <Skeleton className="h-5 w-32" />
        <Skeleton className="mt-4 h-10" />
      </Panel>
    );
  }

  const { gift } = wallet;

  async function claim() {
    if (!token || claiming) return;
    setClaiming(true);
    try {
      const result = await apiFetch<RubyClaimResult>(API_ROUTES.rubyGift, {
        method: "POST",
        token,
      });
      setWallet((prev) => (prev ? { ...prev, balance: result.balance, gift: result.gift } : prev));
      if (result.granted > 0) {
        show({
          tone: "ok",
          title: "Đã nhận quà hôm nay",
          description: `+${result.granted} ruby.`,
          dedupeKey: "ruby-gift",
        });
      }
    } catch {
      // Nhận quà hỏng thì im lặng: nó là một khoản thêm, và một hộp thoại lỗi
      // cho một cú bấm vào phần thưởng là cách chắc chắn nhất để biến nó thành
      // một việc phải làm.
    } finally {
      setClaiming(false);
    }
  }

  return (
    <Panel className="mb-4 p-5" role="region" aria-labelledby="ruby-wallet-title">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <div className="flex items-center gap-3">
          <span aria-hidden className="grid h-9 w-9 place-items-center rounded bg-alert-tint">
            <Gem size={18} strokeWidth={1.75} className="text-alert" />
          </span>
          <div>
            <h2 id="ruby-wallet-title" className="text-subtitle">
              Ruby
            </h2>
            <p className="font-data text-small tabular-nums text-ink-muted">
              {/* Không tô màu số 0: màu là tín hiệu, và một số 0 xanh đọc như
                  một việc đã hoàn thành (§6.3 của USER-ROAD, áp cho cả ở đây). */}
              <span className={cx("text-title", wallet.balance > 0 && "text-alert")}>
                {wallet.balance}
              </span>
              <span className="ml-1.5 text-ink-faint">ruby đang có</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {gift.claimed ? (
            <p className="text-small text-ink-muted">Đã nhận quà hôm nay. Mai quay lại nhé.</p>
          ) : gift.unlocked ? (
            <Button onClick={claim} disabled={claiming}>
              <Gift size={16} strokeWidth={1.75} aria-hidden className="mr-2" />
              Nhận {gift.amount} ruby
            </Button>
          ) : (
            <p className="max-w-xs text-small text-ink-muted">
              Học xong một chút là mở được quà hôm nay ({gift.amount} ruby).
            </p>
          )}
        </div>
      </div>

      {/* Kiếm ruby bằng việc LÀM XONG, không bằng số lượt — câu này là thứ duy
          nhất trên màn hình nói ra sự khác nhau giữa hai đơn vị. */}
      <p className="mt-4 border-t border-rule pt-3 text-small text-ink-muted">
        Ruby đến từ việc <span className="text-ink">làm xong</span>: nghe hết một bài, thuộc trọn
        một chủ đề, làm hết một đề.
        {/* Nói thẳng với admin rằng con số này được cấp, không phải kiếm được.
            Không nói thì chính người vận hành là người đầu tiên hiểu sai nền
            kinh tế mà họ đang chỉnh — họ thấy 500 ruby ở đâu cũng đủ và kết luận
            rằng giá trứng đang quá rẻ. */}
        {canPublish && (
          <span className="mt-2 block text-ink-faint">
            Tài khoản quản trị luôn được cấp sẵn ruby để thử tính năng, nên số dư này không phải số
            kiếm được.
          </span>
        )}
      </p>
    </Panel>
  );
}
