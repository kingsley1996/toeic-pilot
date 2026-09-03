"use client";

import { type QuestionPublic } from "@toeic-pilot/shared";
import { Flag } from "lucide-react";

import { cx } from "@/components/ui";
import { type Block, credit } from "@/lib/attempt";
import { CoachBlock } from "@/components/coach-block";
import { ExplanationNote } from "./explanation-note";

/**
 * Ngữ liệu của một khối và các câu hỏi thuộc về nó.
 *
 * Không rẽ nhánh theo `review_mode` để quyết định hiển thị: cứ hiện thứ máy chủ
 * gửi. Đáp án đúng và lời thoại không tồn tại ở đây khi đang thi, nên không có
 * gì để lộ — quy tắc 3 của màn làm bài.
 */

export function StimulusBlock({
  block,
  done,
  attemptId,
  token,
  onView,
  onChoose,
  onFlag,
}: {
  block: Block;
  done: boolean;
  attemptId: string;
  token: string | null;
  onView: (number: number) => void;
  onChoose: (question: QuestionPublic, optionId: string) => void;
  onFlag: (question: QuestionPublic) => void;
}) {
  const questions = (
    <div className="space-y-4">
      {block.questions.map((question) => (
        <QuestionCard
          key={question.id}
          question={question}
          done={done}
          attemptId={attemptId}
          token={token}
          onView={onView}
          onChoose={onChoose}
          onFlag={onFlag}
        />
      ))}
    </div>
  );

  // Đánh số theo VỊ TRÍ TRONG DANH SÁCH, không theo `slot` ở database: ô rỗng
  // đã bị `_passages` lọc đi, nên một bộ dùng slot 1 và slot 3 phải đọc là
  // "Đoạn 1, Đoạn 2" — đúng thứ người học nhìn thấy. Đánh theo `slot` sẽ ra
  // "Đoạn 1, Đoạn 3" và người học đi tìm đoạn 2 không tồn tại.
  const numbered = block.passages.length > 1;

  // Không có ngữ liệu (Part 2, Part 5) thì không dựng lưới hai cột chỉ để bỏ
  // trống một nửa: một cột rỗng đọc như thứ đang tải dở.
  if (!block.hasStimulus) {
    return <section className="max-w-3xl">{questions}</section>;
  }

  return (
    <section className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-3 lg:sticky lg:top-32 lg:self-start">
        {block.title && <p className="text-small font-semibold text-ink-muted">{block.title}</p>}

        {/* Ảnh nằm ở object store ngoài, và `next/image` cần khai domain cho
            từng nhà cung cấp trong `next.config` — trong khi nhà cung cấp ở
            đây là một biến môi trường (ADR-006 §2.8). Nên dùng <img> thẳng. */}
        {block.imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={block.imageUrl}
            alt={block.imageAlt ?? ""}
            // Chặn chiều cao: ảnh Part 1 là ảnh dọc thì nó đẩy trình phát audio
            // xuống dưới màn hình, và người làm bài phải cuộn đi tìm nút Play ở
            // một phần thi tính bằng giây.
            className="max-h-[55vh] w-full rounded border border-rule object-contain"
          />
        )}

        {/* Ghi công là ĐIỀU KIỆN của giấy phép, không phải chú thích tuỳ chọn:
            ảnh CC-BY chỉ được dùng khi có ghi công (ADR-004 §4.2). Lưu vào
            database mà không hiện ra vẫn là vi phạm. */}
        {block.imageUrl && block.imageCredit && (
          <p className="text-label text-ink-faint">{block.imageCredit}</p>
        )}

        {block.audioUrl && (
          // `controls` gốc của trình duyệt, không tự dựng player: nó đã có tua,
          // âm lượng, tốc độ phát và phím tắt — và quan trọng hơn, nó đọc được
          // bằng trình đọc màn hình mà không cần ta làm gì thêm.
          /* `preload="metadata"`, không phải `"none"`: với `"none"` trình duyệt
             chưa tải header nên thanh phát hiện "0:00 / 0:00", và người làm bài
             không biết clip dài bao nhiêu trước khi bấm — thứ họ cần biết ở một
             bài thi có giới hạn giờ. Metadata chỉ vài KB, không phải cả file. */
          <audio src={block.audioUrl} controls preload="metadata" className="w-full">
            Trình duyệt của bạn không phát được audio.
          </audio>
        )}

        {block.transcript.length > 0 && (
          /* Đóng sẵn, không mở sẵn. Lời thoại về được nghĩa là người học đã trả
             lời xong, nhưng họ có thể muốn nghe lại lần nữa trước khi đọc — mở
             sẵn thì mắt đọc trước tai, và lần nghe lại đó mất giá trị. */
          <details className="rounded border border-rule bg-panel">
            <summary className="cursor-pointer select-none px-4 py-2 text-small font-medium">
              Full transcript
            </summary>
            <div className="space-y-2 border-t border-rule px-4 py-3">
              {block.transcript.map((turn, index) => (
                <p key={index} className="text-small leading-relaxed">
                  <span className="text-ink-faint">{turn.speaker}: </span>
                  {turn.text}
                </p>
              ))}
            </div>
          </details>
        )}

        {block.passages.map((passage, index) => (
          <article
            key={index}
            /* Nhãn cũng đi vào cây trợ năng, không chỉ lên màn hình: `article`
               là landmark điều hướng được, nên một bộ ba tài liệu nhảy qua lại
               được thay vì phải cuộn. Dùng `aria-label` chứ không dựng `<h2>` —
               màn làm bài không có heading nào khác, và một heading đơn độc
               không có h1 phía trên là một cây tiêu đề gãy. */
            aria-label={numbered ? `Đoạn ${index + 1}` : undefined}
            className="rounded border border-rule bg-panel p-4"
          >
            {/* Chỉ đánh số khi có từ hai đoạn trở lên. Một đoạn duy nhất mà đề
                "Đoạn 1" là thêm một dòng chữ không trả lời câu hỏi nào — còn từ
                hai đoạn thì câu hỏi bắt đầu nói "trong email thứ hai", và người
                học phải đối chiếu được. */}
            {numbered && (
              <p className="mb-2 border-b border-rule pb-1.5 text-label font-semibold uppercase text-ink-faint">
                Passage {index + 1}
              </p>
            )}
            {passage.text && (
              <p className="whitespace-pre-wrap text-small leading-relaxed">{passage.text}</p>
            )}
            {passage.image_url && (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={passage.image_url}
                  alt={passage.image_alt ?? ""}
                  className={cx(
                    "max-h-[60vh] w-full rounded border border-rule object-contain",
                    (passage.text || numbered) && "mt-3",
                  )}
                />
                {/* Ghi công là điều kiện của giấy phép ở MỌI nơi ảnh xuất hiện,
                    không riêng Part 1 (ADR-004 §4.2). */}
                {credit(passage.image_attribution, passage.image_license) && (
                  <p className="mt-1.5 text-label text-ink-faint">
                    {credit(passage.image_attribution, passage.image_license)}
                  </p>
                )}
              </>
            )}
          </article>
        ))}
      </div>

      {questions}
    </section>
  );
}

