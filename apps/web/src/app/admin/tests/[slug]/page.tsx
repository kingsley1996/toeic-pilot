"use client";

import {
  API_ROUTES,
  type CollectionAdmin,
  type QuestionAdmin,
  type SetAdmin,
  type TurnDraft,
  type VoiceOption,
  type TestAdmin,
  type AudioRequestAck,
  type BulkPublishResult,
  type TestPartParseResponse,
} from "@toeic-pilot/shared";
import { ArrowLeft, AudioLines, CheckCheck, CircleAlert, Pencil, Send, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

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
import { ApiError, apiFetch } from "@/lib/api";
import { uploadAudio } from "@/lib/audio-upload";
import { uploadImage } from "@/lib/image-upload";
import { useRequireSession } from "@/lib/session";
import { AudioPanel } from "./_components/audio-panel";
import { CopyFormatButton } from "./_components/copy-format-button";
import { GroupPreview } from "./_components/group-preview";
import { ImageUpload } from "./_components/image-upload";
import { QuestionEditor } from "./_components/question-editor";
import { SetPanel } from "./_components/set-panel";

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

const PROVENANCE_LABELS = {
  source_url: "Nguồn ảnh",
  license: "Giấy phép",
  attribution: "Ghi công",
} as const;

const NO_COLLECTION = "__none__";

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
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const slug = params.slug;
  const { status, token, canPublish } = useRequireSession({ canEdit: true });

  const [test, setTest] = useState<TestAdmin | null>(null);
  const [collections, setCollections] = useState<CollectionAdmin[]>([]);
  const [sets, setSets] = useState<SetAdmin[]>([]);
  // Xuất xứ của những ảnh sắp tải lên, dùng chung cho cả lô — cùng khuôn với ô
  // chọn accent ngay bên cạnh. Ba trường này là NOT NULL và không có mặc định ở
  // bất kỳ tầng nào; đặt ở đầu trang để một bộ đề sáu ảnh Part 1 khai một lần
  // thay vì sáu lần, mà vẫn là người khai chứ không phải code đoán.
  //
  // `alt_text` KHÔNG ở đây: nó mô tả riêng từng bức, nên nó nằm trên từng ô.
  const [provenance, setProvenance] = useState({
    source_url: "",
    license: "",
    attribution: "",
  });
  // Danh sách giọng lấy từ server, không chép sang đây: hai bản sao sẽ trôi
  // khỏi nhau và người soạn chọn được một giọng rồi ăn 400 từ chính server
  // vừa gửi dropdown đó.
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  // Id của thứ đang chờ xác nhận xoá; `"test"` nghĩa là cả đề.
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  // Lời từ chối của lần xoá gần nhất, in TRONG hộp thoại. Băng lỗi chung nằm
  // ở đầu trang — tức là **sau lớp phủ của `<dialog>`**, nên một cú 409 ở đây
  // là hoàn toàn vô hình.
  const [deleteRefusal, setDeleteRefusal] = useState<string | null>(null);
  // Accent của bản thu sắp tải lên. Người học lọc nội dung theo nó, nên nó là
  // dữ liệu thật — và không ai ngoài người tải lên biết bản thu giọng gì.
  const [accent, setAccent] = useState("en-US");
  const [questions, setQuestions] = useState<QuestionAdmin[] | null>(null);
  // `null` = chưa chọn tay, tự suy ra. Trước đây đây là `useState(5)` cứng —
  // di tích của lượt 1, khi mới chỉ có Part 5, 6, 7. Hệ quả: mọi đề đều mở ra ở
  // Part 5, kể cả đề chỉ có nội dung Nghe, nên người soạn luôn nhìn vào một tab
  // trống và phải tự đoán mình đang thiếu gì.
  const [partOverride, setPartOverride] = useState<number | null>(null);
  const [raw, setRaw] = useState("");
  const [parsed, setParsed] = useState<TestPartParseResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Ba trường xuất xứ là NOT NULL ở `image_asset` và không có mặc định ở tầng
  // nào, nên thiếu bất kỳ trường nào là chưa tải lên được. Tính ở đây một lần
  // thay vì để mỗi ô tự hỏi.
  const missing = (["source_url", "license", "attribution"] as const).filter(
    (key) => !provenance[key].trim(),
  );
  const imagesBlocked = missing.length
    ? `Điền ${missing.map((key) => PROVENANCE_LABELS[key]).join(", ")} ở đầu trang trước khi tải ảnh.`
    : null;

  // Part đang xem: người soạn chọn gì thì theo nấy, chưa chọn thì mở ở part
  // ĐẦU TIÊN có câu. Suy ra chứ không ghi vào state qua effect —
  // `react-hooks/set-state-in-effect` chặn đúng lối tắt đó, và một state ghi từ
  // effect sẽ lệch pha với dữ liệu nó mô tả.
  const firstUsedPart = questions?.length
    ? Math.min(...questions.map((question) => question.part))
    : null;
  const part = partOverride ?? firstUsedPart ?? 1;

  const refresh = useCallback(
    (t: string) => {
      apiFetch<TestAdmin>(API_ROUTES.adminTest(slug), { token: t })
        .then(setTest)
        .catch(() => setError("Không mở được đề này."));
      apiFetch<QuestionAdmin[]>(API_ROUTES.adminTestQuestions(slug), { token: t })
        .then(setQuestions)
        .catch(() => {});
      apiFetch<CollectionAdmin[]>(API_ROUTES.adminTestCollections, { token: t })
        .then(setCollections)
        .catch(() => {});
      apiFetch<SetAdmin[]>(API_ROUTES.adminTestSets(slug), { token: t })
        .then(setSets)
        .catch(() => {});
      apiFetch<VoiceOption[]>(API_ROUTES.adminVoices, { token: t })
        .then(setVoices)
        .catch(() => {});
    },
    [slug],
  );

  useEffect(() => {
    if (token) refresh(token);
  }, [token, refresh]);

  // Trả về lời từ chối, `null` là thành công — chứ không nuốt kết quả. Form sửa
  // lời thoại cần cả hai: chỉ đóng khi server đã nhận (đóng dù thất bại là ném
  // đi đoạn hội thoại người ta vừa gõ, đúng lúc họ cần gõ lại nó nhất), và in
  // được lời từ chối NGAY CẠNH nút bấm. Băng lỗi chung nằm tận đầu trang, cách
  // form cả màn hình: bấm Lưu rồi thấy không có gì xảy ra thì không ai nghĩ tới
  // việc cuộn lên tìm.
  async function run<T>(work: () => Promise<T>, done?: (value: T) => void): Promise<string | null> {
    if (!token || busy) return "Đang bận.";
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      // `await work()` phải là CÂU LỆNH RIÊNG, không được nằm làm đối số của
      // `done?.(...)`.
      //
      // Optional call ngắt mạch cả đối số: khi `done` là `undefined`,
      // `done?.(await work())` bỏ qua luôn việc tính đối số, nên **`work()`
      // không bao giờ chạy** — mà hàm vẫn đi tiếp và `return null`, tức là báo
      // THÀNH CÔNG cho một việc chưa hề xảy ra.
      //
      // Nó chỉ cắn ở những lời gọi không truyền `done`, nên phần lớn màn hình
      // vẫn chạy đúng và lỗi ẩn rất lâu: nút Xoá đề báo "đã xoá" trong khi
      // database còn nguyên và server không nhận request nào.
      const value = await work();
      done?.(value);
      return null;
    } catch (problem) {
      const message = problem instanceof ApiError ? problem.message : "Có lỗi xảy ra.";
      setError(message);
      return message;
    } finally {
      setBusy(false);
    }
  }

  const parse = () =>
    run(
      () =>
        apiFetch<TestPartParseResponse>(API_ROUTES.adminTestPartParse(slug, part), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ raw_text: raw }),
        }),
      setParsed,
    );

  const commit = () =>
    run(
      () =>
        apiFetch<TestAdmin>(API_ROUTES.adminTestParts(slug), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ part, groups: parsed?.groups ?? [] }),
        }),
      (updated) => {
        setTest(updated);
        setParsed(null);
        setRaw("");
        setNotice(`Đã ghi vào Part ${part}. Nội dung ở trạng thái nháp cho tới khi xuất bản.`);
        if (token) refresh(token);
      },
    );

  const publishAllQuestions = () =>
    run(
      () =>
        apiFetch<BulkPublishResult>(API_ROUTES.adminTestPublishAllQuestions(slug), {
          method: "POST",
          token: token ?? undefined,
        }),
      (result) => {
        setTest(result.test);
        if (token) refresh(token);
        // Nói CẢ hai nửa. Chỉ in số câu đã xuất bản thì một đề 75 câu ra được
        // 73 sẽ đọc như đã xong, và hai câu còn lại chỉ lộ ra khi bấm "Xuất bản
        // đề" và ăn 409 — lúc đó lời từ chối nói "còn 2 câu" mà không nói vì sao.
        const done = `Đã xuất bản ${result.published_count} câu.`;
        if (result.skipped.length === 0) {
          setNotice(done);
          return;
        }
        const listed = result.skipped
          .slice(0, 3)
          .map((item) => `câu ${item.number} (${item.reason})`)
          .join("; ");
        const more = result.skipped.length > 3 ? ` và ${result.skipped.length - 3} câu nữa` : "";
        setNotice(`${done} Còn ${result.skipped.length} câu chưa đạt: ${listed}${more}.`);
      },
    );

  const publishQuestion = (id: string) =>
    run(
      () =>
        apiFetch<QuestionAdmin>(API_ROUTES.adminQuestionPublish(id), {
          method: "POST",
          token: token ?? undefined,
        }),
      () => token && refresh(token),
    );

  /*
   * Đổi tên gửi ĐÚNG một khoá. `PATCH /tests/{slug}` phân biệt khoá vắng mặt
   * với khoá bằng null, nên gửi kèm `collection_slug` hay `description` lấy từ
   * state trên màn hình sẽ biến một lệnh đổi tên thành một lệnh ghi đè — và
   * nếu state đang cũ hơn database thì nó lặng lẽ khôi phục giá trị cũ.
   */
  const rename = (title: string) =>
    run(
      () =>
        apiFetch<TestAdmin>(API_ROUTES.adminTest(slug), {
          method: "PATCH",
          token: token ?? undefined,
          body: JSON.stringify({ title }),
        }),
      setTest,
    );

  const moveToCollection = (target: string) =>
    run(
      () =>
        apiFetch<TestAdmin>(API_ROUTES.adminTest(slug), {
          method: "PATCH",
          token: token ?? undefined,
          // `null` là *gỡ khỏi bộ*, khác hẳn với không gửi khoá này. Chuỗi rỗng
          // của <select> phải được dịch sang null ở đây, nếu không nó sẽ đi
          // xuống dưới dạng "" và biến thành một slug không tồn tại.
          body: JSON.stringify({ collection_slug: target === NO_COLLECTION ? null : target }),
        }),
      setTest,
    );

  const saveQuestion = (id: string, changes: Record<string, unknown>) =>
    run(
      () =>
        apiFetch<QuestionAdmin>(API_ROUTES.adminQuestion(id), {
          method: "PATCH",
          token: token ?? undefined,
          body: JSON.stringify(changes),
        }),
      () => {
        setEditing(null);
        if (token) refresh(token);
      },
    );

  const saveSetScript = (setId: string, script: TurnDraft[]) =>
    run(
      () =>
        apiFetch<SetAdmin>(API_ROUTES.adminQuestionSet(setId), {
          method: "PATCH",
          token: token ?? undefined,
          body: JSON.stringify({ audio_script: script }),
        }),
      () => {
        setNotice("Đã lưu lời thoại. Cụm và các câu của nó quay về nháp.");
        if (token) refresh(token);
      },
    );

  const saveQuestionScript = (questionId: string, script: TurnDraft[]) =>
    run(
      () =>
        apiFetch<QuestionAdmin>(API_ROUTES.adminQuestion(questionId), {
          method: "PATCH",
          token: token ?? undefined,
          body: JSON.stringify({ audio_script: script }),
        }),
      () => {
        setNotice("Đã lưu lời thoại.");
        if (token) refresh(token);
      },
    );

  const uploadSetAudio = (setId: string, file: File) =>
    run(
      async () => {
        const asset = await uploadAudio(file, accent, token ?? "");
        return apiFetch<SetAdmin>(API_ROUTES.adminSetAudio(setId), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ asset_id: asset.id }),
        });
      },
      () => {
        if (token) refresh(token);
      },
    );

  const uploadQuestionAudio = (questionId: string, file: File) =>
    run(
      async () => {
        const asset = await uploadAudio(file, accent, token ?? "");
        return apiFetch<QuestionAdmin>(API_ROUTES.adminQuestionAudio(questionId), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ asset_id: asset.id }),
        });
      },
      () => {
        if (token) refresh(token);
      },
    );

  // Gỡ ảnh CHỈ tháo liên kết; hàng `image_asset` và object trên Cloudinary ở
  // lại. Xoá hẳn cần biết chắc không còn ai trỏ tới — ảnh là content-addressed
  // nên hai câu dùng chung một bức là chuyện bình thường, và xoá nhầm là mất
  // ảnh của một câu khác. Dọn file mồ côi là việc riêng, chạy ngoài luồng.
  const removeQuestionImage = (questionId: string) =>
    run(
      () =>
        apiFetch<QuestionAdmin>(API_ROUTES.adminQuestionImage(questionId), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ asset_id: null }),
        }),
      () => {
        if (token) refresh(token);
      },
    );

  const removePassageImage = (setId: string, slot: number) =>
    run(
      () =>
        apiFetch<SetAdmin>(API_ROUTES.adminPassageImage(setId), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ slot, image_id: null }),
        }),
      () => {
        if (token) refresh(token);
      },
    );

  const uploadQuestionImage = (questionId: string, file: File, alt: string | null) =>
    run(
      async () => {
        const asset = await uploadImage(file, { ...provenance, alt_text: alt }, token ?? "");
        return apiFetch<QuestionAdmin>(API_ROUTES.adminQuestionImage(questionId), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ asset_id: asset.id }),
        });
      },
      () => {
        if (token) refresh(token);
      },
    );

  const uploadPassageImage = (setId: string, slot: number, file: File, alt: string | null) =>
    run(
      async () => {
        const asset = await uploadImage(file, { ...provenance, alt_text: alt }, token ?? "");
        return apiFetch<SetAdmin>(API_ROUTES.adminPassageImage(setId), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ slot, image_id: asset.id }),
        });
      },
      () => {
        if (token) refresh(token);
      },
    );

  const archiveTest = (archived: boolean) =>
    run(
      () =>
        apiFetch<TestAdmin>(API_ROUTES.adminTestArchive(slug), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ archived }),
        }),
      () => {
        if (token) refresh(token);
      },
    );

  // KHÔNG tự chuyển hướng. Điều hướng ngầm là thứ nói dối được: nếu vì bất cứ
  // lý do gì mà lệnh xoá không chạy, người dùng vẫn thấy trang đổi và tin rằng
  // đề đã bị xoá — trong khi nó còn nguyên. Chuyển trang chỉ xảy ra khi người
  // dùng bấm, sau khi đã đọc kết quả.
  const deleteTest = async (force = false) => {
    const problem = await run(() =>
      apiFetch<void>(API_ROUTES.adminTest(slug) + (force ? "?force=true" : ""), {
        method: "DELETE",
        token: token ?? undefined,
      }),
    );
    setDeleteRefusal(problem);
    if (problem !== null) return;
    setConfirmDelete(null);
    router.push("/admin/tests");
  };

  const archiveQuestion = (questionId: string, archived: boolean) =>
    run(
      () =>
        apiFetch<QuestionAdmin>(API_ROUTES.adminQuestionArchive(questionId), {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({ archived }),
        }),
      () => {
        if (token) refresh(token);
      },
    );

  const deleteQuestion = (questionId: string, force = false) =>
    run(
      () =>
        apiFetch<void>(API_ROUTES.adminQuestion(questionId) + (force ? "?force=true" : ""), {
          method: "DELETE",
          token: token ?? undefined,
        }),
      () => {
        setConfirmDelete(null);
        if (token) refresh(token);
      },
    );

  // Từ chối xoá MỘT câu, in TRONG hộp thoại của chính câu đó — cùng lý do có
  // `deleteRefusal` cho đề: băng lỗi chung nằm sau lớp phủ `<dialog>`.
  const [questionDeleteRefusal, setQuestionDeleteRefusal] = useState<string | null>(null);

  const tryDeleteQuestion = async (questionId: string, force = false) => {
    const problem = await deleteQuestion(questionId, force);
    setQuestionDeleteRefusal(problem);
  };

  const requestAudio = () =>
    run(
      () =>
        apiFetch<AudioRequestAck>(API_ROUTES.adminAudioRequests, {
          method: "POST",
          token: token ?? undefined,
        }),
      (ack) =>
        setNotice(
          ack.queued
            ? "Đã xếp hàng. Worker sẽ sinh audio cho lời thoại còn thiếu — tải lại trang sau một lát."
            : "Chuông không tới được worker, nhưng vòng quét định kỳ vẫn sẽ tìm ra. Có thể mất vài phút.",
        ),
    );

  const publishTest = () =>
    run(
      () =>
        apiFetch<TestAdmin>(API_ROUTES.adminTestPublish(slug), {
          method: "POST",
          token: token ?? undefined,
        }),
      (updated) => {
        setTest(updated);
        setNotice("Đề đã được xuất bản.");
      },
    );

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
