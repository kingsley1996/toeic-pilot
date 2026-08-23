"use client";

import {
  API_ROUTES,
  type CollectionAdmin,
  type GroupDraft,
  type QuestionAdmin,
  type SetAdmin,
  type TurnDraft,
  type VoiceOption,
  type TestAdmin,
  type AudioRequestAck,
  type BulkPublishResult,
  type TestPartParseResponse,
} from "@toeic-pilot/shared";
import {
  ArrowLeft,
  AudioLines,
  Check,
  CheckCheck,
  CircleAlert,
  Copy,
  Pencil,
  Plus,
  Send,
  Trash2,
  Upload,
} from "lucide-react";
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
import { Modal } from "@/components/modal";
import { ApiError, apiFetch } from "@/lib/api";
import { uploadAudio } from "@/lib/audio-upload";
import { uploadImage } from "@/lib/image-upload";
import { useRequireSession } from "@/lib/session";

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
voice: uk_male_1
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
voice: us_male_1
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
voice: uk_male_1
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

function GroupPreview({ parsed }: { parsed: TestPartParseResponse }) {
  return (
    <Panel className="mt-4 overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-rule bg-recess px-4 py-2.5">
        <Tag tone="ok">{parsed.ok_count} cụm hợp lệ</Tag>
        {parsed.error_count > 0 && <Tag tone="alert">{parsed.error_count} cụm lỗi</Tag>}
        {/* Câu này phải nói ra, vì nó là toàn bộ lý do bước xem trước tồn tại. */}
        <span className="text-small text-ink-muted">Chưa có gì được ghi vào cơ sở dữ liệu</span>
      </div>
      <ul className="divide-y divide-rule">
        {parsed.groups.map((group) => (
          <GroupRow key={group.line} group={group} part={parsed.part} />
        ))}
      </ul>
    </Panel>
  );
}

function GroupRow({ group, part }: { group: GroupDraft; part: number }) {
  const broken = group.problems.length > 0 || group.questions.some((q) => q.problems.length > 0);
  // Part 1 và 2 không in gì; chữ của chúng nằm trong lời thoại bên dưới.
  const printed = part !== 1 && part !== 2;
  return (
    <li className={cx("px-4 py-3", broken && "bg-alert-tint/50")}>
      {group.title && <p className="text-small font-semibold">{group.title}</p>}

      {group.passages.map((passage, index) => (
        <p
          key={index}
          className="mt-1.5 line-clamp-3 whitespace-pre-wrap rounded border border-rule bg-recess p-2 text-small text-ink-muted"
        >
          {passage}
        </p>
      ))}

      {group.problems.map((problem) => (
        <p key={problem} className="mt-1.5 flex items-center gap-1.5 text-small text-alert">
          <CircleAlert size={14} strokeWidth={2} aria-hidden className="shrink-0" />
          {problem}
        </p>
      ))}

      {group.questions.map((question) => (
        <div key={question.line} className="mt-2.5 border-l-2 border-rule pl-3">
          <div className="flex items-start gap-2">
            <span className="w-6 shrink-0 text-right font-data text-small text-ink-faint">
              {question.line}
            </span>
            <div className="min-w-0 flex-1">
              {/* NULL là giá trị ĐÚNG ở Part 1/2, không phải dữ liệu thiếu — in
                  "thiếu đề bài" ở đó là báo lỗi cho một câu hoàn toàn ổn, ngay
                  tại bước người ta đang soát xem có gì sai không. */}
              {printed ? (
                <p className="text-small">{question.prompt_text || <em>thiếu đề bài</em>}</p>
              ) : (
                <p className="text-small text-ink-faint">Đọc lên, không in — xem Lời thoại</p>
              )}
              <p className="mt-0.5 text-small text-ink-muted">
                {question.options.map((option) => (
                  <span
                    key={option.label}
                    className={cx("mr-3", option.is_correct && "font-semibold text-ok")}
                  >
                    ({option.label}){option.content ? ` ${option.content}` : ""}
                  </span>
                ))}
              </p>
              {question.problems.map((problem) => (
                <p key={problem} className="mt-1 flex items-center gap-1.5 text-small text-alert">
                  <CircleAlert size={14} strokeWidth={2} aria-hidden className="shrink-0" />
                  {problem}
                </p>
              ))}
            </div>
          </div>
        </div>
      ))}
    </li>
  );
}

