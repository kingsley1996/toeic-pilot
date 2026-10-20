"use client";

import { API_ROUTES, type DictationDetail } from "@toeic-pilot/shared";
import { ArrowLeft, Shuffle } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { DictationExercise } from "@/components/dictation-exercise";
import { Alert, Button, Page, PageHeader, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { GuestNotice } from "@/components/guest-notice";
import { useSession } from "@/lib/session";

/**
 * Nghe ngẫu nhiên: một câu bất kỳ trong toàn bộ nội dung, không theo cây.
 *
 * Cây topic → unit → bài trả lời câu hỏi "học theo trình tự thì đi đâu". Trang
 * này trả lời câu khác hẳn: *ôn lại* thì nghe gì. Không có trình tự, không có
 * tiến độ, không có chỗ dừng — đúng tinh thần một buổi nghe cho quen tai.
 *
 * **Việc bốc nằm ở máy chủ.** Trình duyệt không biết kho có bao nhiêu câu, và
 * bắt nó hỏi `total` rồi tự bốc `offset` là kéo cơ chế phân trang vào một tính
 * năng không liên quan — chưa kể nó không loại được câu vừa nghe.
 *
 * Gõ đúng rồi thì Enter là "câu khác", cùng phím với "câu tiếp theo" ở luồng
 * bài: cả hai đều là *việc kế tiếp*, nên tay không phải học lại phím mới khi
 * đổi chế độ.
 */
export default function RandomDictationPage() {
  // Không lấy `token`: trang này không hiện tiến độ và endpoint không cần auth.
  const { status } = useSession();
  const [item, setItem] = useState<DictationDetail | null>(null);
  const [rolling, setRolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /*
   * `setRolling` KHÔNG nằm trong `roll`, và đó không phải chuyện gọn gàng.
   *
   * `roll` được gọi thẳng trong effect lúc mở trang. Một `setState` chạy đồng
   * bộ trong thân effect là thứ luật `react-hooks/set-state-in-effect` của dự án
   * này chặn — nó xếp tầng render — nên trạng thái "đang bốc" được bật ở CHỖ
   * BẤM, nơi nó thật sự có nghĩa, còn `roll` chỉ đi lấy dữ liệu.
   */
  const roll = useCallback((exclude?: string) => {
    const url = exclude
      ? `${API_ROUTES.dictationRandom}?exclude=${exclude}`
      : API_ROUTES.dictationRandom;
    return apiFetch<DictationDetail>(url)
      .then((data) => {
        setItem(data);
        setError(null);
      })
      .catch(() => setError("Chưa có câu nào để nghe. Nội dung có thể đang được biên soạn."))
      .finally(() => setRolling(false));
  }, []);

  useEffect(() => {
    // KHÔNG chờ token: `/dictation-random` không cần đăng nhập, và trang này
    // không hiện tiến độ nên chẳng có gì để đợi. Điều kiện cũ là `if (token)`,
    // và với khách vãng lai nó im lặng không bao giờ chạy — trang dựng xong với
    // `item` là null, không skeleton vì phiên đã phân giải, không lỗi vì chưa ai
    // gọi gì. Một trang trắng mà không có gì sai để mà báo.
    void roll();
  }, [roll]);

  /** Bốc lại theo yêu cầu của người dùng: khoá nút trong lúc chờ, rồi đi lấy. */
  function reroll(exclude: string) {
    setRolling(true);
    void roll(exclude);
  }

  if (status === "loading") {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page className={item ? "py-4 sm:py-6" : "max-w-3xl"}>
      {item ? (
        // Cùng chế độ luyện với trang bài: thanh trên gọn, phần gõ ở giữa.
        <div className="mx-auto flex min-h-[calc(100dvh-16rem)] w-full max-w-5xl flex-col">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/learn/dictation"
              aria-label="Quay lại Dictation"
              title="Quay lại Dictation"
              className="grid h-8 w-8 shrink-0 place-items-center rounded border border-rule-strong text-ink-muted transition-colors hover:bg-recess hover:text-ink"
            >
              <ArrowLeft size={16} strokeWidth={2} aria-hidden />
            </Link>
            <h1 className="min-w-0 truncate text-subtitle font-semibold">Nghe ngẫu nhiên</h1>
            <Button
              className="ml-auto"
              variant="secondary"
              size="sm"
              onClick={() => reroll(item.id)}
              disabled={rolling}
              /* Bỏ qua được TRƯỚC khi gõ xong. Một câu quá khó mà không có
                 đường vòng thì chế độ "nghe cho vui" biến thành chỗ mắc kẹt. */
            >
              <Shuffle size={14} strokeWidth={2} aria-hidden />
              Câu khác
            </Button>
          </div>
          <p className="mb-1 mt-2 text-small text-ink-muted">
            {item.word_count} từ · nghe lại bao nhiêu lần cũng được
          </p>
          <div className="flex flex-1 flex-col justify-center">
            <DictationExercise
              /* `key` chứ không phải effect reset — xem chú thích ở component.
                 Ở đây nó còn gánh thêm một việc: bốc câu mới phải xoá sạch ô
                 nhập và bảng đối chiếu của câu cũ, mà cách duy nhất chắc chắn
                 là thay hẳn component. */
              key={item.id}
              item={item}
              onNext={() => reroll(item.id)}
              nextLabel="Câu khác"
            />
          </div>
        </div>
      ) : (
        <>
          <Breadcrumbs trail={[{ href: "/learn/dictation", label: "Dictation" }]} />
          <PageHeader
            eyebrow="Dictation"
            title="Nghe ngẫu nhiên"
            description="Một câu bất kỳ trong toàn bộ nội dung. Không tính tiến độ, chỉ để quen tai."
          />

          <GuestNotice className="mb-4" />

          {error && <Alert>{error}</Alert>}

          {!item && !error && <SkeletonList rows={3} />}
        </>
      )}
    </Page>
  );
}