function QuestionCard({
  question,
  done,
  attemptId,
  token,
  onView,
  onChoose,
  onFlag,
}: {
  question: QuestionPublic;
  done: boolean;
  attemptId: string;
  token: string | null;
  onView: (number: number) => void;
  onChoose: (question: QuestionPublic, optionId: string) => void;
  onFlag: (question: QuestionPublic) => void;
}) {
  // Part 1 và 2 KHÔNG in đáp án — ETS chỉ đọc lên. `content` là NULL ở đó, và
  // đó là giá trị đúng chứ không phải dữ liệu thiếu, nên giao diện thu về những
  // ô chữ cái thay vì hiện bốn dòng trống.
  const lettersOnly = question.options.every((option) => option.content === null);
  // Chỉ khi đã lộ, máy chủ mới gửi kèm lời đọc và bản dịch — và ô chữ cái rộng
  // 48px không chứa nổi một câu, nên chữ tràn ra ngoài rồi đè lên ô bên cạnh.
  // Lộ rồi thì bố cục phải quay về danh sách đầy chiều ngang; ô chữ cái chỉ
  // đúng ở đúng trạng thái nó được dựng cho, là lúc chưa có gì để đọc.
  const spoken = question.options.some(
    (option) => option.spoken_text !== null || option.content_vi !== null,
  );
  const chips = lettersOnly && !spoken;

  return (
    <div
      id={`q-${question.number}`}
      // Bấm vào thẻ để đánh dấu đang xem câu này. Bỏ qua cú bấm phát ra từ một
      // nút bên trong — chọn đáp án hay đánh dấu có ý nghĩa riêng của chúng, và
      // để chúng nổi lên đây sẽ ghi đè lại đúng thứ vừa được xử lý.
      onClick={(event) => {
        if (!(event.target as HTMLElement).closest("button")) onView(question.number);
      }}
      className="scroll-mt-32 rounded border border-rule-strong bg-panel p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold">Câu {question.number}</p>
        <button
          type="button"
          onClick={() => onFlag(question)}
          disabled={done}
          aria-pressed={question.flagged}
          className={cx(
            "inline-flex items-center gap-1.5 rounded px-2 py-1 text-small font-semibold disabled:opacity-45",
            question.flagged ? "text-warn" : "text-ink-muted hover:text-ink",
          )}
        >
          <Flag
            size={14}
            strokeWidth={2}
            aria-hidden
            fill={question.flagged ? "currentColor" : "none"}
          />
          Đánh dấu
        </button>
      </div>

      {question.prompt_text && (
        <p className="mt-2 whitespace-pre-wrap leading-relaxed">{question.prompt_text}</p>
      )}

      <div className={cx("mt-3", chips ? "flex flex-wrap gap-2" : "space-y-2")}>
        {question.options.map((option) => {
          const chosen = question.selected_option_id === option.id;
          const correct = question.correct_option_id === option.id;
          // `correct_option_id` chỉ tồn tại ở chế độ Luyện tập hoặc sau khi nộp.
          // Không cần hỏi "đang ở chế độ nào" — nếu máy chủ không gửi thì
          // `revealed` là false và không có gì để lộ.
          const revealed = question.correct_option_id !== null;

          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onChoose(question, option.id)}
              disabled={done}
              aria-pressed={chosen}
              className={cx(
                "rounded border text-left disabled:cursor-default",
                chips ? "h-10 w-12 font-semibold" : "flex w-full items-start gap-3 p-3",
                revealed && correct
                  ? "border-ok bg-ok-tint text-ok"
                  : revealed && chosen
                    ? "border-alert bg-alert-tint text-alert"
                    : chosen
                      ? "border-action bg-action-tint text-action-ink"
                      : "border-rule bg-panel hover:border-rule-strong",
              )}
            >
              {chips ? (
                /*
                 * Part 1 và 2: lúc làm bài chỉ có chữ cái, vì đề thi không in
                 * gì — đọc được bốn câu trả lời thì phần kiểm kỹ năng NGHE
                 * không còn đo thứ nó định đo.
                 */
                <span className="block text-center">{option.label}</span>
              ) : (
                <>
                  <span
                    className={cx(
                      "grid h-6 w-6 shrink-0 place-items-center rounded border text-label font-semibold",
                      chosen || (revealed && correct) ? "border-current" : "border-rule-strong",
                    )}
                  >
                    {option.label}
                  </span>
                  <span className="min-w-0 leading-relaxed">
                    {option.content ?? option.spoken_text}
                    {/* Bản dịch xuống dòng riêng, cỡ nhỏ hơn: nó là chú thích
                        cho nguyên văn chứ không phải một đáp án thứ hai. Cùng
                        dòng thì mắt đọc thành một câu song ngữ dài. */}
                    {option.content_vi && (
                      <span className="mt-0.5 block text-small text-ink-muted">
                        {option.content_vi}
                      </span>
                    )}
                  </span>
                </>
              )}
            </button>
          );
        })}
      </div>

      {question.explanation && (
        <ExplanationNote
          text={question.explanation}
          correctLabel={
            question.options.find((option) => option.id === question.correct_option_id)?.label ??
            null
          }
        />
      )}

      {/*
       * Chỉ hiện SAU KHI NỘP, và chỉ cho câu làm sai hoặc bỏ trống.
       *
       * Trước khi nộp thì máy chủ trả 409 — nhưng giao diện không được dựa vào
       * đó: một nút bấm được rồi báo lỗi là một nút hứa sai. Và câu làm ĐÚNG thì
       * không có gì để chẩn đoán; đưa nút ra đó chỉ mời người ta đốt hạn mức.
       */}
      {done &&
        question.correct_option_id !== null &&
        question.selected_option_id !== question.correct_option_id && (
          <CoachBlock attemptId={attemptId} questionId={question.id} token={token} />
        )}
    </div>
  );
}