/**
 * Tải một bức ảnh lên NGAY TẠI Ô nó thuộc về.
 *
 * Thay cho luồng cũ: tải lên một thư viện chung rồi quay lại chọn từ dropdown.
 * Dropdown đó hỏng theo số lượng — hai chục ảnh là còn tìm được, hai trăm thì
 * nhãn duy nhất phân biệt được chúng là mười hai ký tự cuối của `storage_key`,
 * và chọn nhầm ảnh **khớp thành công**, không có gì báo.
 *
 * Xuất xứ (nguồn, giấy phép, ghi công) khai một lần ở đầu trang cho cả lô, vì
 * một bộ đề thường lấy ảnh từ cùng một nguồn. `alt_text` thì ở đây, vì nó mô tả
 * riêng bức này.
 */
function ImageUpload({
  busy,
  hasImage,
  needsAlt,
  blocked,
  onUpload,
  onRemove,
}: {
  busy: boolean;
  hasImage: boolean;
  needsAlt: boolean;
  /** Lý do chưa tải lên được, hoặc null. Xem `send`. */
  blocked: string | null;
  onUpload: (file: File, alt: string | null) => Promise<string | null>;
  onRemove: () => Promise<string | null>;
}) {
  const [alt, setAlt] = useState("");
  const [refusal, setRefusal] = useState<string | null>(null);

  async function send(file: File) {
    // Chặn TRƯỚC khi tải lên, không phải sau. Bước xác nhận từ chối thiếu xuất
    // xứ bằng 422, nhưng lúc đó file đã nằm trên Cloudinary rồi — và nó ở lại
    // đó, không ai trỏ tới, không ai biết để dọn.
    //
    // Luật này đã áp cho chữ thay ảnh ngay từ đầu; không áp cho xuất xứ là một
    // chỗ sót, và nó nổ ngay lần tải ảnh Part 1 đầu tiên.
    if (blocked) {
      setRefusal(blocked);
      return;
    }
    if (needsAlt && !alt.trim()) {
      setRefusal("Cần chữ thay ảnh trước khi tải lên.");
      return;
    }
    setRefusal(await onUpload(file, alt.trim() || null));
  }

  return (
    <div className="mt-2">
      {needsAlt && (
        <Field label="Chữ thay ảnh" hint="Mô tả nội dung hình. Bắt buộc.">
          <Input value={alt} onChange={(event) => setAlt(event.target.value)} />
        </Field>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <label className="inline-flex cursor-pointer items-center gap-2 text-small font-semibold text-action-ink">
          <Upload size={14} strokeWidth={2} aria-hidden />
          {hasImage ? "Thay ảnh" : "Tải ảnh lên"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
            disabled={busy}
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              // Xoá giá trị để chọn LẠI cùng một file vẫn kích hoạt onChange —
              // thứ người ta làm ngay sau một lần tải lên thất bại.
              event.target.value = "";
              if (file) void send(file);
            }}
          />
        </label>

        {hasImage && (
          <Button
            size="sm"
            variant="quiet"
            onClick={async () => setRefusal(await onRemove())}
            disabled={busy}
          >
            <Trash2 size={14} strokeWidth={1.75} aria-hidden />
            Gỡ ảnh
          </Button>
        )}
      </div>

      {refusal && <FieldError>{refusal}</FieldError>}
    </div>
  );
}

function CopyFormatButton({ template, part }: { template: string; part: number }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  /*
   * Sao chép CHÍNH chuỗi đang làm placeholder, không phải một bản mẫu viết
   * riêng: hai chuỗi mô tả cùng một định dạng thì sẽ lệch nhau, và bản lệch là
   * bản người ta dán vào — trong khi bản đúng là bản họ chỉ nhìn thấy mờ mờ.
   */
  async function copy() {
    try {
      // `navigator.clipboard` chỉ tồn tại ở secure context. Thiếu nó thì phải
      // NÓI RA chứ không im lặng không làm gì — cùng bài học với trình dán trả
      // về 0 cụm và 0 lỗi.
      if (!navigator.clipboard) throw new Error("no clipboard");
      // Chạy đua với đồng hồ, vì `writeText` có thể **không bao giờ settle**:
      // khi trình duyệt chặn (thiếu user activation, hoặc đang chờ một hộp xin
      // quyền không hiện ra), promise treo vô hạn. Không có nhánh nào chạy,
      // nút đứng im, và người dùng bấm lại vài lần rồi bỏ cuộc — đúng kiểu im
      // lặng mà trình dán vừa phải sửa. Đã gặp thật khi kiểm bằng trình duyệt.
      await Promise.race([
        navigator.clipboard.writeText(template),
        new Promise((_, reject) => window.setTimeout(() => reject(new Error("timeout")), 1500)),
      ]);
      setState("copied");
      window.setTimeout(() => setState("idle"), 2000);
    } catch {
      setState("failed");
      window.setTimeout(() => setState("idle"), 4000);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {state === "failed" && (
        <span className="text-small text-alert">Trình duyệt chặn — bấm vào ô mẫu rồi copy tay</span>
      )}
      <Button
        size="sm"
        variant="quiet"
        onClick={() => void copy()}
        title={`Chép mẫu định dạng Part ${part} vào clipboard`}
      >
        {state === "copied" ? (
          <>
            <Check size={14} strokeWidth={2} aria-hidden />
            Đã chép
          </>
        ) : (
          <>
            <Copy size={14} strokeWidth={2} aria-hidden />
            Chép mẫu
          </>
        )}
      </Button>
    </div>
  );
}

function SetPanel({
  stimulus,
  busy,
  onUploadImage,
  onRemoveImage,
  blocked,
  onUploadAudio,
  onSaveScript,
  voices,
  allowImages,
}: {
  stimulus: SetAdmin;
  busy: boolean;
  onUploadImage: (slot: number, file: File, alt: string | null) => Promise<string | null>;
  onRemoveImage: (slot: number) => Promise<string | null>;
  blocked: string | null;
  onUploadAudio: (file: File) => void;
  onSaveScript: (script: TurnDraft[]) => Promise<string | null>;
  voices: VoiceOption[];
  allowImages: boolean;
}) {
  // Part 6 chỉ có MỘT đoạn văn; hiện ba ô là mô tả sai format, và nó mời người
  // soạn điền vào hai ô không tồn tại trong đề thật.
  // Ba hình dạng, không phải hai. Part 7: tối đa ba ngữ liệu, chữ và ảnh. Part
  // 6: **một** đoạn văn, toàn chữ. Part 3/4: **một** hình dùng chung cho cả cụm
  // ("Look at the graphic") và không in chữ nào — nên hiện ô văn bản ở đó là mô
  // tả sai format và mời người soạn gõ vào chỗ đề thật để trống.
  const graphic = stimulus.part === 3 || stimulus.part === 4;
  const slots = allowImages ? stimulus.passages : stimulus.passages.slice(0, 1);

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-semibold">{stimulus.title ?? "Cụm không tên"}</p>
        <PublishTag status={stimulus.status} />
      </div>

      {!allowImages && stimulus.part <= 4 && (
        <AudioPanel
          script={stimulus.audio_script}
          audioUrl={stimulus.audio_url ?? null}
          stale={stimulus.audio_may_be_stale}
          attachedAt={stimulus.audio_attached_at ?? null}
          busy={busy}
          voices={voices}
          onUpload={onUploadAudio}
          onSaveScript={onSaveScript}
        />
      )}

      <div className={cx("mt-3 space-y-3", stimulus.part <= 2 && "hidden")}>
        {slots.map((passage) => (
          <div key={passage.slot} className="rounded border border-rule p-3">
            <p className="text-label font-semibold uppercase text-ink-muted">
              {graphic ? "Hình đi kèm" : `Ngữ liệu ${passage.slot}`}
            </p>

            {!graphic &&
              (passage.text ? (
                <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-small text-ink-muted">
                  {passage.text}
                </p>
              ) : (
                <p className="mt-1 text-small text-ink-faint">— không có văn bản —</p>
              ))}

            {passage.image_url && (
              <div className="mt-2 flex items-start gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={passage.image_url}
                  alt={passage.image_alt ?? ""}
                  className="h-20 w-28 rounded border border-rule object-cover"
                />
                <p className="min-w-0 flex-1 text-small text-ink-muted">{passage.image_alt}</p>
              </div>
            )}

            {(allowImages || graphic) && (
              <ImageUpload
                busy={busy}
                hasImage={passage.image_url !== null}
                // Ngược hẳn Part 1: ở đây ảnh LÀ ngữ liệu, nên thiếu chữ thay
                // ảnh là một câu người dùng máy đọc màn hình không làm được — mà
                // mô tả nó cũng không lộ gì, vì vẫn phải nghe (Part 3/4) hoặc
                // vẫn phải đọc phần còn lại (Part 7).
                needsAlt
                blocked={blocked}
                onUpload={(file, alt) => onUploadImage(passage.slot, file, alt)}
                onRemove={() => onRemoveImage(passage.slot)}
              />
            )}
          </div>
        ))}
      </div>

      {/* Nói ra ngay tại chỗ, vì đây là chỗ người ta sắp làm sai: phần lớn ngữ
          liệu KHÔNG cần ảnh, và bản văn bản thì tốt hơn thật. */}
      <p className={cx("mt-3 text-small text-ink-muted", stimulus.part <= 2 && "hidden")}>
        {graphic
          ? "Chỉ vài cụm cuối Part 3/4 có hình. Chữ thay ảnh là bắt buộc và không lộ đáp án ở đây — người học vẫn phải nghe mới trả lời được."
          : allowImages
            ? "Bảng giá, lịch trình, mẫu đơn nên viết thành văn bản — đọc được bằng máy đọc màn hình, phóng to và tìm kiếm được. Ảnh dành cho biểu đồ, sơ đồ, bản đồ."
            : "Part 6 là một đoạn văn có các chỗ trống, mỗi chỗ trống là một câu hỏi. Không có ảnh và không có bài nhiều đoạn."}
      </p>
    </Panel>
  );
}

function QuestionEditor({
  question,
  busy,
  onSave,
}: {
  question: QuestionAdmin;
  busy: boolean;
  onSave: (changes: Record<string, unknown>) => void;
}) {
  const [prompt, setPrompt] = useState(question.prompt_text ?? "");
  const [explanation, setExplanation] = useState(question.explanation ?? "");
  const [correct, setCorrect] = useState(
    question.options.find((option) => option.is_correct)?.label ?? "A",
  );
  const [options, setOptions] = useState<Record<string, string>>(
    Object.fromEntries(question.options.map((option) => [option.label, option.content ?? ""])),
  );
  const [translations, setTranslations] = useState<Record<string, string>>(
    Object.fromEntries(question.options.map((option) => [option.label, option.content_vi ?? ""])),
  );

  // Part 1 và 2 KHÔNG in gì cả, nên ở đó không có đề bài và không có nội dung
  // đáp án để sửa — chữ của chúng nằm trong lời thoại, sửa ở khung Lời thoại.
  //
  // Không phải chuyện gọn mắt: hai ô đó gửi `""` lên server, mà `""` không phải
  // NULL, nên `validate_question` từ chối và câu Part 1/2 nào cũng không lưu
  // nổi. Ẩn ô đi mà vẫn gửi khoá thì vẫn hỏng y hệt — nên khoá cũng bị bỏ khỏi
  // payload bên dưới.
  const printed = question.part !== 1 && question.part !== 2;

  return (
    <div className="mt-3 border-t border-rule pt-3">
      {printed && (
        <Field label="Đề bài">
          <Textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={2} />
        </Field>
      )}

      <div className="mt-3 space-y-2">
        {question.options.map((option) => (
          <div key={option.label} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCorrect(option.label)}
              aria-pressed={correct === option.label}
              title="Đặt làm đáp án đúng"
              className={cx(
                "grid h-8 w-8 shrink-0 place-items-center rounded border font-semibold",
                correct === option.label
                  ? "border-ok bg-ok-tint text-ok"
                  : "border-rule-strong text-ink-muted hover:border-ok",
              )}
            >
              {option.label}
            </button>
            {printed ? (
              <Input
                value={options[option.label] ?? ""}
                onChange={(event) => setOptions({ ...options, [option.label]: event.target.value })}
              />
            ) : (
              <span className="text-small text-ink-faint">
                {/* Part 1/2 không in đáp án, nhưng LỜI ĐỌC thì có — hiện nó ở
                    đây để người soạn biết mình đang dịch câu nào. */}
                {option.spoken_text ?? "đọc lên, không in — sửa ở khung Lời thoại"}
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="mt-3 space-y-2">
        {/*
         * Bản dịch tách thành một khối riêng, không xen giữa các đáp án.
         *
         * Xen vào thì hàng đáp án dài gấp đôi và việc hay làm nhất — soát xem
         * đáp án đúng đã chọn chưa — bị đẩy ra xa nhau. Ở đây người soạn dịch
         * cả bốn câu một lượt, đúng nhịp thật của việc dịch.
         *
         * Hiện ở MỌI part, khác ô nội dung: Part 1/2 không in đáp án nhưng vẫn
         * có lời đọc để dịch, và bản dịch đó hiện cho học viên ở chế độ Luyện tập.
         */}
        <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
          Dịch nghĩa từng đáp án
        </p>
        {question.options.map((option) => (
          <div key={option.label} className="flex items-center gap-2">
            <span className="w-8 shrink-0 text-center font-data text-small text-ink-faint">
              {option.label}
            </span>
            <Input
              value={translations[option.label] ?? ""}
              placeholder="để trống nếu chưa dịch"
              aria-label={`Dịch nghĩa đáp án ${option.label}`}
              onChange={(event) =>
                setTranslations({ ...translations, [option.label]: event.target.value })
              }
            />
          </div>
        ))}
      </div>

      <div className="mt-3">
        <Field label="Giải thích" hint="Viết tiếng Việt — người học sẽ đọc nó.">
          <Textarea
            value={explanation}
            onChange={(event) => setExplanation(event.target.value)}
            rows={2}
          />
        </Field>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          onClick={() =>
            onSave(
              // `exclude_unset` ở server phân biệt "vắng mặt" với "null", nên
              // với Part 1/2 phải BỎ HẲN hai khoá này — gửi `""` là ghi một
              // chuỗi rỗng vào cột buộc phải NULL, và câu sẽ không lưu được.
              printed
                ? {
                    prompt_text: prompt,
                    explanation: explanation || null,
                    correct_label: correct,
                    options,
                    translations,
                  }
                : {
                    explanation: explanation || null,
                    correct_label: correct,
                    // `translations` đi kèm CẢ ở Part 1/2, khác `options`: chỗ
                    // này dịch lời đọc, và lời đọc thì hai part đó có.
                    translations,
                  },
            )
          }
          disabled={busy}
        >
          Lưu
        </Button>
        {/* Sửa một câu đã xuất bản sẽ đưa nó về nháp, và người soạn phải biết
            trước khi bấm — không phải phát hiện sau khi cái badge đổi màu. */}
        {question.status === "published" && (
          <span className="text-small text-warn">Lưu xong câu này quay về trạng thái nháp</span>
        )}
      </div>
    </div>
  );
}

/**
 * Lời thoại và bản thu của một câu (Part 1, 2) hoặc một cụm (Part 3, 4).
 *
 * Lời thoại hiện ra ngay cạnh nút tải lên, vì đó là thứ người soạn phải đối
 * chiếu: `media_state` KHÔNG xác minh được audio tải lên — hash của nó băm một
 * id ngẫu nhiên nên không suy ngược ra text — nên mắt người là lớp kiểm duy
 * nhất còn lại (ADR-007 §2.7).
 *
 * Và nó phải SỬA được ngay tại đây. Không có ô sửa thì sai một chữ chỉ còn cách
 * xoá cả cụm rồi dán lại — kéo theo mất số câu đã cấp và bản thu đã gắn.
 */
function AudioPanel({
  script,
  audioUrl,
  stale,
  attachedAt,
  busy,
  voices,
  onUpload,
  onSaveScript,
}: {
  script: TurnDraft[];
  audioUrl: string | null;
  stale: boolean;
  attachedAt: string | null;
  busy: boolean;
  voices: VoiceOption[];
  onUpload: (file: File) => void;
  onSaveScript: (script: TurnDraft[]) => Promise<string | null>;
}) {
  // `null` nghĩa là không sửa. Một cờ boolean riêng cạnh bản nháp sẽ có hai
  // nguồn sự thật cho cùng một câu hỏi, và chúng lệch nhau được.
  const [draft, setDraft] = useState<TurnDraft[] | null>(null);
  // Lời từ chối của lần lưu gần nhất, in ngay dưới nút Lưu. Băng lỗi chung ở
  // đầu trang vẫn hiện, nhưng nó cách chỗ này cả màn hình.
  const [refusal, setRefusal] = useState<string | null>(null);
  const fallbackVoice = voices[0]?.name ?? "us_female_1";

  const patch = (index: number, turn: Partial<TurnDraft>) =>
    setDraft((current) =>
      (current ?? []).map((item, at) => (at === index ? { ...item, ...turn } : item)),
    );

  async function save() {
    if (!draft) return;
    // Đóng CHỈ khi server đã nhận. Giọng sai hay lượt rỗng đều bị từ chối ở
    // server, và lời từ chối đó vô dụng nếu ô nhập đã biến mất cùng nội dung.
    const problem = await onSaveScript(draft);
    setRefusal(problem);
    if (problem === null) setDraft(null);
  }

  return (
    <div className="mt-3 rounded border border-rule p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-label font-semibold uppercase text-ink-muted">Lời thoại</p>
        {draft === null && (
          <Button
            size="sm"
            variant="quiet"
            onClick={() => {
              setRefusal(null);
              setDraft(script.map((t) => ({ ...t })));
            }}
          >
            <Pencil size={14} strokeWidth={1.75} aria-hidden />
            Sửa
          </Button>
        )}
      </div>

      {draft === null ? (
        script.length === 0 ? (
          <p className="mt-1 text-small text-ink-faint">— chưa có lời thoại —</p>
        ) : (
          <ul className="mt-1.5 space-y-1">
            {script.map((turn, index) => (
              <li key={index} className="text-small">
                <span className="font-data text-label text-ink-faint">{turn.voice}</span>{" "}
                {turn.text}
              </li>
            ))}
          </ul>
        )
      ) : (
        <div className="mt-2 space-y-2">
          {draft.map((turn, index) => (
            <div key={index} className="flex items-start gap-2">
              {/* Bề rộng đặt ở lớp bọc, không đặt lên chính control: `CONTROL`
                  đã có `w-full`, và hai lớp width cùng tồn tại thì thứ tự trong
                  file CSS quyết định chứ không phải thứ tự viết ở đây — nên
                  `w-40` trên `<Select>` thua im lặng và ô nhập bị bóp còn vài
                  pixel. */}
              <div className="w-44 shrink-0">
                <Select
                  value={turn.voice}
                  aria-label={`Giọng của lượt ${index + 1}`}
                  onChange={(event) => patch(index, { voice: event.target.value })}
                >
                  {/* Giọng hiện tại luôn có mặt, kể cả khi nó đã bị gỡ khỏi danh
                    sách: một option biến mất sẽ lặng lẽ đổi giọng của lượt này
                    sang giọng đầu bảng khi người ta lưu. */}
                  {!voices.some((voice) => voice.name === turn.voice) && (
                    <option value={turn.voice}>{turn.voice}</option>
                  )}
                  {voices.map((voice) => (
                    <option key={voice.name} value={voice.name}>
                      {voice.name} · {voice.accent}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="min-w-0 flex-1">
                <Textarea
                  rows={2}
                  value={turn.text}
                  aria-label={`Lời của lượt ${index + 1}`}
                  onChange={(event) => patch(index, { text: event.target.value })}
                />
              </div>
              <Button
                size="sm"
                variant="quiet"
                aria-label={`Xoá lượt ${index + 1}`}
                onClick={() => setDraft(draft.filter((_, at) => at !== index))}
              >
                <Trash2 size={14} strokeWidth={1.75} aria-hidden />
              </Button>
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="quiet"
              onClick={() => setDraft([...draft, { text: "", voice: fallbackVoice }])}
            >
              <Plus size={14} strokeWidth={1.75} aria-hidden />
              Thêm lượt
            </Button>
            <Button size="sm" onClick={() => void save()} disabled={busy}>
              Lưu lời thoại
            </Button>
            <Button
              size="sm"
              variant="quiet"
              onClick={() => {
                setRefusal(null);
                setDraft(null);
              }}
              disabled={busy}
            >
              Huỷ
            </Button>
          </div>
          {refusal ? (
            <FieldError>{refusal}</FieldError>
          ) : (
            <p className="text-small text-ink-faint">
              Lưu xong, nội dung quay về nháp — bản thu đang gắn ứng với lời thoại cũ.
            </p>
          )}
        </div>
      )}

      {audioUrl ? (
        <audio src={audioUrl} controls preload="metadata" className="mt-3 w-full" />
      ) : (
        <p className="mt-3 text-small text-warn">Chưa có bản thu — chưa xuất bản được.</p>
      )}

      {/* Cảnh báo chứ không chặn. Hash của file tải lên không suy ngược ra lời
          thoại, nên không có cách nào biết CHẮC là nó lệch — chỉ biết lời thoại
          đã đổi kể từ lúc gắn, và nói ra điều đó vẫn hơn im lặng. */}
      {stale && (
        <p className="mt-2 text-small text-warn">
          Lời thoại đã đổi sau khi gắn bản thu
          {attachedAt && ` (gắn lúc ${new Date(attachedAt).toLocaleString("vi-VN")})`} — nghe lại
          hoặc thu lại cho khớp.
        </p>
      )}

      <label className="mt-3 inline-flex cursor-pointer items-center gap-2 text-small font-semibold text-action-ink">
        <Upload size={14} strokeWidth={2} aria-hidden />
        {audioUrl ? "Thay bản thu" : "Tải bản thu lên"}
        <input
          type="file"
          accept="audio/mpeg,audio/mp4,audio/wav,.mp3,.m4a,.wav"
          disabled={busy}
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Xoá giá trị để chọn LẠI cùng một file vẫn kích hoạt onChange —
            // thứ người ta làm ngay sau khi một lần tải lên thất bại.
            event.target.value = "";
            if (file) onUpload(file);
          }}
        />
      </label>
    </div>
  );
}
