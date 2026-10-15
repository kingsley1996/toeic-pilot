"use client";

import {
  ArrowRight,
  BarChart3,
  BatteryMedium,
  BookOpen,
  Check,
  Clock,
  Flame,
  Headphones,
  House,
  Map,
  PencilLine,
  Signal,
  Sparkles,
  Target,
  Wifi,
} from "lucide-react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect } from "react";

import {
  DICTATION_DURATION,
  EXAM_DURATION,
  type IconName,
  landing,
  VOCAB_DURATION,
} from "@/content/landing";
import { useSession } from "@/lib/session";

/*
 * Ba khối nặng nhất của trang nằm NGOÀI khung nhìn đầu tiên, và mỗi khối kéo
 * theo một runtime đắt (Remotion cho ô minh hoạ, canvas + dữ liệu bản đồ cho
 * Petland). Tải lười từng khối: khách truy cập đầu tiên chỉ trả đúng phần họ
 * cuộn tới. `ssr: false` an toàn vì cả ba đều chỉ hiện khi đã hydrate
 * (`MockPlayer` tự đo bằng `useSyncExternalStore`, hai khối Petland đo bằng
 * IntersectionObserver).
 */
const MockPlayer = dynamic(() => import("@/components/mock-player").then((m) => m.MockPlayer), {
  ssr: false,
});
const PetlandDemo = dynamic(
  () => import("@/components/petland/petland-demo").then((m) => m.PetlandDemo),
  {
    ssr: false,
  },
);
const PetlandSpecies = dynamic(
  () => import("@/components/petland/petland-preview").then((m) => m.PetlandSpecies),
  { ssr: false },
);
/*
 * `mocks.tsx` là nơi duy nhất kéo runtime `remotion` vào bundle — tách nó khỏi
 * trang bằng đúng nhánh lazy trên, còn duration là hằng số bé nên giữ ở đây.
 */
const VocabCard = dynamic(() => import("@/remotion/mocks").then((m) => m.VocabCard), {
  ssr: false,
});
const DictationBox = dynamic(() => import("@/remotion/mocks").then((m) => m.DictationBox), {
  ssr: false,
});
const ExamQuestion = dynamic(() => import("@/remotion/mocks").then((m) => m.ExamQuestion), {
  ssr: false,
});

/* Icon tra theo TÊN, không ghép theo chỉ số mảng: người dịch thêm hay bớt một
   mục thì ghép theo chỉ số lệch hết mà TypeScript không kêu gì. */
const ICONS: Record<IconName, typeof BookOpen> = {
  "book-open": BookOpen,
  headphones: Headphones,
  "pencil-line": PencilLine,
  target: Target,
  "bar-chart": BarChart3,
  clock: Clock,
  flame: Flame,
  house: House,
  map: Map,
  sparkles: Sparkles,
};

/*
 * Trang giới thiệu — bố cục VÀ nội dung theo `planning/toeic-pilot-landing.html`,
 * dịch sang tiếng Việt cho khớp phần còn lại của app dành cho người học.
 *
 * **Trang này đứng ngoài design system về hình khối** — bo góc 24px, bóng đổ,
 * khung cửa sổ nghiêng — nhưng **màu thì theo hệ**: biến `--l-*` ở cuối
 * `globals.css` chỉ là bí danh trỏ vào token, nên chế độ tối tự đúng.
 *
 * Khung minh hoạ ở hero ("trang Hôm nay", điện thoại, mascot) là hình minh hoạ
 * tĩnh với số liệu minh hoạ — nó không đọc gì từ máy chủ và không thay thế màn
 * hình thật trong app.
 *
 * **Không có chữ hiển thị nào viết thẳng trong tệp này** — tất cả ở
 * `content/landing.ts`, để sửa lời hay dịch sang ngôn ngữ khác không phải mở
 * một tệp JSX ra dò.
 */

