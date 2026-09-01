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
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { uploadAudio } from "@/lib/audio-upload";
import { uploadImage } from "@/lib/image-upload";
import { useRequireSession } from "@/lib/session";

const PROVENANCE_LABELS = {
  source_url: "Nguồn ảnh",
  license: "Giấy phép",
  attribution: "Ghi công",
} as const;

export const NO_COLLECTION = "__none__";

/**
 * Toàn bộ state và hành động của màn sửa đề.
 *
 * Là một HOOK chứ không phải mấy component nhận props: mọi hành động ở đây đều
 * gói quanh cùng ba thứ — `run`, `refresh`, `setBusy` — nên chẻ thành component
 * sẽ phải luồn cả ba xuống từng nhánh, và đó đúng là loại đường nối mà mọi lỗi
 * frontend của dự án này từng nằm ở đó.
 *
 * Cái được là 16 định danh giờ KHÔNG với tới JSX nữa: `run`, `refresh`,
 * `setQuestions`, `setError`… trước đây nằm chung một phạm vi hơn nghìn dòng và
 * gọi được từ bất cứ đâu trong đó.
 *
 * Một chỗ trong `run` đã tốn một buổi truy và đừng "gọn lại": KHÔNG viết
 * `done?.(await work())`. Gọi tuỳ chọn short-circuit CẢ biểu thức, kể cả đối
 * số — không có `done` thì `work()` KHÔNG BAO GIỜ CHẠY, và hàm vẫn trả về như
 * thể đã xong.
 */
export function useTestEditor() {
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

  return {
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
  };
}
