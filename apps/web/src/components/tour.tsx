"use client";

import { autoUpdate, flip, offset, shift, useFloating } from "@floating-ui/react-dom";
import { API_ROUTES, type UserProfilePublic } from "@toeic-pilot/shared";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/**
 * Tour giới thiệu, chạy một lần cho người mới ở màn hình chính.
 *
 * **Tự dựng, không dùng thư viện tour.** Phần khó duy nhất là đặt bong bóng cạnh
 * một phần tử mà không tràn khỏi màn hình, và `@floating-ui/react-dom` làm đúng
 * việc đó — nó cũng chính là bộ định vị mà react-joyride và Shepherd dùng bên
 * dưới. Đổi lại, mọi thứ NHÌN THẤY ĐƯỢC là component của repo này, nên ba luật
 * hỏng-im-lặng của hệ thiết kế (không `box-shadow`, một bán kính 4px, viền
 * `rule-strong`) và chế độ sáng/tối đúng miễn phí. Thư viện tour nào cũng ship vỏ
 * riêng với bóng đổ và màu cứng, tức một tệp CSS đè lên chúng — và tệp ấy phải
 * sửa lại mỗi lần chúng lên bản.
 *
 * **Đèn rọi vẽ bằng SVG có lỗ khoét**, không phải `box-shadow` khổng lồ. Mẹo
 * `box-shadow: 0 0 0 9999px` là cách phổ biến nhất để làm hiệu ứng này, và nó bị
 * hệ thiết kế ở đây cấm thẳng.
 */

export type TourStep = {
  /** Bộ chọn CSS của phần tử được rọi. Bước không tìm thấy đích thì bị loại. */
  target: string;
  title: string;
  body: string;
};

/** Chừa quanh phần tử được rọi, để lỗ khoét không cắt sát vào chữ. */
const HALO = 6;

/** Bao lâu thì thôi đợi các khối trên trang hiện ra. */
const WAIT_MS = 6000;
const POLL_MS = 200;

