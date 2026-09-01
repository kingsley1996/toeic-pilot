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
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

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
      ? { href: "/dashboard", label: "Vào học" }
      : { href: "/register", label: "Bắt đầu miễn phí" };

  return (
    <div className="landing">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="l-hero">
        <div className="l-container l-hero-grid">
          <div>
            <div className="l-eyebrow">Học TOEIC, theo cách dễ theo đuổi</div>
            <h1>
              Học TOEIC.
              <br />
              <span>Thấy mình tiến bộ.</span>
            </h1>
            <p className="l-lead">
              Xây vốn từ, luyện tai bằng nghe chép chính tả, và làm đề TOEIC Listening &amp; Reading
              — trong một hệ thống học được dựng để bạn quay lại mỗi ngày.
            </p>

            <div className="l-actions">
              {status !== "loading" && (
                <Link className="l-btn l-btn-primary" href={cta.href}>
                  {cta.label} <ArrowRight size={16} strokeWidth={2.5} aria-hidden />
                </Link>
              )}
              <a className="l-btn l-btn-secondary" href="#features">
                Xem nền tảng
              </a>
            </div>

            <div className="l-trust">
              {["Luyện từ vựng", "Nghe chép chính tả", "Luyện đề TOEIC LR"].map((t) => (
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
                  <div className="l-label">Chào buổi tối</div>
                  <div style={{ fontWeight: 800 }}>Bảng học của bạn</div>
                </div>
                <span className="l-pill">Mục tiêu 700</span>
              </div>

              <div className="l-dash">
                <div className="l-card l-card-tall">
                  <div className="l-label">Tiến độ TOEIC</div>
                  <div className="l-big">
                    560 <span>/ 700</span>
                  </div>
                  <div className="l-bar">
                    <i style={{ width: "72%" }} />
                  </div>
                  <div className="l-ministat">
                    <span>Listening</span>
                    <b>62%</b>
                  </div>
                  <div className="l-ministat">
                    <span>Reading</span>
                    <b>71%</b>
                  </div>
                  {/* Ô duy nhất mang số THẬT: bản mẫu để "438 words" ở đúng đây. */}
                  {words !== null && (
                    <div className="l-ministat">
                      <span>Từ vựng</span>
                      <b>{words.toLocaleString("vi-VN")} từ</b>
                    </div>
                  )}
                </div>

                <div className="l-card">
                  <div className="l-label">Hôm nay</div>
                  <div className="l-activity">
                    <div className="l-icon-box">
                      <BookOpen size={17} strokeWidth={1.9} aria-hidden />
                    </div>
                    <div>
                      <b>Từ vựng</b>
                      <small>10 phút</small>
                    </div>
                  </div>
                </div>

                <div className="l-card">
                  <div className="l-label">Tiếp theo</div>
                  <div className="l-activity">
                    <div className="l-icon-box">
                      <Headphones size={17} strokeWidth={1.9} aria-hidden />
                    </div>
                    <div>
                      <b>Nghe chép chính tả</b>
                      <small>Part 3</small>
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
            <div className="l-kicker">Vì sao học TOEIC hay thất bại</div>
            <h2>Biết phải học gì thôi thì chưa đủ.</h2>
            <p>
              Phần lớn người học không cần thêm một đống câu hỏi nữa. Họ cần một cách luyện đều đặn,
              và một dấu hiệu cho thấy công sức đang đưa mình đi lên.
            </p>
          </div>
          <div className="l-grid-3">
            {PROBLEMS.map((p, i) => (
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
            <div className="l-kicker">Một vòng học duy nhất</div>
            <h2>Học → luyện → tiến bộ.</h2>
            <p>
              TOEIC Pilot gom các hoạt động học hằng ngày vào một vòng học đơn giản, thay vì rải
              chúng ra nhiều công cụ khác nhau.
            </p>
          </div>
          <div className="l-loop">
            <div className="l-loop-visual">
              <div className="l-flow">
                {LOOP.map((s, i) => (
                  <div key={s.label} className="contents">
                    {i > 0 && (
                      <div className="l-arrow" aria-hidden>
                        <ArrowRight size={16} strokeWidth={2} />
                      </div>
                    )}
                    <div className="l-flow-item">
                      <div className="l-flow-box">
                        <s.Icon size={25} strokeWidth={1.6} aria-hidden />
                      </div>
                      <b>{s.label}</b>
                    </div>
                  </div>
                ))}
              </div>
              <div className="l-hr" />
              <div className="l-loop-foot">
                <span>Luyện mỗi ngày</span>
                <b>+ đều đặn</b>
              </div>
            </div>

            <div className="l-grid-2">
              {FEATURES.map((f) => (
                <article key={f.title} className="l-tile">
                  <div className="l-feature-icon">
                    <f.Icon size={21} strokeWidth={1.8} aria-hidden />
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
              <div className="l-kicker">Từ vựng</div>
              <h3>Học những từ bạn thật sự dùng được.</h3>
              <p>
                Học vốn từ có trọng tâm, kèm phát âm, định nghĩa và phần luyện tập — thay vì cố
                thuộc lòng một cuốn từ điển không có điểm dừng.
              </p>
              <Bullets items={["Từ vựng theo chủ đề", "Phát âm có audio", "Ôn tập tương tác"]} />
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
              <div className="l-kicker">Nghe chép chính tả</div>
              <h3>Rèn tai, không chỉ rèn trí nhớ.</h3>
              <p>Nghe tiếng Anh, dựng lại câu, và tìm ra những từ tai bạn vẫn còn bỏ sót.</p>
              <Bullets items={["Hiểu ý khi nghe", "Nhận mặt từ", "Luyện chính tả"]} />
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
              <div className="l-kicker">TOEIC Listening &amp; Reading</div>
              <h3>Luyện đúng định dạng bạn sắp thi.</h3>
              <p>
                Đi từ từng part tới trọn một đề. Luyện dưới áp lực thời gian và xem lại bài làm kèm
                giải thích rõ ràng.
              </p>
              <Bullets
                items={[
                  "Part 1 đến Part 7",
                  "Luyện có tính giờ",
                  "Trọn đề Listening & Reading",
                  "Có giải thích đáp án",
                ]}
              />
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
            <div className="l-kicker">Chất lượng nội dung</div>
            <h2>Máy sinh. Chuyên gia duyệt.</h2>
            <p>
              Quy trình nội dung được dựng để sinh bài luyện đúng định dạng TOEIC một cách hiệu quả,
              đồng thời luôn giữ người duyệt trong vòng lặp.
            </p>
          </div>
          <div className="l-pipeline">
            {PIPELINE.map((p, i) => (
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
            <b>Dựng để luyện, không phải để đi tắt.</b> TOEIC Pilot là nền tảng luyện thi độc lập.
            Nội dung luyện tập được xây dựng quanh định dạng đề TOEIC và không phải nội dung chính
            thức của ETS.
          </div>
        </div>
      </section>

      {/* ── Thú cưng ─────────────────────────────────────────────────────── */}
      <section className="l-section">
        <div className="l-container l-pet-layout">
          <PetlandMap className="l-pet-card" />
          <div>
            <div className="l-kicker">Một chút động lực thêm</div>
            <h3>Con thú sống ở góc màn hình — việc học vẫn ở chính giữa.</h3>
            <p className="l-pet-lead">
              Hệ thú cưng là một phần nhỏ và không bắt buộc. Bật lên khi bạn muốn thêm chút động lực
              kiểu trò chơi: hoàn thành thử thách từ vựng và nghe chép, kiếm Ruby, ấp trứng và sưu
              tầm bạn đồng hành mới.
            </p>
            <Bullets
              items={[
                "Góc thú cưng bật tắt tuỳ ý",
                "Kiếm Ruby từ chính việc học",
                "Ấp trứng và sưu tầm thú",
              ]}
            />
          </div>
        </div>

        {/* Nói "sưu tầm bạn đồng hành mới" mà không cho xem con nào thì người
            đọc không biết mình đang được mời sưu tầm cái gì. */}
        <div className="l-container l-species">
          <div className="l-tile">
            <div className="l-label">45 loài, sáu bậc hiếm</div>
            <div style={{ marginTop: 22 }}>
              <PetlandSpecies />
            </div>
          </div>
        </div>
      </section>

      {/* ── Dựng cho sự đều đặn ──────────────────────────────────────────── */}
      <section className="l-section l-alt">
        <div className="l-container">
          <div className="l-head">
            <div className="l-kicker">Dựng cho sự đều đặn</div>
            <h2>Những buổi ngắn cộng lại.</h2>
            <p>
              Thay vì chờ một buổi học hai tiếng hoàn hảo, hãy tiến bộ thật sự trong khoảng thời
              gian bạn thật sự có.
            </p>
          </div>
          <div className="l-grid-3">
            {HABITS.map((h) => (
              <article key={h.title} className="l-tile">
                <div className="l-feature-icon">
                  <h.Icon size={21} strokeWidth={1.8} aria-hidden />
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
          <div className="l-kicker">Sẵn sàng lúc nào cũng được</div>
          <h2>
            Điểm mục tiêu của bạn
            <br />
            bắt đầu từ buổi luyện hôm nay.
          </h2>
          <p>Xây vốn từ. Rèn tai nghe. Luyện đề TOEIC. Và thấy mình khá lên.</p>
          <div className="l-actions l-center">
            {status !== "loading" && (
              <Link className="l-btn l-btn-primary" href={cta.href}>
                {cta.label} <ArrowRight size={16} strokeWidth={2.5} aria-hidden />
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* ── Góc thú cưng nổi ─────────────────────────────────────────────── */}
      {/* Bản mẫu có nút nổi này để xem thử góc thú cưng mà không phải đăng nhập.
          Giữ nguyên, chỉ thay con rồng emoji bằng sprite thật của trò chơi. */}
      <button
        type="button"
        className="l-pet-toggle"
        aria-expanded={petOpen}
        onClick={() => setPetOpen((v) => !v)}
      >
        <PawPrint size={15} strokeWidth={2.2} aria-hidden /> Góc thú cưng
      </button>
      <div className={petOpen ? "l-pet-widget l-open" : "l-pet-widget"} aria-hidden={!petOpen}>
        <div className="l-pet-widget-head">
          <b>Góc thú cưng của bạn</b>
          <span className="l-ruby">◆ 320 Ruby</span>
        </div>
        <div className="l-pet-mini">
          <PetlandCreature name="Rồng lửa" size={72} />
        </div>
        <p className="l-pet-widget-foot">
          Học tiếp để kiếm Ruby.
          <small>Hoàn thành thử thách từ vựng và nghe chép để mở quả trứng tiếp theo.</small>
        </p>
      </div>
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
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

const PROBLEMS = [
  {
    title: "Lặp đi lặp lại thì chán",
    body: "Danh sách từ vựng và câu hỏi nối nhau khiến việc luyện hằng ngày thành một việc phải làm.",
  },
  {
    title: "Động lực nguội dần",
    body: "Điểm mục tiêu trông xa vời khi công sức của hôm nay không đổi lấy một phần thưởng nào thấy được.",
  },
  {
    title: "Không rõ mình tiến tới đâu",
    body: "Bạn luyện rất nhiều, nhưng khó thấy kỹ năng nào đang lên và bước tiếp theo nên là gì.",
  },
];

const LOOP = [
  { label: "Học", Icon: BookOpen },
  { label: "Luyện", Icon: Headphones },
  { label: "Tiến bộ", Icon: BarChart3 },
];

const FEATURES = [
  {
    title: "Từ vựng",
    body: "Xây vốn từ TOEIC thực dụng theo chủ đề và ôn lại đúng những từ bạn hay vấp.",
    Icon: BookOpen,
  },
  {
    title: "Nghe chép chính tả",
    body: "Nghe, gõ lại điều bạn nghe được, và rèn khả năng nhận mặt từ cùng độ chính xác khi nghe.",
    Icon: Headphones,
  },
  {
    title: "TOEIC LR",
    body: "Luyện từng Part 1–7, hoặc làm trọn một đề Listening & Reading.",
    Icon: PencilLine,
  },
  {
    title: "Tiến độ",
    body: "Theo dõi kết quả và hiểu bước tiến tiếp theo nên đến từ đâu.",
    Icon: Target,
  },
];

const PIPELINE = [
  {
    title: "Đặc tả TOEIC",
    body: "Định dạng, part, độ khó và yêu cầu nội dung được xác định trước tiên.",
  },
  {
    title: "Máy sinh nội dung",
    body: "Máy viết trọn phần nội dung luyện tập từ đầu.",
  },
  {
    title: "Kiểm tự động",
    body: "Các bước kiểm tự động soi cấu trúc, đáp án và những trường bắt buộc.",
  },
  {
    title: "Chuyên gia duyệt",
    body: "Người có chuyên môn tiếng Anh đọc lại toàn bộ trước khi xuất bản.",
  },
];

const HABITS = [
  {
    title: "Buổi 10–20 phút",
    body: "Nhét vừa từ vựng, nghe chép, hoặc một chặp luyện đề có trọng tâm vào ngày của bạn.",
    Icon: Clock,
  },
  {
    title: "Tiến độ nhìn thấy được",
    body: "Biến kết quả luyện tập thành bức tranh rõ hơn về điểm mạnh và điểm yếu.",
    Icon: BarChart3,
  },
  {
    title: "Giữ thói quen sống",
    body: "Phần thưởng hằng ngày và hệ thú cưng tuỳ chọn cho bạn thêm một lý do để quay lại.",
    Icon: Flame,
  },
];
