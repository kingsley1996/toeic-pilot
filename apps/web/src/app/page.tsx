"use client";

import { API_ROUTES, type VocabularyPage } from "@toeic-pilot/shared";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Check,
  Clock,
  Flame,
  Headphones,
  PawPrint,
  PencilLine,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { MockPlayer } from "@/components/mock-player";
import { PetlandCreature, PetlandMap, PetlandSpecies } from "@/components/petland-preview";
import {
  DICTATION_DURATION,
  DictationBox,
  EXAM_DURATION,
  ExamQuestion,
  VOCAB_DURATION,
  VocabCard,
} from "@/remotion/mocks";
import { type IconName, landing } from "@/content/landing";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

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
};

/*
 * Trang giới thiệu — bố cục VÀ nội dung theo `planning/toeic-pilot-landing.html`,
 * dịch sang tiếng Việt cho khớp phần còn lại của app dành cho người học.
 *
 * **Trang này đứng ngoài design system về hình khối** — bo góc 24px, bóng đổ,
 * khung cửa sổ nghiêng — nhưng **màu thì theo hệ**: biến `--l-*` ở cuối
 * `globals.css` chỉ là bí danh trỏ vào token, nên chế độ tối tự đúng.
 *
 * Con số duy nhất đọc từ máy chủ là số từ vựng, cắm vào đúng ô mà bản mẫu để
 * "438 words". Còn lại là số minh hoạ của bản mẫu.
 *
 * **Không có chữ hiển thị nào viết thẳng trong tệp này** — tất cả ở
 * `content/landing.ts`, để sửa lời hay dịch sang ngôn ngữ khác không phải mở
 * một tệp JSX ra dò.
 */

export default function HomePage() {
  const { status } = useSession();
  const [petOpen, setPetOpen] = useState(false);
  const [words, setWords] = useState<number | null>(null);

  useEffect(() => {
    /*
     * Số từ lấy từ `total` của trang đầu, KHÔNG phải tổng `entry_count` các chủ
     * đề: `vocabulary_topic` là quan hệ nhiều-nhiều, nên một từ nằm ở hai chủ đề
     * sẽ được cộng hai lần và trang này khoe nhiều hơn số thật.
     */
    apiFetch<VocabularyPage>(`${API_ROUTES.vocabulary}?limit=1`)
      .then((p) => setWords(p.total))
      .catch(() => {});
  }, []);

  // Ba trạng thái, không phải hai: `loading` khác `anonymous`, vì localStorage
  // chưa tồn tại lúc máy chủ dựng trang.
  const cta =
    status === "authenticated"
      ? { href: "/dashboard", label: landing.hero.ctaSignedIn }
      : { href: "/register", label: landing.hero.ctaSignedOut };

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
              {status !== "loading" && (
                <Link className="l-btn l-btn-primary" href={cta.href}>
                  {cta.label} <ArrowRight size={16} strokeWidth={2.5} aria-hidden />
                </Link>
              )}
              <a className="l-btn l-btn-secondary" href="#features">
                {landing.hero.ctaSecondary}
              </a>
            </div>

            <div className="l-trust">
              {landing.hero.trust.map((t) => (
                <span key={t}>
                  <Check size={13} strokeWidth={3.5} aria-hidden />
                  {t}
                </span>
              ))}
            </div>
          </div>

          <div className="l-window">
            <div className="l-window-top" aria-hidden>
              <i className="l-dot" />
              <i className="l-dot" />
              <i className="l-dot" />
            </div>
            <div className="l-window-body">
              <div className="l-window-head">
                <div>
                  <div className="l-label">{landing.dashboard.greeting}</div>
                  <div style={{ fontWeight: 800 }}>{landing.dashboard.title}</div>
                </div>
                <span className="l-pill">{landing.dashboard.goal}</span>
              </div>

              <div className="l-dash">
                <div className="l-card l-card-tall">
                  <div className="l-label">{landing.dashboard.progressLabel}</div>
                  <div className="l-big">
                    {landing.dashboard.score} <span>{landing.dashboard.scoreOf}</span>
                  </div>
                  <div className="l-bar">
                    <i style={{ width: "72%" }} />
                  </div>
                  {landing.dashboard.rows.map((r) => (
                    <div key={r.label} className="l-ministat">
                      <span>{r.label}</span>
                      <b>{r.value}</b>
                    </div>
                  ))}
                  {/* Ô duy nhất mang số THẬT: bản mẫu để "438 words" ở đúng đây. */}
                  {words !== null && (
                    <div className="l-ministat">
                      <span>{landing.dashboard.vocabularyLabel}</span>
                      <b>
                        {landing.dashboard.vocabularyValue.replace(
                          "{n}",
                          words.toLocaleString("vi-VN"),
                        )}
                      </b>
                    </div>
                  )}
                </div>

                <div className="l-card">
                  <div className="l-label">{landing.dashboard.todayLabel}</div>
                  <div className="l-activity">
                    <div className="l-icon-box">
                      <BookOpen size={17} strokeWidth={1.9} aria-hidden />
                    </div>
                    <div>
                      <b>{landing.dashboard.todayTitle}</b>
                      <small>{landing.dashboard.todayNote}</small>
                    </div>
                  </div>
                </div>

                <div className="l-card">
                  <div className="l-label">{landing.dashboard.nextLabel}</div>
                  <div className="l-activity">
                    <div className="l-icon-box">
                      <Headphones size={17} strokeWidth={1.9} aria-hidden />
                    </div>
                    <div>
                      <b>{landing.dashboard.nextTitle}</b>
                      <small>{landing.dashboard.nextNote}</small>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Vì sao học TOEIC hay thất bại ────────────────────────────────── */}
      <section className="l-section l-alt">
        <div className="l-container">
          <div className="l-head">
            <div className="l-kicker">{landing.problems.kicker}</div>
            <h2>{landing.problems.title}</h2>
            <p>{landing.problems.lead}</p>
          </div>
          <div className="l-grid-3">
            {landing.problems.items.map((p, i) => (
              <article key={p.title} className="l-tile">
                <div className="l-num">{String(i + 1).padStart(2, "0")}</div>
                <h3>{p.title}</h3>
                <p>{p.body}</p>
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
              <div className="l-flow">
                {landing.loop.steps.map((s, i) => (
                  <div key={s.label} className="contents">
                    {i > 0 && (
                      <div className="l-arrow" aria-hidden>
                        <ArrowRight size={16} strokeWidth={2} />
                      </div>
                    )}
                    <div className="l-flow-item">
                      <div className="l-flow-box">
                        {(() => {
                          const Icon = ICONS[s.icon];
                          return <Icon size={25} strokeWidth={1.6} aria-hidden />;
                        })()}
                      </div>
                      <b>{s.label}</b>
                    </div>
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
                  <h4>{p.title}</h4>
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
          <PetlandMap className="l-pet-card" />
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