export function Tour({ steps }: { steps: readonly TourStep[] }) {
  const { token, status } = useSession();
  /*
   * Danh sách bước THẬT SỰ chạy, chốt một lần lúc bắt đầu. `null` là chưa chạy.
   *
   * Lọc sẵn thay vì bỏ qua dọc đường: màn hình chính vẽ dần theo dữ liệu về và
   * vài khối chỉ hiện với người đã học, nên một bước trỏ vào thứ không tồn tại là
   * chuyện bình thường. Chốt trước cũng làm con số "2/4" nói thật — bỏ qua dọc
   * đường thì mẫu số hứa nhiều hơn số bước người ta sẽ thấy.
   */
  const [plan, setPlan] = useState<readonly TourStep[] | null>(null);
  const [at, setAt] = useState(0);

  const hole = useRef<SVGPathElement | null>(null);
  const ring = useRef<SVGRectElement | null>(null);

  const { refs, floatingStyles, update } = useFloating({
    placement: "bottom",
    /* `flip` lật sang phía còn chỗ, `shift` đẩy vào trong mép. Không có chúng thì
       một khối cao — vốn chiếm gần hết màn hình — đẩy bong bóng ra ngoài rìa. */
    middleware: [offset(HALO + 8), flip({ padding: 12 }), shift({ padding: 12 })],
    whileElementsMounted: autoUpdate,
  });

  /* Đọc `refs` trong callback chứ không lúc dựng: `react-hooks/refs` chặn lối
     kia, và nó đúng — một ref đọc lúc dựng là giá trị React không biết đã đổi. */
  const attachFloating = useCallback(
    (node: HTMLDivElement | null) => refs.setFloating(node),
    [refs],
  );

  /*
   * Chỉ chạy cho người CHƯA xem, và câu trả lời ấy đến từ máy chủ.
   *
   * `localStorage` sẽ làm tour bật lại ở mỗi thiết bị mới — người học bỏ qua nó
   * trên máy tính rồi gặp lại đúng lời chào ấy trên điện thoại.
   *
   * Rồi ĐỢI các khối hiện ra: trang này vẽ dần theo dữ liệu về, nên hỏi ngay lúc
   * hồ sơ trả lời là hỏi một trang còn trống. Đợi có hạn — quá hạn thì thôi, và
   * KHÔNG đánh dấu đã xem, nên lần sau họ vẫn được chào.
   */
  useEffect(() => {
    if (status !== "authenticated" || !token) return;
    let alive = true;
    let timer = 0;

    void apiFetch<UserProfilePublic>(API_ROUTES.profile, { token })
      .then((profile) => {
        if (!alive || profile.tour_done) return;
        const deadline = Date.now() + WAIT_MS;
        const look = () => {
          if (!alive) return;
          const found = steps.filter((step) => document.querySelector(step.target) !== null);
          /* Đợi ĐỦ bước, không phải bước đầu tiên: các khối hiện dần, nên dừng ở
             cái đầu tiên tìm thấy sẽ chốt một kế hoạch cụt và con số "1/1" nói
             dối. Hết hạn thì lấy những gì đang có. */
          if (found.length === steps.length) setPlan(found);
          else if (Date.now() < deadline) timer = window.setTimeout(look, POLL_MS);
          else if (found.length > 0) setPlan(found);
        };
        look();
      })
      .catch(() => {
        /* Không đọc được hồ sơ thì thôi không chào — im lặng hơn là chào nhầm. */
      });

    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [status, token, steps]);

  const finish = useCallback(() => {
    setPlan(null);
    if (!token) return;
    /* Bỏ qua và xem hết ghi CÙNG một thứ: cả hai đều là "tôi không cần thấy lại",
       và một tour bật lại vì người ta bấm Bỏ qua thì đúng là thứ khiến người ta
       bấm Bỏ qua lần nữa. */
    void apiFetch(API_ROUTES.profileTourSeen, { method: "POST", token }).catch(() => {});
  }, [token]);

  /*
   * Bám theo phần tử đang được rọi.
   *
   * Ghi THẲNG vào thuộc tính SVG thay vì giữ toạ độ trong state, cùng khuôn mà
   * bong bóng thoại của Petland dùng: cuộn sinh hàng trăm sự kiện mỗi giây, và
   * mỗi cái một `setState` là mỗi cái một lần dựng lại cả lớp phủ. Nó cũng tránh
   * luôn `react-hooks/set-state-in-effect`.
   */
  const step = plan?.[at] ?? null;
  useEffect(() => {
    if (!step) return;
    const target = document.querySelector<HTMLElement>(step.target);
    if (!target) return;
    refs.setReference(target);
    /*
     * Đích đã ở chỗ nhìn được chưa.
     *
     * Khối cao hơn màn hình KHÔNG BAO GIỜ vào trọn, nên với chúng chỉ đòi mép
     * trên nằm ở nửa trên — đòi cả hai mép là một điều kiện không bao giờ đúng,
     * và lần kéo lại bên dưới sẽ giật trang mãi.
     */
    const reached = () => {
      const box = target.getBoundingClientRect();
      if (box.top < 0) return false;
      return box.height > window.innerHeight
        ? box.top < window.innerHeight / 2
        : box.bottom <= window.innerHeight;
    };

    /*
     * Chỉ cuộn khi cần, và KIỂM LẠI xem cuộn có tới không.
     *
     * Hai chỗ hỏng im lặng nằm cạnh nhau ở đây. Một: `scrollIntoView` luôn cuộn
     * kể cả khi không cần, nên bước cuối — trỏ vào thẻ thú cưng trong sidebar CỐ
     * ĐỊNH — kéo cả trang xuống đáy để canh giữa một phần tử vốn không nhúc
     * nhích, và người dùng thấy trang bay đi trong khi thứ được rọi đứng yên.
     * Hai: cuộn mượt là một hiệu ứng, và trình duyệt được phép không chạy nó —
     * tab ở nền là trường hợp dễ gặp nhất. Khi đó tour rọi vào một khối nằm dưới
     * mép màn hình và bong bóng neo vào chỗ trống, không một lỗi nào được in ra.
     */
    let settle = 0;
    if (!reached()) {
      /* Cuộn mượt là chuyển động, nên nó theo cùng lựa chọn mà cả app theo
         (`motion-reduce:`). Người tắt hiệu ứng vẫn tới đích, chỉ là tới ngay. */
      const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      target.scrollIntoView({ block: "center", behavior: calm ? "auto" : "smooth" });
      settle = window.setTimeout(() => {
        if (!reached()) target.scrollIntoView({ block: "center" });
      }, 600);
    }

    const follow = () => {
      const box = target.getBoundingClientRect();
      const x = box.x - HALO;
      const y = box.y - HALO;
      const w = box.width + HALO * 2;
      const h = box.height + HALO * 2;
      // `fill-rule="evenodd"`: hình chữ nhật thứ hai đục thủng hình thứ nhất.
      hole.current?.setAttribute(
        "d",
        `M0 0H${window.innerWidth}V${window.innerHeight}H0Z M${x} ${y}h${w}v${h}h${-w}Z`,
      );
      const box2 = ring.current;
      if (box2) {
        box2.setAttribute("x", `${x}`);
        box2.setAttribute("y", `${y}`);
        box2.setAttribute("width", `${w}`);
        box2.setAttribute("height", `${h}`);
      }
      update();
    };
    follow();
    /* Cuộn mượt chạy vài trăm mili giây sau khi effect trả về, nên một lần đo là
       đo ở chỗ cũ. `capture` để bắt cả cuộn bên trong một khối con. */
    window.addEventListener("scroll", follow, true);
    window.addEventListener("resize", follow);
    /* Và đích tự lớn lên: mỗi khối trên trang này vẽ khung xám trước rồi mới
       thay bằng dữ liệu về, nên đo một lần là khoét một cái lỗ vừa vặn với khung
       xám và hụt mất phần vừa mọc thêm. */
    const grow = new ResizeObserver(follow);
    grow.observe(target);
    return () => {
      window.clearTimeout(settle);
      grow.disconnect();
      window.removeEventListener("scroll", follow, true);
      window.removeEventListener("resize", follow);
    };
  }, [step, refs, update]);

  // Escape để thoát — phím người ta thử đầu tiên trước bất cứ thứ gì che màn hình.
  useEffect(() => {
    if (!step) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") finish();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, finish]);

  if (!plan || !step) return null;

  const last = at + 1 >= plan.length;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={step.title}>
      {/* Lớp phủ nuốt cú bấm ra ngoài, và đó là chủ ý: một tour bấm xuyên qua
          được thì người dùng đi lạc giữa chừng, và bước sau trỏ vào một trang
          khác. `pointer-events-none` trên `<rect>` viền để nó không nằm chắn
          trước bong bóng — nó chỉ là nét vẽ. */}
      <svg className="absolute inset-0 h-full w-full" aria-hidden onClick={finish}>
        <path ref={hole} fillRule="evenodd" className="fill-ground/80" d="" />
        <rect
          ref={ring}
          rx={4}
          className="pointer-events-none fill-none stroke-action"
          strokeWidth={2}
        />
      </svg>

      <div
        ref={attachFloating}
        style={floatingStyles}
        className="w-[min(20rem,calc(100vw-24px))] rounded border border-rule-strong bg-panel p-4"
      >
        <p className="text-small font-semibold text-ink">{step.title}</p>
        <p className="mt-1 text-label leading-relaxed text-ink-muted">{step.body}</p>
        <div className="mt-3 flex items-center justify-between gap-3">
          {/* Số bước nói ra cái kết: người ta chịu đọc bước hai khi biết chỉ còn
              hai bước nữa, chứ không phải khi không biết còn bao nhiêu. */}
          <span className="font-data text-label tabular-nums text-ink-faint">
            {at + 1}/{plan.length}
          </span>
          <span className="flex items-center gap-2">
            <button
              type="button"
              onClick={finish}
              className={cx(
                "rounded px-2 py-1 text-label text-ink-muted transition-colors",
                "hover:bg-recess hover:text-ink",
              )}
            >
              Bỏ qua
            </button>
            <Button size="sm" onClick={() => (last ? finish() : setAt(at + 1))} autoFocus>
              {last ? "Xong" : "Tiếp"}
            </Button>
          </span>
        </div>
      </div>
    </div>
  );
}
