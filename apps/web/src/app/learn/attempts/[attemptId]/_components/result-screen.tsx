"use client";

import { type AttemptResult, type AttemptState, type QuestionPublic } from "@toeic-pilot/shared";

import { Button, ButtonLink, cx } from "@/components/ui";
import { groupQuestions } from "@/lib/attempt";
import { SkillRadar } from "./skill-radar";
import { formatDuration, Tally } from "./shared";

/** Màn kết quả sau khi nộp: điểm quy đổi và số câu đúng theo part. */

/**
 * Bảng kết quả sau khi nộp.
 *
 * Thay cho danh sách câu chứ không nằm đè lên nó: câu hỏi đầu tiên sau khi nộp
 * là "tôi được bao nhiêu", còn xem lại từng câu là việc thứ hai và có nút riêng.
 *
 * Điểm quy đổi chỉ hiện khi máy chủ THẬT SỰ gửi. `scoring.py` từ chối quy đổi
 * một đề rút gọn — bảng điểm dựng cho 200 câu, nên đề 40 câu tra vào đó sẽ chạm
 * sàn và in ra "Nghe 5 · Đọc 5" cho một người làm đúng 60%. Chỗ trống đó được
 * lấp bằng `scale_note` nói lý do, không phải bằng số 0.
 */
/**
 * Một thẻ điểm: nhãn, số lớn kèm thang của nó, một thanh mức, và chú thích.
 *
 * `max` không phải trang trí. Một số 750 trần không nói được nó nằm ở đâu trên
 * thang, còn "750/990" thì nói ngay — và thang của mỗi phần (495) khác thang
 * của tổng (990), thứ người học không có nghĩa vụ phải nhớ.
 */
function ScoreCard({
  label,
  value,
  max,
  ratio,
  note,
  coverage,
  strong,
}: {
  label: string;
  value: number;
  max: number;
  ratio: number;
  note: string;
  coverage?: { answered: number; total: number };
  strong?: boolean;
}) {
  const incomplete = coverage !== undefined && coverage.answered < coverage.total;
  return (
    <div
      className={cx(
        "flex flex-col rounded border p-5",
        strong ? "border-rule-strong bg-panel" : "border-rule bg-panel",
      )}
    >
      <p className="text-label uppercase text-ink-muted">{label}</p>
      <p className="mt-1 font-data tabular-nums">
        <span className={cx("font-semibold", strong ? "text-4xl text-action-ink" : "text-3xl")}>
          {value}
        </span>
        <span className="ml-1 text-small text-ink-faint">/{max}</span>
      </p>
      <div className="mt-3 h-1.5 overflow-hidden rounded-pill bg-recess">
        <div
          className={cx("h-full", strong ? "bg-action" : "bg-ok")}
          style={{ width: `${Math.max(0, Math.min(1, ratio)) * 100}%` }}
        />
      </div>
      <p className="mt-2 font-data text-label tabular-nums text-ink-muted">{note}</p>
      {coverage && (
        <p
          className={cx(
            "font-data text-label tabular-nums",
            incomplete ? "text-warn" : "text-ink-faint",
          )}
        >
          {coverage.answered}/{coverage.total} câu đã trả lời
        </p>
      )}
    </div>
  );
}

