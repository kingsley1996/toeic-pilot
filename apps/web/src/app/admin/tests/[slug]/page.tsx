"use client";

import { ArrowLeft, AudioLines, CheckCheck, CircleAlert, Pencil, Send, Trash2 } from "lucide-react";
import Link from "next/link";

import {
  Alert,
  Button,
  EmptyState,
  FieldError,
  Page,
  Field,
  Input,
  Panel,
  PublishTag,
  SectionHeader,
  Select,
  SkeletonList,
  Tag,
  Textarea,
  cx,
} from "@/components/ui";
import { InlineRename } from "@/components/admin-bits";
import { Modal } from "@/components/modal";
import { AudioPanel } from "./_components/audio-panel";
import { CopyFormatButton } from "./_components/copy-format-button";
import { GroupPreview } from "./_components/group-preview";
import { ImageUpload } from "./_components/image-upload";
import { QuestionEditor } from "./_components/question-editor";
import { SetPanel } from "./_components/set-panel";
import { NO_COLLECTION, useTestEditor } from "./_components/use-test-editor";

/*
 * Soạn một đề (ADR-007).
 *
 * Ba bước, không phải một: dán → xem trước → ghi. Bước xem trước tồn tại vì
 * `parse` **không ghi gì vào database** (ADR-005 §3.4), nên biên tập viên còn
 * cơ hội sửa trước khi có hàng nào được tạo — và đó cũng là lý do định dạng dán
 * là khối chứ không phải một dòng dài ngăn bằng dấu gạch đứng: dòng vài trăm ký
 * tự thì mắt người không soát được, mà soát được mới là điểm của bước này.
 */

/*
 * Soạn một đề (ADR-007).
 *
 * Ba bước, không phải một: dán → xem trước → ghi. Bước xem trước tồn tại vì
 * `parse` **không ghi gì vào database** (ADR-005 §3.4), nên biên tập viên còn
 * cơ hội sửa trước khi có hàng nào được tạo — và đó cũng là lý do định dạng dán
 * là khối chứ không phải một dòng dài ngăn bằng dấu gạch đứng: dòng vài trăm ký
 * tự thì mắt người không soát được, mà soát được mới là điểm của bước này.
 */

const PARTS = [1, 2, 3, 4, 5, 6, 7] as const;

// Part 1 và 2 KHÔNG in gì cả — ETS chỉ đọc lên — nên chúng không có ngữ liệu
// dùng chung, và phần chữ người soạn gõ vào là lời thoại (ADR-007 §2.1).
const UNPRINTED = [1, 2];

const LISTENING = [1, 2, 3, 4];

// Part 3, 4, 6, 7 gom nhiều câu dưới một ngữ liệu dùng chung (ADR-001 §A2).
const GROUPED = [3, 4, 6, 7];

// Các part có ảnh ở đâu đó: Part 1 trên câu, Part 3, 4, 7 trên cụm.
const WITH_IMAGES = [1, 3, 4, 7];