export default function HomePage() {
  const { status } = useSession();

  // Ba trạng thái, không phải hai: `loading` khác `anonymous`, vì localStorage
  // chưa tồn tại lúc máy chủ dựng trang.
  //
  // Nút chính luôn là bài test đầu vào: đã đăng nhập thì vào thẳng placement,
  // chưa thì đăng ký xong quay lại đúng đó (`?next=`, register hỗ trợ sẵn).
  const cta =
    status === "authenticated"
      ? { href: "/learn/placement", label: landing.hero.ctaPrimary }
      : { href: "/register?next=/learn/placement", label: landing.hero.ctaPrimary };
  const v = landing.heroVisual;

  /* Hiện dần khi cuộn cho section problems: chỉ thêm class `l-in`, CSS lo
     hiệu ứng. Không có IntersectionObserver (trình duyệt rất cũ) thì hiện
     luôn để không giấu nội dung. */
  useEffect(() => {
    const els = Array.from(document.querySelectorAll(".l-reveal"));
    if (!("IntersectionObserver" in window)) {
      els.forEach((el) => el.classList.add("l-in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("l-in");
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.2 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <div className="landing">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="l-hero">
        <div className="l-container l-hero-grid">
          <div>
            <div className="l-eyebrow">{landing.hero.eyebrow}</div>
            <h1>
              {landing.hero.titleTop}
              <br />
              <span>{landing.hero.titleAccent}</span>
            </h1>
            <p className="l-lead">{landing.hero.lead}</p>

            <div className="l-actions">
              {/* Giữ nút chiếm chỗ lúc session chưa xong (`visibility`, không
                  phải bỏ hẳn): nút hiện ra muộn đẩy nút phụ xuống là CLS. */}
              {status !== "loading" ? (
                <Link className="l-btn l-btn-primary" href={cta.href}>
                  {cta.label} <ArrowRight size={16} strokeWidth={2.5} aria-hidden />
                </Link>
              ) : (
                <span className="l-btn l-btn-primary invisible" aria-hidden>
                  {landing.hero.ctaPrimary} <ArrowRight size={16} strokeWidth={2.5} aria-hidden />
                </span>
              )}
              <a className="l-btn l-btn-secondary" href="#features">
                {landing.hero.ctaSecondary}
              </a>
            </div>

            <div className="l-trust">
              {landing.hero.features.map((f) => (
                <span key={f.title}>{f.title}</span>
              ))}
            </div>
          </div>

          {/* Minh hoạ tĩnh "trang Hôm nay": số liệu minh hoạ, không đọc API.
              `aria-hidden` vì đây là hình trang trí — lời kêu gọi thật nằm ở
              cột trái. */}
          <div className="l-hero-visual" aria-hidden>
            <div className="l-dashcard">
              <div className="l-dashcard-top">
                <span className="l-dashcard-brand">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src="/brand/mark.png" alt="" width={20} height={20} />
                  {v.brand}
                </span>
                <span className="l-dashcard-right">
                  <span className="l-dashcard-ruby">{v.ruby}</span>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    className="l-dashcard-avatar"
                    src="/brand/pilot-idle.png"
                    alt=""
                    width={22}
                    height={22}
                  />
                </span>
              </div>
              <div className="l-dashcard-body">
                <div className="l-dashcard-nav">
                  {v.nav.map((item, i) => (
                    <span key={item} className={i === 0 ? "l-dashcard-nav-active" : undefined}>
                      {item}
                    </span>
                  ))}
                </div>
                <div className="l-dashcard-main">
                  <div className="l-dashcard-hello">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      className="l-dashcard-avatar"
                      src="/brand/pilot-idle.png"
                      alt=""
                      width={30}
                      height={30}
                    />
                    <span>
                      <b>{v.greeting}</b>
                      <small>{v.greetingNote}</small>
                    </span>
                  </div>
                  <div className="l-dashcard-stats">
                    <div className="l-dashcard-stat">
                      <span>{v.levelLabel}</span>
                      <b>{v.levelValue}</b>
                      <i className="l-dashcard-bar">
                        <i style={{ width: "42%" }} />
                      </i>
                    </div>
                    <div className="l-dashcard-stat">
                      <span>{v.tasksLabel}</span>
                      <b>{v.tasksValue}</b>
                      <i className="l-dashcard-bar">
                        <i style={{ width: "67%" }} />
                      </i>
                    </div>
                  </div>
                  <div className="l-dashcard-continue">{v.continueLabel}</div>
                  <div className="l-dashcard-row">
                    <span>
                      <b>{v.courseTitle}</b>
                      <small>{v.courseMeta}</small>
                    </span>
                    <em>{v.courseCta}</em>
                  </div>
                  <div className="l-dashcard-row">
                    <span>
                      <b>{v.reviewTitle}</b>
                      <small>{v.reviewMeta}</small>
                    </span>
                    <em>{v.reviewCta}</em>
                  </div>
                </div>
              </div>
            </div>

            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              className="l-mascot"
              src="/brand/pilot-cheer.png"
              alt=""
              width={110}
              height={110}
            />

            <div className="l-cheer">
              <span>{landing.hero.cheer}</span>
              <svg viewBox="0 0 60 40" aria-hidden>
                <path
                  d="M6 4 C 30 6, 48 12, 52 34 M52 34 l-9 -6 M52 34 l1 -11"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              </svg>
            </div>

            {/* Điện thoại minh hoạ giao diện app thật: thanh trạng thái, đầu
                trang, tiến độ, thẻ bài học, tab dưới, vạch home. Chữ lấy từ
                `heroVisual` như dashboard, "9:41" là số giờ mẫu như iPhone. */}
            <div className="l-phone">
              <div className="l-phone-screen">
                <div className="l-phone-status">
                  <span>9:41</span>
                  <i className="l-phone-island" />
                  <span className="l-phone-status-icons">
                    <Signal size={10} strokeWidth={2.5} aria-hidden />
                    <Wifi size={10} strokeWidth={2.5} aria-hidden />
                    <BatteryMedium size={13} strokeWidth={2} aria-hidden />
                  </span>
                </div>
                <div className="l-phone-app">
                  <span className="l-phone-brand">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src="/brand/mark.png" alt="" width={18} height={18} />
                    {v.brand}
                  </span>
                  <span className="l-dashcard-ruby">{v.ruby}</span>
                </div>
                <div className="l-phone-hello">
                  <b>{v.greeting}</b>
                  <small>
                    {v.tasksLabel} {v.tasksValue}
                  </small>
                  <i className="l-dashcard-bar">
                    <i style={{ width: "67%" }} />
                  </i>
                </div>
                <div className="l-phone-card">
                  <span>{v.unfinishedLabel}</span>
                  <b>{v.courseTitle}</b>
                  <small>{v.courseMeta}</small>
                  <em>{v.courseCta}</em>
                </div>
                <div className="l-phone-card">
                  <b>{v.reviewTitle}</b>
                  <small>{v.reviewMeta}</small>
                  <em>{v.reviewCta}</em>
                </div>
                <div className="l-phone-tabs">
                  {v.tabs.map((t) => {
                    const Icon = ICONS[t.icon];
                    return (
                      <span key={t.label}>
                        <Icon size={14} strokeWidth={2.2} aria-hidden />
                        {t.label}
                      </span>
                    );
                  })}
                </div>
                <i className="l-phone-home" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Vì sao học TOEIC hay thất bại ────────────────────────────────── */}
      <section className="l-section l-alt l-problems">
        <div className="l-container">
          <div className="l-head l-reveal">
            <div className="l-kicker">{landing.problems.kicker}</div>
            <h2>{landing.problems.title}</h2>
            <p>{landing.problems.lead}</p>
          </div>
          <div className="l-grid-3">
            {landing.problems.items.map((p, i) => (
              <article
                key={p.title}
                className="l-tile l-reveal"
                style={{ transitionDelay: `${(i + 1) * 100}ms` }}
              >
                <div className="l-num">{String(i + 1).padStart(2, "0")}</div>
                <h3>{p.title}</h3>
                <p>{p.body}</p>
                {/* Mỗi vấn đề chốt bằng đúng tính năng gỡ nó: ô vấn đề không còn
                    là ngõ cụt, và mọi con số đều lấy từ USER-GUIDE (không hứa
                    điểm, không gọi placement là điểm thi thật). */}
                <div className="l-solution">{p.answer}</div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── Một vòng học ─────────────────────────────────────────────────── */}
      <section className="l-section" id="features">
        <div className="l-container">
          <div className="l-head">
            <div className="l-kicker">{landing.loop.kicker}</div>
            <h2>{landing.loop.title}</h2>
            <p>{landing.loop.lead}</p>
          </div>
          <div className="l-loop">
            <div className="l-loop-visual">
              {/* Ba bước trên một quỹ đạo xoay: vòng đứt nét quay chậm cùng ba
                  mũi tên chỉ chiều học, nút tròn nào cũng đọc từ `loop.steps`.
                  Trang trí thuần CSS, tắt khi giảm chuyển động. */}
              <div className="l-orbit" aria-hidden>
                <svg className="l-orbit-ring" viewBox="0 0 300 300">
                  <defs>
                    <linearGradient id="l-orbit-grad" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0" className="l-g1" />
                      <stop offset="0.45" className="l-g1" />
                      <stop offset="0.7" className="l-g0" />
                      <stop offset="1" className="l-g0" />
                    </linearGradient>
                  </defs>
                  <circle className="l-orbit-track" cx="150" cy="150" r="118" fill="none" />
                  <circle
                    className="l-orbit-flow"
                    cx="150"
                    cy="150"
                    r="118"
                    fill="none"
                    stroke="url(#l-orbit-grad)"
                    strokeWidth="2.5"
                    strokeDasharray="6 8"
                    strokeLinecap="round"
                  />
                  {/* Mũi tên nằm GIỮA các nút (góc -30/90/210°), không đè nút. */}
                  <g transform="translate(252,91) rotate(60)">
                    <path className="l-orbit-head" d="M-7,-6 L7,0 L-7,6 Z" />
                  </g>
                  <g transform="translate(150,268) rotate(180)">
                    <path className="l-orbit-head" d="M-7,-6 L7,0 L-7,6 Z" />
                  </g>
                  <g transform="translate(48,91) rotate(300)">
                    <path className="l-orbit-head" d="M-7,-6 L7,0 L-7,6 Z" />
                  </g>
                </svg>
                {landing.loop.steps.map((s, i) => (
                  <div key={s.label} className={`l-orbit-node l-pos-${i}`}>
                    <span className="l-orbit-dot">
                      {(() => {
                        const Icon = ICONS[s.icon];
                        return <Icon size={24} strokeWidth={1.8} aria-hidden />;
                      })()}
                    </span>
                    <b>{s.label}</b>
                  </div>
                ))}
              </div>
              <div className="l-hr" />
              <div className="l-loop-foot">
                <span>{landing.loop.footLeft}</span>
                <b>{landing.loop.footRight}</b>
              </div>
            </div>

            <div className="l-grid-2">
              {landing.loop.features.map((f) => (
                <article key={f.title} className="l-tile">
                  <div className="l-feature-icon">
                    {(() => {
                      const Icon = ICONS[f.icon];
                      return <Icon size={21} strokeWidth={1.8} aria-hidden />;
                    })()}
                  </div>
                  <h3>{f.title}</h3>
                  <p>{f.body}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Từ vựng ──────────────────────────────────────────────────────── */}
      <section className="l-section l-alt">
        <div className="l-container">
          <div className="l-showcase">
            <div className="l-copy">
              <div className="l-kicker">{landing.vocabulary.kicker}</div>
              <h3>{landing.vocabulary.title}</h3>
              <p>{landing.vocabulary.lead}</p>
              <Bullets items={landing.vocabulary.bullets} />
            </div>
            <div className="l-mock">
              <MockPlayer
                component={VocabCard}
                durationInFrames={VOCAB_DURATION}
                width={460}
                height={310}
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Nghe chép chính tả ───────────────────────────────────────────── */}
      <section className="l-section">
        <div className="l-container">
          <div className="l-showcase l-reverse">
            <div className="l-copy">
              <div className="l-kicker">{landing.dictation.kicker}</div>
              <h3>{landing.dictation.title}</h3>
              <p>{landing.dictation.lead}</p>
              <Bullets items={landing.dictation.bullets} />
              {/* Chỉ dựng cho khách. Người đã đăng nhập có mục "Dictation" ngay
                  trên thanh điều hướng, nên nút này với họ là một lối vào thứ
                  hai tới cùng một chỗ. `loading` cũng không dựng: nháy một nút
                  rồi rút đi là thứ luật ba trạng thái tồn tại để tránh. */}
              {status === "anonymous" && (
                <Link className="l-btn l-btn-primary l-inline-cta" href="/learn/dictation">
                  {landing.dictation.cta} <ArrowRight size={16} strokeWidth={2.5} aria-hidden />
                </Link>
              )}
            </div>
            <div className="l-mock">
              <MockPlayer
                component={DictationBox}
                durationInFrames={DICTATION_DURATION}
                width={460}
                height={250}
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Luyện đề ─────────────────────────────────────────────────────── */}
      <section className="l-section l-alt">
        <div className="l-container">
          <div className="l-showcase">
            <div className="l-copy">
              <div className="l-kicker">{landing.exam.kicker}</div>
              <h3>{landing.exam.title}</h3>
              <p>{landing.exam.lead}</p>
              <Bullets items={landing.exam.bullets} />
            </div>
            <div className="l-mock">
              <MockPlayer
                component={ExamQuestion}
                durationInFrames={EXAM_DURATION}
                width={460}
                height={320}
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Chất lượng nội dung ──────────────────────────────────────────── */}
      <section className="l-section l-ai">
        <div className="l-container">
          <div className="l-head">
            <div className="l-kicker">{landing.quality.kicker}</div>
            <h2>{landing.quality.title}</h2>
            <p>{landing.quality.lead}</p>
          </div>
          <div className="l-pipeline">
            {landing.quality.steps.map((p, i) => (
              <div key={p.title} className="contents">
                {i > 0 && (
                  <div className="l-pipe-arrow" aria-hidden>
                    <ArrowRight size={16} strokeWidth={2} />
                  </div>
                )}
                <div className="l-pipe">
                  <div className="l-num">{String(i + 1).padStart(2, "0")}</div>
                  <h3>{p.title}</h3>
                  <p>{p.body}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="l-note">
            <b>{landing.quality.noteStrong}</b> {landing.quality.noteBody}
          </div>
        </div>
      </section>

      {/* ── Thú cưng ─────────────────────────────────────────────────────── */}
      {/* `l-alt` ở đây, không phải ở `habits`: dải "chất lượng nội dung" ngay
          trên đã nhả nền riêng, nên nhịp sáng–tối phải nhích xuống một bậc. */}
      <section className="l-section l-alt">
        <div className="l-container l-pet-layout">
          {/* Cảnh chạy thay cho bản đồ đứng yên. Nó tự lo vòng chạy: `rAF` ghi
              thẳng vào DOM, và không chạy chút nào khi người dùng xin giảm
              chuyển động. */}
          <div className="l-console">
            <div className="l-console-top">
              <span className="l-console-led" aria-hidden />
              <span className="l-console-name">Petland</span>
            </div>
            <div className="l-console-screen">
              <PetlandDemo />
            </div>
            {/* Trang trí, không phải điều khiển — nên là `div` chứ không phải
                `button`, và `aria-hidden` để trình đọc màn hình không mời người
                dùng bấm vào thứ không làm gì. */}
            <div className="l-console-pad" aria-hidden>
              <span className="l-console-dpad" />
              <span className="l-console-keys">
                <span className="l-console-key" />
                <span className="l-console-key" />
              </span>
            </div>
          </div>
          <div>
            <div className="l-kicker">{landing.pet.kicker}</div>
            <h3>{landing.pet.title}</h3>
            <p className="l-pet-lead">{landing.pet.lead}</p>
            <Bullets items={landing.pet.bullets} />
          </div>
        </div>

        {/* Nói "sưu tầm bạn đồng hành mới" mà không cho xem con nào thì người
            đọc không biết mình đang được mời sưu tầm cái gì. */}
        <div className="l-container l-species">
          <div className="l-tile">
            <div className="l-label">{landing.pet.speciesLabel}</div>
            <div style={{ marginTop: 22 }}>
              <PetlandSpecies />
            </div>
          </div>
        </div>
      </section>

      {/* ── Dựng cho sự đều đặn ──────────────────────────────────────────── */}
      <section className="l-section">
        <div className="l-container">
          <div className="l-head">
            <div className="l-kicker">{landing.habits.kicker}</div>
            <h2>{landing.habits.title}</h2>
            <p>{landing.habits.lead}</p>
          </div>
          <div className="l-grid-3">
            {landing.habits.items.map((h) => (
              <article key={h.title} className="l-tile">
                <div className="l-feature-icon">
                  {(() => {
                    const Icon = ICONS[h.icon];
                    return <Icon size={21} strokeWidth={1.8} aria-hidden />;
                  })()}
                </div>
                <h3>{h.title}</h3>
                <p>{h.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── Kết ──────────────────────────────────────────────────────────── */}
      <section className="l-final">
        <div className="l-container">
          <div className="l-kicker">{landing.final.kicker}</div>
          <h2>
            {landing.final.titleTop}
            <br />
            {landing.final.titleBottom}
          </h2>
          <p>{landing.final.lead}</p>
          <div className="l-actions l-center">
            {status !== "loading" && (
              <Link className="l-btn l-btn-primary" href={cta.href}>
                {cta.label} <ArrowRight size={16} strokeWidth={2.5} aria-hidden />
              </Link>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

// `readonly`: `content/landing.ts` khai `as const`, và component này chỉ đọc.
function Bullets({ items }: { items: readonly string[] }) {
  return (
    <div className="l-bullets">
      {items.map((b) => (
        <div key={b}>
          <Check size={15} strokeWidth={3} aria-hidden />
          <span>{b}</span>
        </div>
      ))}
    </div>
  );
}