export function ResultScreen({
  result,
  state,
  onReview,
}: {
  result: AttemptResult;
  state: AttemptState;
  onReview: (target?: QuestionPublic) => void;
}) {
  const answered = state.questions.filter((q) => q.selected_option_id).length;
  const flagged = state.questions.filter((q) => q.flagged).length;
  const percent = result.question_count
    ? Math.round((result.correct_count / result.question_count) * 100)
    : 0;

  // Đúng/tổng theo từng part, tính từ chính danh sách câu — sau khi nộp mỗi câu
  // đã mang `correct_option_id`, nên không cần endpoint thống kê riêng.
  // Đã trả lời bao nhiêu câu của mỗi PHẦN. `section` do máy chủ gửi kèm từng
  // part, nên không phải bịa lại bảng "part nào thuộc phần Nghe" ở client —
  // đúng một chỗ biết luật đó và nó nằm ở `schemas/practice.py::section_of`.
  const sectionOf = new Map(state.parts.map((part) => [part.part, part.section]));
  const bySection = (name: string) => {
    const questions = state.questions.filter((q) => sectionOf.get(q.part) === name);
    return {
      answered: questions.filter((q) => q.selected_option_id).length,
      total: questions.length,
    };
  };
  const listening = bySection("listening");
  const reading = bySection("reading");

  // Cụm nào làm tệ nhất. "Part 7: 60%" không chỉ vào đâu cả; "câu 176-180: 1/5"
  // chỉ thẳng vào MỘT ngữ liệu để đọc lại. Chỉ xét cụm thật (từ 2 câu trở lên)
  // — Part 2 và 5 mỗi câu một mình, ở đó cụm không mang thêm thông tin gì.
  const weakSets = groupQuestions(state.questions)
    .filter((block) => block.questions.length > 1)
    .map((block) => {
      const correct = block.questions.filter(
        (q) => q.selected_option_id !== null && q.selected_option_id === q.correct_option_id,
      ).length;
      const answered = block.questions.filter((q) => q.selected_option_id !== null).length;
      const numbers = block.questions.map((q) => q.number);
      // Một dòng nhận ra được cụm. "Part 7" thì không: cả mười lăm cụm Part 7
      // đều tên như nhau, nên danh sách đọc ra như mười lăm dòng giống hệt và
      // không giúp quyết định quay lại cụm nào. `set_title` gần như luôn NULL,
      // nên lấy chính chữ người học đã đọc: câu mở đầu ngữ liệu với phần Đọc,
      // đề bài câu đầu với phần Nghe (ở đó ngữ liệu là âm thanh, không in ra).
      const passage = block.passages.find((item) => item.text)?.text ?? null;
      // Phần Nghe không in ngữ liệu, nhưng sau khi nộp thì lời thoại đã về —
      // và "Good afternoon. This is the personnel office…" nhận ra cuộc hội
      // thoại ngay, trong khi "Why are the speakers talking?" là đề bài dùng
      // chung cho hàng chục cụm.
      const spoken = block.transcript[0]?.text ?? null;
      const hint = passage ?? spoken ?? block.questions[0].prompt_text ?? block.title;
      return {
        key: block.key,
        first: block.questions[0],
        hint: hint ? hint.replace(/\s+/g, " ").trim().slice(0, 110) : null,
        part: block.questions[0].part,
        from: Math.min(...numbers),
        to: Math.max(...numbers),
        correct,
        answered,
        blank: block.questions.length - answered,
        count: block.questions.length,
      };
    })
    .filter((set) => set.correct < set.count)
    // Xếp theo tỉ lệ sai TRONG SỐ CÂU ĐÃ LÀM, không theo tỉ lệ đúng trên tổng.
    //
    // Một cụm bỏ trống vì hết giờ có "0/5" và sẽ leo lên đầu danh sách, đọc ra
    // như cụm khó nhất bài — trong khi người học chưa từng đọc nó. Đó là đúng
    // kiểu gộp "sai" với "chưa làm" mà thanh từng part vừa tách ra.
    .sort(
      (a, b) =>
        (a.answered ? a.correct / a.answered : 1) - (b.answered ? b.correct / b.answered : 1) ||
        a.from - b.from,
    );

  const scaled =
    result.total_scaled !== null &&
    result.listening_scaled !== null &&
    result.reading_scaled !== null;

  // Ngưỡng 5 câu, tối đa 8 dòng. Một dạng chỉ có 2-3 câu thì "1/2" là nhiễu
  // chứ không phải tín hiệu, và một bảng 33 dòng thì không ai đọc.
  const skills = (result.skills ?? []).filter((skill) => skill.count >= 5).slice(0, 8);
  // Dạng yếu nhất, nói thẳng bằng chữ. Hình đa giác cho thấy hồ sơ méo về đâu
  // nhưng không đọc ra được tên; một câu chữ thì đọc được ngay mà không cần
  // giải mã biểu đồ.
  const weakest = skills.reduce<(typeof skills)[number] | null>(
    (worst, skill) =>
      worst === null || skill.correct / skill.count < worst.correct / worst.count ? skill : worst,
    null,
  );

  const byPart = state.parts.map((part) => {
    const questions = state.questions.filter((q) => q.part === part.part);
    const correct = questions.filter(
      (q) => q.selected_option_id !== null && q.selected_option_id === q.correct_option_id,
    ).length;
    const answered = questions.filter((q) => q.selected_option_id !== null).length;
    // Sai và BỎ TRỐNG là hai chuyện khác nhau. Gộp chúng lại thì người bỏ dở
    // Part 7 vì hết giờ trông y hệt người đọc sai — một bên cần luyện tốc độ,
    // bên kia cần luyện đọc, và trang không phân biệt nổi.
    return {
      ...part,
      correct,
      answered,
      blank: questions.length - answered,
      count: questions.length,
    };
  });

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <p className="text-label uppercase text-ink-muted">Kết quả</p>
      <h1 className="mt-1 text-title">{state.test_title}</h1>

      {/*
       * Lưới ba thẻ CÙNG CHIỀU CAO, không phải một hàng số nằm cạnh nhau.
       *
       * Bản trước xếp năm ô vào một `flex items-end`: khi hai ô Nghe/Đọc có
       * thêm dòng độ phủ còn ba ô kia thì không, chúng cao thấp khác nhau và
       * cả hàng lệch. Lưới buộc mọi thẻ cao bằng nhau nên thêm bớt một dòng
       * không làm xô phần còn lại.
       */}
      <div className={cx("mt-6 grid gap-3", scaled ? "sm:grid-cols-3" : "sm:grid-cols-1")}>
        <ScoreCard
          label={scaled ? "Tổng quy đổi" : "Số câu đúng"}
          value={scaled ? result.total_scaled! : result.correct_count}
          max={scaled ? 990 : result.question_count}
          ratio={scaled ? result.total_scaled! / 990 : percent / 100}
          note={`${result.correct_count}/${result.question_count} câu đúng · ${percent}%`}
          strong
        />
        {scaled && (
          <ScoreCard
            label="Nghe"
            value={result.listening_scaled!}
            max={495}
            ratio={result.listening_scaled! / 495}
            note={`${result.listening_raw}/${listening.total} câu đúng`}
            coverage={listening}
          />
        )}
        {scaled && (
          <ScoreCard
            label="Đọc"
            value={result.reading_scaled!}
            max={495}
            ratio={result.reading_scaled! / 495}
            note={`${result.reading_raw}/${reading.total} câu đúng`}
            coverage={reading}
          />
        )}
      </div>

      <div className="mt-3 rounded border border-rule-strong bg-panel p-5">
        {/* Một thanh cho CẢ ĐỀ, cùng ba màu với thanh từng part bên dưới, nên
            mắt chuyển từ tổng thể xuống chi tiết mà không phải học lại bảng màu. */}
        <div className="flex h-2.5 overflow-hidden rounded-pill bg-recess">
          <div
            className="h-full bg-ok"
            style={{ width: `${(result.correct_count / result.question_count) * 100}%` }}
          />
          <div
            className="h-full bg-alert"
            style={{
              width: `${((answered - result.correct_count) / result.question_count) * 100}%`,
            }}
          />
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-5">
          <Tally label="Đúng" value={result.correct_count} />
          <Tally label="Sai" value={answered - result.correct_count} />
          <Tally
            label="Bỏ trống"
            value={result.question_count - answered}
            tone={answered < result.question_count ? "warn" : undefined}
          />
          <Tally label="Đã đánh dấu" value={flagged} />
          {/* Thời gian đi kèm THỜI LƯỢNG của đề. "1:47" một mình không nói được
              là vội hay thong thả; "1:47 / 2:00" thì nói được ngay. */}
          <Tally
            label="Thời gian"
            value={
              state.time_limit_seconds
                ? `${formatDuration(result.elapsed_seconds)} / ${formatDuration(state.time_limit_seconds)}`
                : formatDuration(result.elapsed_seconds)
            }
          />
        </dl>

        {answered < result.question_count && result.total_scaled !== null && (
          /*
           * Vì sao ghi chú này tồn tại, khi con số vẫn đúng công thức.
           *
           * TOEIC quy đổi số câu ĐÚNG ra thang 5–495 và không trừ điểm câu bỏ
           * trống, nên 0 câu đúng đúng là 5 điểm. Nhưng trong kỳ thi thật thí
           * sinh KHÔNG được rời phòng giữa chừng: một điểm Đọc bằng 5 luôn có
           * nghĩa "đã ngồi 75 phút và không đúng câu nào". Ở đây nộp sớm được,
           * nên cùng con số ấy có thể có nghĩa "chưa từng mở phần Đọc" — và
           * thang điểm không định nghĩa cho tình huống đó.
           */
          <p className="mt-4 rounded border border-warn bg-warn-tint p-3 text-small">
            Bài chưa làm hết {result.question_count} câu. Điểm quy đổi vẫn tính theo đúng công thức
            TOEIC, nhưng nó chỉ so sánh được với một bài làm đủ.
          </p>
        )}

        {result.scale_note && (
          <p className="mt-4 rounded border border-rule bg-recess p-3 text-small text-ink-muted">
            {result.scale_note}
          </p>
        )}
      </div>

      <section className="mt-8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-subtitle font-semibold">Theo từng phần</h2>
          {/* Thanh ba màu không tự giải thích được, và chú giải là thứ rẻ nhất
              để nó đọc được ngay. */}
          <p className="flex items-center gap-3 text-label text-ink-faint">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-pill bg-ok" />
              đúng
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-pill bg-alert" />
              sai
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-pill bg-recess ring-1 ring-rule" />
              bỏ trống
            </span>
          </p>
        </div>
        <div className="mt-3 space-y-2">
          {byPart
            .filter((part) => part.count > 0)
            .map((part) => {
              const share = part.count ? Math.round((part.correct / part.count) * 100) : 0;
              return (
                <div
                  key={part.part}
                  className="flex items-center gap-3 rounded border border-rule bg-panel px-3 py-2.5"
                >
                  {/* Hai dòng trong một cột đủ rộng, không phải một dòng trong
                      `w-28`: "Part 1 listening" tràn khỏi 112px và bị cắt giữa
                      chữ. Và tên part ("Conversations") nói được nhiều hơn tên
                      phần — số part đã cho biết nó thuộc Nghe hay Đọc rồi. */}
                  <span className="w-36 shrink-0 text-small font-semibold leading-tight">
                    Part {part.part}
                    <span className="block truncate font-normal text-ink-faint">{part.title}</span>
                  </span>
                  {/* Ba đoạn: đúng, sai, và phần nền còn lại là bỏ trống. Nền
                      `bg-recess` làm luôn đoạn thứ ba nên không cần vẽ nó. */}
                  <div className="flex h-2 min-w-0 flex-1 overflow-hidden rounded-pill bg-recess">
                    <div className="h-full bg-ok" style={{ width: `${share}%` }} />
                    <div
                      className="h-full bg-alert"
                      style={{
                        width: `${part.count ? ((part.answered - part.correct) / part.count) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="w-20 shrink-0 text-right font-data text-small tabular-nums">
                    {part.correct}/{part.count}
                  </span>
                  <span className="w-16 shrink-0 text-right font-data text-label tabular-nums text-warn">
                    {part.blank > 0 ? `${part.blank} trống` : ""}
                  </span>
                  <span className="w-12 shrink-0 text-right font-data text-small tabular-nums text-ink-muted">
                    {share}%
                  </span>
                </div>
              );
            })}
        </div>
      </section>

      {skills.length > 0 && (
        <section className="mt-8">
          <h2 className="text-subtitle font-semibold">Theo dạng câu</h2>
          <p className="mt-1 text-small text-ink-muted">
            Cùng một dạng câu xuất hiện ở nhiều part, nên tỉ lệ ở đây nói được điều mà tỉ lệ theo
            part không nói được.
            {weakest && (
              <>
                {" "}
                Yếu nhất:{" "}
                <span className="font-semibold text-ink">
                  {weakest.name.toLowerCase()} ({weakest.correct}/{weakest.count})
                </span>
                .
              </>
            )}
          </p>

          <div className="mt-4 grid items-center gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
            <div className="flex justify-center rounded border border-rule bg-panel p-2">
              <SkillRadar skills={skills} />
            </div>

            <div className="space-y-2">
              {skills.map((skill) => {
                const share = Math.round((skill.correct / skill.count) * 100);
                return (
                  <div
                    key={skill.name}
                    className="flex items-center gap-3 rounded border border-rule bg-panel px-3 py-2.5"
                  >
                    <span className="min-w-0 flex-1 text-small leading-snug">{skill.name}</span>
                    <div className="h-2 w-20 shrink-0 overflow-hidden rounded-pill bg-recess sm:w-32">
                      <div
                        className={cx("h-full", share >= 50 ? "bg-ok" : "bg-warn")}
                        style={{ width: `${share}%` }}
                      />
                    </div>
                    <span className="w-12 shrink-0 text-right font-data text-small tabular-nums">
                      {skill.correct}/{skill.count}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {weakSets.length > 0 && (
        <section className="mt-8">
          <h2 className="text-subtitle font-semibold">Cụm cần xem lại</h2>
          <p className="mt-1 text-small text-ink-muted">
            Xếp từ cụm mất nhiều câu nhất. Bấm một dòng để mở thẳng cụm đó ở phần xem lại.
          </p>
          <ul className="mt-3 space-y-1.5">
            {weakSets.slice(0, 8).map((set) => (
              <li key={set.key}>
                {/* Cả dòng là nút, không phải một dòng chữ có nút nhỏ ở cuối:
                    đích bấm càng lớn càng dễ trúng, và ở đây cả dòng nói về
                    đúng một thứ nên không có gì để bấm nhầm. */}
                <button
                  type="button"
                  onClick={() => onReview(set.first)}
                  className="flex w-full items-start gap-3 rounded border border-rule bg-panel px-3 py-2.5 text-left hover:border-rule-strong"
                >
                  <span className="w-24 shrink-0 font-data text-small tabular-nums">
                    Câu {set.from}–{set.to}
                  </span>
                  <span className="min-w-0 flex-1 text-small leading-snug text-ink-muted">
                    {set.hint ?? `Part ${set.part}`}
                  </span>
                  {set.blank > 0 && (
                    <span className="shrink-0 font-data text-label tabular-nums text-warn">
                      {set.blank} chưa làm
                    </span>
                  )}
                  <span
                    className={cx(
                      "w-10 shrink-0 text-right font-data text-small tabular-nums",
                      set.correct === 0 && set.answered > 0 ? "text-alert" : "text-ink",
                    )}
                  >
                    {set.correct}/{set.count}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {weakSets.length > 8 && (
            <p className="mt-2 text-label text-ink-faint">
              và {weakSets.length - 8} cụm nữa — xem hết ở phần chi tiết từng câu.
            </p>
          )}
        </section>
      )}

      <div className="mt-8 flex flex-wrap gap-2">
        <Button onClick={() => onReview()}>Xem chi tiết từng câu</Button>
        <ButtonLink href="/learn/tests" variant="secondary">
          Về danh sách đề
        </ButtonLink>
      </div>
    </div>
  );
}