const PLACEHOLDER: Record<number, string> = {
  1: `[QUESTION]
voice: us_female_1
Look at the picture marked number one in your test book.
(A) The woman is sitting at a picnic table.
-> Người phụ nữ đang ngồi ở bàn dã ngoại.
(B) The woman is reading a newspaper.
-> Người phụ nữ đang đọc báo.
(C) The woman is loading a truck.
-> Người phụ nữ đang chất hàng lên xe tải.
(D) The woman is walking along a path.
-> Người phụ nữ đang đi bộ trên lối đi.
answer: A
source: original`,
  2: `[QUESTION]
voice: us_female_1
Where did you put the sales report?
voice: ca_male_1
(A) On your desk, next to the printer.
-> Trên bàn anh, cạnh máy in.
(B) Yes, I finished it last night.
-> Vâng, tôi làm xong tối qua.
(C) About thirty copies, I think.
-> Khoảng ba mươi bản, tôi nghĩ vậy.
answer: A
source: original`,
  3: `[SCRIPT] Hội thoại về đơn hàng ghế
voice: us_female_1
Hi, I'm calling about the office chairs we ordered last week.
voice: ca_male_1
I'm sorry about that. Let me pull up the tracking number.

[QUESTION]
What is the woman calling about?
(A) A late delivery
-> Giao hàng trễ
(B) A billing error
-> Sai sót hoá đơn
(C) A product return
-> Trả lại hàng
(D) A price change
-> Thay đổi giá
answer: A
source: original
explanation: Cô ấy gọi vì đơn ghế chưa tới.`,
  4: `[SCRIPT] Thông báo bảo trì sảnh
voice: uk_female_1
Attention, all tenants. Maintenance work on the lobby entrance
will begin this Wednesday and continue through Friday.

[QUESTION]
Where would this announcement most likely be heard?
(A) In an office building
-> Trong một toà nhà văn phòng
(B) At an airport
-> Ở sân bay
(C) In a factory
-> Trong một nhà máy
(D) At a school
-> Ở một trường học
answer: A
source: original`,
  5: `[QUESTION]
The board approved the ____ budget for the next quarter.
(A) annual
-> thường niên — tính từ
(B) annually
-> hằng năm — trạng từ
(C) annualize
-> quy đổi theo năm — động từ
(D) annuity
-> khoản niên kim — danh từ
answer: A
source: original
explanation: Cần một tính từ bổ nghĩa cho "budget".`,
  6: `[PASSAGE] Thư báo lịch bảo trì
Dear tenants,

The lobby entrance will be closed (131) ____ Wednesday. During this time,
please use the side entrance on Le Loi Street.

[QUESTION]
(131)
(A) since
-> từ khi — mốc quá khứ
(B) from
-> từ — mốc bắt đầu
(C) during
-> trong suốt
(D) until
-> cho đến khi
answer: B
source: original
explanation: "from + mốc thời gian" chỉ thời điểm bắt đầu.`,
  7: `[PASSAGE] Thông báo bảo trì
The lobby entrance will be closed from Wednesday.
Please use the side entrance on Le Loi Street.

[QUESTION]
What is the notice mainly about?
(A) A change of address
-> Thay đổi địa chỉ
(B) Building maintenance
-> Bảo trì toà nhà
(C) A new tenant
-> Một người thuê mới
(D) A rent increase
-> Tăng tiền thuê
answer: B
source: original
explanation: Đoạn văn nói về việc đóng cửa sảnh để bảo trì.`,
};

export default function AdminTestPage() {
  const {
    accent,
    archiveQuestion,
    archiveTest,
    busy,
    canPublish,
    collections,
    commit,
    confirmDelete,
    deleteRefusal,
    deleteTest,
    editing,
    error,
    imagesBlocked,
    moveToCollection,
    notice,
    parse,
    parsed,
    part,
    provenance,
    publishAllQuestions,
    publishQuestion,
    publishTest,
    questionDeleteRefusal,
    questions,
    raw,
    removePassageImage,
    removeQuestionImage,
    rename,
    requestAudio,
    saveQuestion,
    saveQuestionScript,
    saveSetScript,
    setAccent,
    setConfirmDelete,
    setDeleteRefusal,
    setEditing,
    setParsed,
    setPartOverride,
    setProvenance,
    setQuestionDeleteRefusal,
    setRaw,
    sets,
    status,
    test,
    tryDeleteQuestion,
    uploadPassageImage,
    uploadQuestionAudio,
    uploadQuestionImage,
    uploadSetAudio,
    voices,
  } = useTestEditor();

  if (status === "loading" || (test === null && error === null)) {
    return (
      <Page>
        <SkeletonList rows={4} />
      </Page>
    );
  }

  if (test === null) {
    return (
      <Page>
        <EmptyState
          icon={CircleAlert}
          title="Không mở được đề này"
          description={error ?? "Có thể nó đã bị gỡ."}
        />
      </Page>
    );
  }

  const inPart = (questions ?? []).filter((question) => question.part === part);
  const allPublished =
    (questions ?? []).length > 0 && (questions ?? []).every((q) => q.status === "published");

  return (
    <Page>
      <Link
        href="/admin/tests"
        className="inline-flex items-center gap-1.5 text-small font-semibold text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={14} strokeWidth={2} aria-hidden />
        Đề thi
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1>{test.title}</h1>
            <InlineRename
              value={test.title}
              label="this test"
              disabled={busy}
              onSave={(title) => void rename(title)}
            />
            <PublishTag status={test.status} />
          </div>
          <p className="mt-1 text-small text-ink-muted">
            <span className="font-data">{test.slug}</span> ·{" "}
            <span className="font-data tabular-nums">{test.question_count}</span> câu
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-small text-ink-muted">Thuộc bộ đề</span>
            <Select
              value={test.collection_slug ?? NO_COLLECTION}
              onChange={(event) => void moveToCollection(event.target.value)}
              disabled={busy}
              className="w-auto"
            >
              <option value={NO_COLLECTION}>— chưa thuộc bộ nào —</option>
              {collections.map((collection) => (
                <option key={collection.id} value={collection.slug}>
                  {collection.title}
                </option>
              ))}
            </Select>
            {/* Đề không thuộc bộ nào thì người học không có đường nào tới nó.
                Nói ra ở đây, vì nó trông y hệt một đề bình thường. */}
            {test.collection_slug === null && (
              <span className="text-small text-warn">Người học chưa nhìn thấy đề này</span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Nút này KHÔNG sinh audio — nó đánh chuông. API không sinh được
              (A4.1), nên câu chữ phải nói đúng thứ vừa xảy ra: đã xếp hàng.
              Viết "đã sinh audio" ở đây là hứa một thứ chưa xảy ra, và biên tập
              viên sẽ bấm Xuất bản ngay sau đó rồi ăn 409. */}
          <Button variant="secondary" onClick={() => void requestAudio()} disabled={busy}>
            <AudioLines size={14} strokeWidth={2} aria-hidden />
            Sinh audio còn thiếu
          </Button>
          {/* Xuất bản tất cả đứng TRƯỚC "Xuất bản đề", đúng thứ tự phải làm:
              nút kia bị khoá cho tới khi mọi câu đã ra, và tự tay bấm 75 lần là
              việc nút này tồn tại để bỏ đi.

              Điều kiện là `questions !== null`, không phải `(questions ?? [])`:
              danh sách chưa tải xong cũng cho `allPublished === false`, nên nút
              sẽ hiện ra trước khi ta biết có câu nào chưa xuất bản hay không —
              cùng cái bẫy ba trạng thái của phiên đăng nhập, thu nhỏ lại.

              Nó KHÔNG khoá theo `test.status`: một đề đã xuất bản vẫn nhận thêm
              part mới ở trạng thái nháp, và lúc đó nút "Xuất bản đề" đã ẩn đi
              rồi. Đúng chuyện đã xảy ra với `tp-form-06`. */}
          {canPublish && questions !== null && !allPublished && (
            <Button
              variant="secondary"
              onClick={() => void publishAllQuestions()}
              disabled={busy}
              title="Xuất bản mọi câu đạt cổng kiểm; câu chưa đạt sẽ được nêu tên"
            >
              <CheckCheck size={14} strokeWidth={2} aria-hidden />
              Xuất bản tất cả câu
            </Button>
          )}
          {canPublish && test.status !== "published" && (
            <Button
              onClick={() => void publishTest()}
              disabled={busy || !allPublished}
              title={
                allPublished
                  ? undefined
                  : "Còn câu chưa xuất bản — xuất bản từng câu trước, rồi mới xuất bản đề"
              }
            >
              <Send size={14} strokeWidth={2} aria-hidden />
              Xuất bản đề
            </Button>
          )}
          {/* Lưu trữ đứng NGAY CẠNH Xoá, không nằm đâu khác: lời từ chối 409
              chỉ sang `archived`, và một lối thoát chỉ có giá trị khi nó ở
              trong tầm tay người vừa bị từ chối. */}
          {canPublish && (
            <>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void archiveTest(test.status !== "archived")}
                disabled={busy}
              >
                {test.status === "archived" ? "Bỏ lưu trữ" : "Lưu trữ"}
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => {
                  setDeleteRefusal(null);
                  setConfirmDelete("test");
                }}
                disabled={busy}
              >
                <Trash2 size={14} strokeWidth={1.75} aria-hidden />
                Xoá đề
              </Button>
            </>
          )}
        </div>
      </div>

      <Modal
        open={confirmDelete === "test"}
        onClose={() => {
          setDeleteRefusal(null);
          setConfirmDelete(null);
        }}
        title={`Xoá đề ${test.title}?`}
        description={
          `${questions?.length ?? 0} câu hỏi và các cụm của chúng sẽ bị xoá theo. ` +
          "Đề đã có người làm thì không xoá được — lưu trữ thay vì xoá."
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="destructive" onClick={() => void deleteTest()} disabled={busy}>
            Xoá đề và {questions?.length ?? 0} câu
          </Button>
          <Button
            variant="quiet"
            onClick={() => {
              setDeleteRefusal(null);
              setConfirmDelete(null);
            }}
            disabled={busy}
          >
            Huỷ
          </Button>
        </div>

        {/* Lời từ chối phải in TRONG hộp thoại: băng lỗi chung nằm ở đầu trang,
            tức là sau lớp phủ của `<dialog>`, nên một cú 409 ở đó vô hình. Và
            nút Lưu trữ — thứ lời từ chối nêu tên — phải ở ngay cạnh nó, không
            phải ở đầu trang sau lớp phủ. */}
        {deleteRefusal && (
          <div className="mt-3">
            <FieldError>{deleteRefusal}</FieldError>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  const problem = await archiveTest(true);
                  if (problem === null) {
                    setDeleteRefusal(null);
                    setConfirmDelete(null);
                  }
                }}
                disabled={busy}
              >
                Lưu trữ đề thay vì xoá
              </Button>
              {/* Lối thoát cho giai đoạn dev: xoá cả lượt làm bài của tài khoản
                  thử. Server từ chối ở production, nên nút này vô hại khi lên
                  thật. */}
              <Button
                size="sm"
                variant="destructive"
                onClick={() => void deleteTest(true)}
                disabled={busy}
                title="Xoá đề cùng mọi lượt làm bài — chỉ dùng khi dọn dữ liệu thử"
              >
                Xoá cưỡng chế (mất lịch sử làm bài)
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {error && (
        <div className="mt-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}
      {notice && (
        <div className="mt-4">
          <Alert tone="ok">{notice}</Alert>
        </div>
      )}

      {/* Thanh part. Part 1–4 hiện ra nhưng khoá lại, chứ không giấu đi: giấu
          thì người soạn tưởng đề chỉ có ba phần và đó là thiết kế. */}
      <div className="mt-6 flex flex-wrap items-center gap-1.5">
        {PARTS.map((value) => {
          const summary = test.parts.find((p) => p.part === value);
          return (
            <button
              key={value}
              type="button"

              onClick={() => {
                setPartOverride(value);
                setParsed(null);
              }}

              className={cx(
                "inline-flex items-center gap-1.5 rounded border px-3 py-1.5 text-small font-semibold disabled:opacity-45",
                part === value
                  ? "border-rule-strong bg-recess text-action-ink"
                  : "border-rule bg-panel hover:border-rule-strong",
              )}
            >
              Part {value}
              {summary && (
                <span className="font-data tabular-nums text-label text-ink-faint">
                  {summary.published_count}/{summary.question_count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {LISTENING.includes(part) && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-small text-ink-muted">Accent của bản thu sắp tải lên</span>
          <Select value={accent} onChange={(e) => setAccent(e.target.value)} className="w-auto">
            <option value="en-US">Mỹ (en-US)</option>
            <option value="en-GB">Anh (en-GB)</option>
            <option value="en-AU">Úc (en-AU)</option>
            <option value="en-CA">Canada (en-CA)</option>
          </Select>
        </div>
      )}

      {WITH_IMAGES.includes(part) && (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Field label="Nguồn ảnh" hint="URL nơi giữ bản gốc.">
            <Input
              value={provenance.source_url}
              onChange={(e) => setProvenance({ ...provenance, source_url: e.target.value })}
            />
          </Field>
          <Field label="Giấy phép" hint="CC0, CC-BY, hoặc 'tự chụp'.">
            <Input
              value={provenance.license}
              onChange={(e) => setProvenance({ ...provenance, license: e.target.value })}
            />
          </Field>
          <Field label="Ghi công" hint="Tên tác giả hoặc nguồn.">
            <Input
              value={provenance.attribution}
              onChange={(e) => setProvenance({ ...provenance, attribution: e.target.value })}
            />
          </Field>
          {/* Nói ra ở ĐÂY, chỗ phải sửa — không chỉ ở nút tải lên, chỗ phát hiện
              ra vấn đề. Ba cột này NOT NULL và không có mặc định ở tầng nào. */}
          {imagesBlocked && (
            <p className="text-small text-warn sm:col-span-3">
              Cả ba trường đều bắt buộc — chưa đủ thì chưa tải ảnh lên được.
            </p>
          )}
        </div>
      )}

      <section className="mt-6">
        <SectionHeader
          title={`Dán nội dung Part ${part}`}
          aside={<CopyFormatButton template={PLACEHOLDER[part]} part={part} />}
        />
        {/* Mốc và khoá bằng tiếng Anh ASCII — dạng có dấu từng hỏng vì macOS
            trả chữ Â ở dạng phân rã, và hai chuỗi thì hiện lên giống hệt nhau.
            Nội dung `explanation` viết tiếng Việt vì người học đọc nó. */}
        <p className="mb-2 text-small text-ink-muted">
          Mốc và khoá viết bằng tiếng Anh: <span className="font-data">[PASSAGE]</span>,{" "}
          <span className="font-data">[QUESTION]</span>, <span className="font-data">answer:</span>,{" "}
          <span className="font-data">source:</span>,{" "}
          <span className="font-data">explanation:</span>. Phần giải thích thì viết tiếng Việt —
          người học sẽ đọc nó.
        </p>
        {/* Dòng dịch là tuỳ chọn nhưng phải nói ra ở đây: nó không có khoá đứng
            trước như các mốc kia, nên người soạn không đoán ra được nếu chỉ nhìn
            mẫu mà không đọc chú thích. */}
        <p className="mb-2 text-small text-ink-muted">
          Ngay dưới mỗi đáp án có thể thêm một dòng bắt đầu bằng{" "}
          <span className="font-data">-&gt;</span> để ghi bản dịch tiếng Việt của đáp án đó — tuỳ
          chọn, và học viên chỉ nhìn thấy nó ở chế độ luyện tập.
        </p>
        <Textarea
          value={raw}
          onChange={(event) => setRaw(event.target.value)}
          rows={12}
          className="font-data text-small"
          placeholder={PLACEHOLDER[part]}
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={() => void parse()} disabled={busy || !raw.trim()}>
            Phân tích
          </Button>
          {parsed && parsed.error_count === 0 && parsed.groups.length > 0 && (
            <Button onClick={() => void commit()} disabled={busy}>
              Ghi {parsed.groups.reduce((sum, g) => sum + g.questions.length, 0)} câu vào đề
            </Button>
          )}
        </div>

        {parsed && <GroupPreview parsed={parsed} />}
      </section>

      {GROUPED.includes(part) && (
        <section className="mt-10">
          <SectionHeader
            title={LISTENING.includes(part) ? `Lời thoại Part ${part}` : `Ngữ liệu Part ${part}`}
          />
          {sets.filter((stimulus) => stimulus.part === part).length === 0 ? (
            <p className="text-small text-ink-muted">Phần này chưa có cụm nào.</p>
          ) : (
            <div className="space-y-3">
              {sets
                .filter((stimulus) => stimulus.part === part)
                .map((stimulus) => (
                  <SetPanel
                    key={stimulus.id}
                    stimulus={stimulus}
                    busy={busy}
                    onUploadImage={(slot, file, alt) =>
                      uploadPassageImage(stimulus.id, slot, file, alt)
                    }
                    onRemoveImage={(slot) => removePassageImage(stimulus.id, slot)}
                    blocked={imagesBlocked}
                    // Chỉ Part 7 có ảnh. Part 6 là Text Completion — một đoạn
                    // văn có các chỗ trống, toàn chữ.
                    allowImages={part === 7}
                    onUploadAudio={(file) => void uploadSetAudio(stimulus.id, file)}
                    onSaveScript={(script) => saveSetScript(stimulus.id, script)}
                    voices={voices}
                  />
                ))}
            </div>
          )}
        </section>
      )}

      <section className="mt-10">
        <SectionHeader
          title={`Câu hỏi Part ${part}`}
          aside={
            <span className="text-small text-ink-muted">
              <span className="font-data tabular-nums">{inPart.length}</span> câu
            </span>
          }
        />
        {inPart.length === 0 ? (
          <p className="text-small text-ink-muted">Phần này chưa có câu nào.</p>
        ) : (
          <div className="space-y-2">
            {inPart.map((question) => (
              <Panel key={question.id} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-data tabular-nums font-semibold">
                        Câu {question.number}
                      </span>
                      <PublishTag status={question.status} />
                      <Tag>{question.source}</Tag>
                    </div>
                    {question.prompt_text ? (
                      <p className="mt-1.5 text-small">{question.prompt_text}</p>
                    ) : (
                      <p className="mt-1.5 text-small text-ink-faint">
                        Đọc lên, không in — nội dung ở lời thoại
                      </p>
                    )}
                    <ul className="mt-2 space-y-0.5">
                      {question.options.map((option) => (
                        <li
                          key={option.label}
                          className={cx(
                            "text-small",
                            option.is_correct ? "font-semibold text-ok" : "text-ink-muted",
                          )}
                        >
                          ({option.label}){option.content ? ` ${option.content}` : ""}
                        </li>
                      ))}
                    </ul>
                    {question.problems.map((problem) => (
                      <p
                        key={problem}
                        className="mt-1.5 flex items-center gap-1.5 text-small text-alert"
                      >
                        <CircleAlert size={14} strokeWidth={2} aria-hidden className="shrink-0" />
                        {problem}
                      </p>
                    ))}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      size="sm"
                      variant="quiet"
                      onClick={() => setEditing(editing === question.id ? null : question.id)}
                    >
                      <Pencil size={13} strokeWidth={2} aria-hidden />
                      {editing === question.id ? "Đóng" : "Sửa"}
                    </Button>
                    {canPublish && question.status !== "published" && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => void publishQuestion(question.id)}
                        disabled={busy || question.problems.length > 0}
                        title={
                          question.problems.length > 0
                            ? "Sửa các lỗi ở trên rồi mới xuất bản được"
                            : undefined
                        }
                      >
                        Xuất bản
                      </Button>
                    )}
                    {canPublish && (
                      <>
                        <Button
                          size="sm"
                          variant="quiet"
                          onClick={() =>
                            void archiveQuestion(question.id, question.status !== "archived")
                          }
                          disabled={busy}
                        >
                          {question.status === "archived" ? "Bỏ lưu trữ" : "Lưu trữ"}
                        </Button>
                        <Button
                          size="sm"
                          variant="quiet"
                          onClick={() => setConfirmDelete(question.id)}
                          disabled={busy}
                          aria-label={`Xoá câu ${question.number}`}
                        >
                          <Trash2 size={14} strokeWidth={1.75} aria-hidden />
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                <Modal
                  open={confirmDelete === question.id}
                  onClose={() => {
                    setQuestionDeleteRefusal(null);
                    setConfirmDelete(null);
                  }}
                  title={`Xoá câu ${question.number}?`}
                  // Số câu để lại chỗ trống chứ không dồn — nói ra, vì người
                  // soạn sẽ tự hỏi ngay và câu trả lời quyết định họ có dán lại
                  // được không.
                  description={
                    `Ô ${question.number} sẽ trống và lần dán sau lấy lại đúng ô đó; ` +
                    "các câu khác giữ nguyên số. Câu đã có người trả lời thì không xoá được."
                  }
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant="destructive"
                      onClick={() => void tryDeleteQuestion(question.id)}
                      disabled={busy}
                    >
                      Xoá câu {question.number}
                    </Button>
                    <Button
                      variant="quiet"
                      onClick={() => {
                        setQuestionDeleteRefusal(null);
                        setConfirmDelete(null);
                      }}
                      disabled={busy}
                    >
                      Huỷ
                    </Button>
                  </div>

                  {questionDeleteRefusal && (
                    <div className="mt-3">
                      <FieldError>{questionDeleteRefusal}</FieldError>
                      <div className="mt-2">
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => void tryDeleteQuestion(question.id, true)}
                          disabled={busy}
                          title="Xoá câu cùng các lượt trả lời nó — chỉ dùng khi dọn dữ liệu thử"
                        >
                          Xoá cưỡng chế (mất câu trả lời)
                        </Button>
                      </div>
                    </div>
                  )}
                </Modal>

                {/* Part 1 và 2: bản thu nằm trên CHÍNH câu, vì mỗi câu là một
                    clip riêng — không có cụm nào để treo nó lên (ADR-001 §A4.3). */}
                {UNPRINTED.includes(question.part) && (
                  <AudioPanel
                    script={question.audio_script}
                    audioUrl={question.audio_url ?? null}
                    stale={question.audio_may_be_stale}
                    attachedAt={question.audio_attached_at ?? null}
                    busy={busy}
                    voices={voices}
                    onUpload={(file) => void uploadQuestionAudio(question.id, file)}
                    onSaveScript={(script) => saveQuestionScript(question.id, script)}
                  />
                )}

                {question.part === 1 && (
                  <div className="mt-3 rounded border border-rule p-3">
                    <p className="text-label font-semibold uppercase text-ink-muted">Bức ảnh</p>
                    {question.image_url ? (
                      <>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={question.image_url}
                          alt=""
                          className="mt-2 h-28 w-40 rounded border border-rule object-cover"
                        />
                      </>
                    ) : (
                      <p className="mt-1 text-small text-warn">
                        Chưa có ảnh — Part 1 chưa xuất bản được.
                      </p>
                    )}
                    <ImageUpload
                      busy={busy}
                      hasImage={question.image_url !== null}
                      // Part 1 KHÔNG có chữ thay ảnh: bức ảnh chính là câu hỏi,
                      // nên mô tả nó là đưa luôn đáp án.
                      needsAlt={false}
                      blocked={imagesBlocked}
                      onUpload={(file, alt) => uploadQuestionImage(question.id, file, alt)}
                      onRemove={() => removeQuestionImage(question.id)}
                    />
                  </div>
                )}

                {editing === question.id && (
                  <QuestionEditor
                    question={question}
                    busy={busy}
                    onSave={(changes) => void saveQuestion(question.id, changes)}
                  />
                )}
              </Panel>
            ))}
          </div>
        )}
      </section>
    </Page>
  );
}
