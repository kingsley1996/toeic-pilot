"use client";

import { API_ROUTES } from "@toeic-pilot/shared";
import { Check, CircleCheck } from "lucide-react";
import { useId, useRef, useState } from "react";

import { Alert, Button, Kbd, Panel, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { cheer } from "@/lib/pet-cheer";
import { notifyStudyReward } from "@/lib/pet-notice";
import { useSession } from "@/lib/session";
import { useToast } from "@/lib/toast";
import {
  annotateTyped,
  grade,
  maskMissing,
  normalise,
  wrongSubmittedIndices,
  type GradeResult,
  type WordResult,
} from "@/lib/dictation";

/*
 * Xanh = đúng, cam = chưa đúng. Nhưng "chưa đúng" có hai vai trò:
 *
 *   missing — từ CỦA ĐÁP ÁN mà người học chưa gõ ra. Che thành `*` (xem
 *             `maskMissing`): lần chấm không được biến thành đáp án, nhất là
 *             khi bỏ trống một từ rồi gõ tiếp các từ sau.
 *   extra   — từ HỌ ĐÃ GÕ nhưng không có trong đáp án. Đây là cái sai, nên
 *             mang gạch bỏ — gạch bỏ phải nằm trên thứ mình muốn xoá đi.
 *
 * Dòng đối chiếu vì thế đọc được thành câu: "… make ~~maek~~" = phải là *make*,
 * bạn gõ *maek*.
 */
/** Số từ giữa hai chỗ trống: ít = 1/4 câu, nhiều = 1/2 câu. */
const BLANK_STEP: Record<Exclude<Difficulty, "full">, number> = { few: 4, many: 2 };

/** `true` = từ đó để trống cho người học gõ; `false` = hiện sẵn làm mốc. */
function blankMask(wordCount: number, difficulty: Difficulty): boolean[] {
  const step = difficulty === "full" ? 1 : BLANK_STEP[difficulty];
  return Array.from({ length: wordCount }, (_, index) => index % step === 0);
}

/** Các ô của một câu mới: từ hiện sẵn được điền luôn, chỗ trống bắt đầu rỗng. */
function seedBoxes(words: string[], difficulty: Difficulty): string[] {
  const blanks = blankMask(words.length, difficulty);
  return words.map((word, index) => (blanks[index] ? "" : word));
}

/**
 * Gợi ý chữ đầu: giữ chữ đầu và mọi dấu câu, mỗi CHỮ cái sau thành một dấu sao.
 *
 * Dấu câu không bị đếm thành sao — `night.` phải là `n****.` (bốn chữ còn lại),
 * không phải `n*****`; dấu sao thừa ở cuối câu từng làm gợi ý trông như đếm sai.
 * Chữ đầu được đánh dấu để tô màu riêng, tách hẳn khỏi phần còn thiếu.
 */
function firstLetterHint(word: string): Array<{ char: string; revealed: boolean }> {
  let shown = false;
  return Array.from(word).map((char) => {
    if (!/[\p{L}\p{N}]/u.test(char)) return { char, revealed: false };
    if (shown) return { char: "*", revealed: false };
    shown = true;
    return { char, revealed: true };
  });
}

/**
 * Đối chiếu TỪNG Ô với đúng từ ở vị trí đó.
 *
 * Chấm cả câu bằng chuỗi gộp (`boxes.join(" ")`) là đúng cho việc lưu và cho
 * "đúng chưa", nhưng sai cho việc tô từng ô: gõ đúng từ nhưng lệch ô thì chuỗi
 * vẫn khớp ở vị trí khác, và ô trống lại được tô xanh. Ở chế độ điền từng từ,
 * mỗi ô là một chỗ của đáp án — lệch ô là sai ở ô đó.
 */
function boxDiff(expected: string[], boxes: string[]): WordResult[] {
  return expected.flatMap((word, index): WordResult[] => {
    const typed = normalise(boxes[index] ?? "")[0];
    if (typed === word) return [{ op: "match" as const, word }];
    return [
      { op: "missing" as const, word },
      ...(typed ? [{ op: "extra" as const, word: typed }] : []),
    ];
  });
}

const DIFF_STYLE: Record<string, string> = {
  match: "text-ok",
  // Từ gõ sai: gạch bỏ, và mờ hơn vì nó là thứ sẽ bị bỏ đi.
  extra: "text-warn line-through decoration-2 opacity-70",
  // Chưa gõ tới: không phải đúng, cũng không phải sai. Xám và không trang trí.
  hidden: "font-data text-ink-faint",
};

const STAGGER_LIMIT_WORDS = 25;
const STAGGER_STEP_MS = 24;
const STAGGER_CAP_MS = 600;
/*
 * Chế độ nhập phải sống qua lần đổi câu.
 *
 * Mỗi câu là một lần mount khác (`key={item.id}`), nên state trong component mất
 * ngay khi bấm "Câu tiếp theo" — người đã chọn điền từng từ sẽ phải bật lại ở
 * từng câu. Cố ý KHÔNG dùng localStorage: đọc nó trong lần render đầu làm server
 * và client lệch nhau, còn đồng bộ bằng effect thì rơi đúng vào
 * `react-hooks/set-state-in-effect`. Biến module chỉ tồn tại trong phiên tab,
 * đúng phạm vi của một lựa chọn đang luyện, và không có gì để hydrate.
 */
let prefersWordMode = false;
/** Cùng phạm vi và cùng lý do với `prefersWordMode`. */
type Difficulty = "full" | "few" | "many";
let prefersDifficulty: Difficulty = "full";

export type ExerciseItem = {
  id: string;
  transcript: string;
  /** Câu chưa dịch vẫn học được — khối lời thoại chỉ hiện tiếng Anh. */
  transcript_vi?: string | null;
  /** Vắng khi nguồn phát không phải file audio (VD: segment YouTube) — lúc đó
   * `media` lo phần nghe, hoặc trang cha đặt player riêng bên ngoài. */
  audio_url?: string;
  /** Khung nghe thay cho `<audio>` mặc định (VD: player YouTube của Lab). */
  media?: React.ReactNode;
  word_count: number;
};

/**
 * Một câu dictation: nghe, gõ, chấm tại chỗ.
 *
 * Tách riêng vì luồng câu lẻ và luồng câu-trong-story phải chấm **giống hệt
 * nhau**. Hai bản sao của màn này sẽ trôi khỏi nhau, và chỗ trôi đầu tiên sẽ là
 * điểm số — thứ tệ nhất để có hai phiên bản.
 *
 * **Đổi câu phải truyền `key={item.id}`**, không phải một effect reset. Effect
 * là setState đồng bộ trong thân effect (lint `react-hooks/set-state-in-effect`
 * chặn đúng chỗ này), và nó còn dựng một khung hình mang câu mới cùng đáp án
 * câu cũ trước khi kịp dọn. `key` thay component mới hoàn toàn, không có khoảng
 * hở đó.
 */
export function DictationExercise({
  item,
  onGraded,
  onNext,
  nextLabel = "Câu tiếp theo",
  footer,
  submitAnswer,
  advanceOnEnter = true,
}: {
  item: ExerciseItem;
  /** Gọi sau mỗi lượt chấm, để trang cha làm mới tiến độ. */
  onGraded?: () => void;
  /** Có thì hiện nút đi tiếp, và Enter sẽ bấm nó khi câu đã đúng. */
  onNext?: () => void;
  nextLabel?: string;
  footer?: React.ReactNode;
  /** Ghi lượt làm về server. Mặc định là endpoint dictation cũ (kèm thưởng
   * pet); Listening Lab truyền hàm riêng trỏ về attempts của segment.
   *
   * `revealed` nói lượt này được làm sau khi đã mở đáp án — server dùng nó để
   * không tính tiến độ/XP, nên hàm ghi nào cũng phải chuyển tiếp. */
  submitAnswer?: (text: string, options: { revealed: boolean }) => Promise<unknown>;
  /** Enter khi đã đúng thì đi tiếp (mặc định, giữ flow cũ). Tắt ở Lab: đáp án
   * đúng là ở yên ngắm trạng thái đó — đi tiếp chỉ bằng nút bấm rõ ràng. */
  advanceOnEnter?: boolean;
}) {
  const [typed, setTyped] = useState("");
  // `checkedText` ghi lại văn bản đã được chấm, để khi người học sửa tiếp thì
  // bảng đối chiếu tự nhận là đã cũ thay vì nói dối về đoạn chữ hiện tại.
  const [result, setResult] = useState<GradeResult | null>(null);
  const [checkedText, setCheckedText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Một lượt lưu đang bay thì chưa nhận lượt nữa: bấm nhanh hai lần, hoặc
  // Enter rơi trúng lúc request trước chưa xong, sẽ ghi hai hàng cho cùng một
  // lần làm. Nút bấm thì tự disable, còn Enter phải chặn ở đây.
  const [saving, setSaving] = useState(false);
  // 0 = không gợi ý, 1 = chữ đầu của từng từ, 2 = nguyên câu. Chỉ đi một chiều:
  // đã thấy đáp án thì không "chưa thấy" lại được, và lượt gõ sau đó phải mang
  // cờ `revealed` để server không tính tiến độ.
  const [hintLevel, setHintLevel] = useState<0 | 1 | 2>(0);
  // Lượt đang hiện kết quả có phải lượt làm sau khi mở đáp án không — khác với
  // `hintLevel` hiện tại, vì người học có thể mở đáp án SAU khi đã chấm xong.
  const [checkedRevealed, setCheckedRevealed] = useState(false);
  // Ảnh chụp các ô tại lần chấm. Đọc `boxes` sống sẽ khiến bảng đổi theo tay
  // người học trước khi họ bấm Kiểm tra lần nữa.
  const [checkedBoxes, setCheckedBoxes] = useState<string[] | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty>(prefersDifficulty);
  const [wordMode, setWordMode] = useState(prefersWordMode);
  const expectedWords = normalise(item.transcript);
  // Một ô cho mỗi từ của đáp án: điền từng từ là chép vào đúng N chỗ, không
  // phải tự đoán xem mình đã gõ tới đâu. Ở chế độ có chỗ trống, từ hiện sẵn
  // vẫn nằm trong mảng này để việc chấm và vị trí ô là một nguồn duy nhất.
  const [boxes, setBoxes] = useState<string[]>(() => seedBoxes(expectedWords, prefersDifficulty));
  const difficultyLabelId = useId();
  const { token } = useSession();
  const { show } = useToast();
  const box = useRef<HTMLTextAreaElement | null>(null);
  const boxRefs = useRef<Array<HTMLInputElement | null>>([]);
  // Ô vừa có con trỏ, để sau khi chấm còn trả con trỏ về đúng chỗ đang gõ thay
  // vì nhảy về ô đầu — người học thường sửa đúng ô vừa bị chấm sai.
  const lastBox = useRef(0);
  const mirror = useRef<HTMLDivElement | null>(null);
  // Văn bản hiện tại của mọi chế độ nhập. Điền từng từ / chỗ trống chỉ là cách
  // chia cùng một câu thành các ô; bộ chấm, nút đi tiếp và việc lưu vẫn nhận
  // một chuỗi, nên không có đường chấm thứ hai.
  const blank = blankMask(expectedWords.length, difficulty);
  const boxMode = difficulty !== "full" || wordMode;
  const blankCount = blank.filter(Boolean).length;
  const current = boxMode ? boxes.join(" ") : typed;
  // Ô nào thật sự gõ được — dùng cho phím cách/Backspace và việc dán cụm.
  const editableIndexes = expectedWords
    .map((_, index) => index)
    .filter((index) => boxMode && blank[index]);
  const hasInput = boxMode
    ? editableIndexes.some((index) => Boolean(boxes[index]?.trim()))
    : Boolean(typed.trim());
  // Một dòng nói rõ mức đang chọn nghĩa là gì — ba nhãn "ít/nhiều" không tự
  // nói được hôm nay có bao nhiêu chỗ trống, và "cả câu" còn tuỳ cách gõ.
  const difficultyHint =
    difficulty === "full"
      ? wordMode
        ? `Mỗi từ một ô — ${blankCount} ô tất cả.`
        : `Gõ lại toàn bộ câu (${blankCount} từ).`
      : `Điền ${blankCount} từ còn trống — ${expectedWords.length - blankCount} từ khác đã hiện sẵn.`;

  /**
   * Chấm tại chỗ, rồi ghi lại lượt làm.
   *
   * Chấm chạy hoàn toàn trong trình duyệt (`lib/dictation.ts`, bản port từng
   * bước của bộ chấm phía server) nên phản hồi hiện tức thì.
   *
   * Ghi lại MỌI lượt, không còn luật "chỉ lần đầu tiên được tính". Luật đó sinh
   * ra khi tiến độ là điểm trung bình và cần chống việc chép lại đáp án để nâng
   * điểm. Giờ tiến độ chỉ đếm "đã gõ đúng chưa", nên không có gì để nâng — và
   * đổi lại, số lần thử trở thành dữ liệu học tập thật. Bỏ được luật đó cũng bỏ
   * luôn dòng chữ "Lần kiểm tra đầu tiên sẽ được ghi nhận", vốn bắt người học
   * phải cân nhắc trước khi bấm một nút lẽ ra bấm thoải mái.
   */
  function check(): GradeResult {
    const graded = grade(item.transcript, current);
    // Mở đáp án rồi mới gõ thì lượt này không được tính là nghe ra, kể cả khi
    // bài gõ khớp từng từ. Server giữ `is_complete` đúng sự thật để UI vẽ diff.
    const revealedNow = hintLevel >= 2;
    setResult(graded);
    setCheckedBoxes(boxMode ? [...boxes] : null);
    setCheckedText(current);
    setCheckedRevealed(revealedNow);
    // Lỗi của lượt trước là chuyện của lượt trước — lượt mới chấm xong thì
    // dòng "không lưu được" cũ không còn nói gì về lần làm này nữa.
    setError(null);

    /*
     * Xong một câu thì báo, và đây là thông báo DUY NHẤT trong app có tiếng.
     *
     * Lý do không phải thẩm mỹ mà là kỹ thuật: trình duyệt chỉ cho phát tiếng
     * sau khi người dùng đã tương tác với trang, và chỗ này chạy ngay trong lần
     * bấm Enter hoặc lần bấm nút Kiểm tra. Ba thông báo còn lại (huy hiệu, việc
     * hôm nay, lên level) bắn ra từ một lần `fetch` lúc mở trang, nên xin tiếng
     * ở đó là xin một thứ chắc chắn không được cấp.
     *
     * Chấm bằng `graded` chứ không bằng `result`: `setResult` chưa có hiệu lực
     * trong chính lần chạy này, nên đọc `result` ở đây là đọc kết quả của LẦN
     * CHẤM TRƯỚC — câu vừa gõ đúng sẽ im, còn câu ngay sau đó sẽ kêu oan.
     *
     * Khoá theo id câu: gõ lại một câu đã xong là chuyện bình thường (mọi lượt
     * đều được ghi), và lúc đó thẻ cũ được thay tại chỗ thay vì xếp thêm một
     * thẻ nữa.
     */
    // Đã xem đáp án thì không ăn mừng: niềm vui này sẽ khen việc chép, không
    // phải việc nghe. Bài gõ vẫn được chấm và hiện diff như mọi lượt.
    if (graded.is_complete && !revealedNow) {
      // Con thú loé sáng cùng lúc với thông báo. Cùng lý do dùng `graded` chứ
      // không dùng `result`: state chưa có hiệu lực trong chính lần chạy này.
      cheer();
      show({
        tone: "ok",
        title: "Đúng rồi",
        description: "Xong một câu. Nghe lại vẫn được nếu bạn muốn.",
        sound: "complete",
        dedupeKey: `dictation-${item.id}`,
      });
    }
    // Bấm nút thì con trỏ nhảy sang nút, và Enter kế tiếp sẽ bấm lại chính nút
    // đó. Trả con trỏ về ô nhập để Enter luôn có nghĩa "việc tiếp theo". Trên
    // màn hình cảm ứng thì ngược lại: focus là bật bàn phím ảo lên ngay lúc
    // người học đang đọc kết quả, nên chỉ giành lại con trỏ khi có chuột/bàn
    // phím thật.
    if (!window.matchMedia("(pointer: coarse)").matches) {
      // `boxMode`, không phải `wordMode`: chế độ ít/nhiều chỗ trống cũng gõ
      // trong các ô, còn textarea không hề được render — trả con trỏ vào một
      // ref rỗng thì nó nằm lại trên nút "Kiểm tra", và Enter kế tiếp chỉ bấm
      // lại nút đó thay vì đi tiếp.
      if (boxMode) {
        (boxRefs.current[lastBox.current] ?? boxRefs.current.find(Boolean))?.focus();
      } else {
        box.current?.focus();
      }
    }

    if (token) {
      // Server chấm lại từ `submitted_text`; kết quả của server mới là bản được
      // lưu, nên bản ghi không phụ thuộc vào bất cứ điều gì trình duyệt khai báo.
      const save = submitAnswer
        ? submitAnswer(current, { revealed: revealedNow })
        : apiFetch<{ pet?: { xp: number; mood: string } | null }>(
            API_ROUTES.submitDictation(item.id),
            {
              method: "POST",
              token,
              body: JSON.stringify({ submitted_text: current, revealed: revealedNow }),
            },
          );
      setSaving(true);
      save
        .then((saved) => {
          // Phần thưởng lấy từ phản hồi của MÁY CHỦ, không tính lại ở đây.
          notifyStudyReward((saved as { pet?: { xp: number; mood: string } | null } | null)?.pet);
          onGraded?.();
        })
        .catch(() => setError("Đã chấm xong, nhưng không lưu được lượt làm này."))
        .finally(() => setSaving(false));
    }
    return graded;
  }

  /**
   * Enter làm việc tiếp theo, dù việc đó là gì.
   *
   * Chưa đúng thì Enter là "kiểm tra"; đúng rồi thì Enter là "câu tiếp theo"
   * (trừ khi `advanceOnEnter` tắt — lúc đó Enter luôn là "kiểm tra lại", và đi
   * tiếp chỉ bằng nút). Cả bài dictation chạy được bằng bàn phím mà không rời
   * tay khỏi chỗ gõ — mà gõ chính là việc duy nhất người học đang làm ở đây.
   *
   * Shift+Enter vẫn xuống dòng. Một câu dictation không cần xuống dòng, nhưng
   * cướp hẳn một phím quen thuộc mà không chừa đường lui là thứ chỉ đúng cho tới
   * lúc có người thật sự cần nó.
   */
  function isComposing(event: React.KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>) {
    // Bộ gõ (IME) đang giữ chữ chưa commit. Xử lý phím lúc này — nhất là chuyển
    // ô khi bấm dấu cách — làm chữ đang soạn bị commit sang ô vừa nhận focus,
    // tức là từ vừa gõ tự nhân bản sang ô sau. Chờ IME nhả chữ đã.
    return event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229;
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>) {
    if (isComposing(event)) return;
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    // Giữ phím không phải là bấm nhiều lần.
    if (event.repeat) return;

    // Đi tiếp CHỈ khi đoạn chữ đang gõ đúng là đoạn đã được chấm. Sửa lại bài
    // rồi bấm Enter mà vẫn nhảy câu là lặng lẽ bỏ qua đoạn vừa sửa — thay vào
    // đó, Enter chấm lại đoạn hiện tại như mọi lần chưa đúng khác.
    if (advanceOnEnter && result?.is_complete && onNext && current === checkedText) {
      onNext();
      return;
    }
    // Lượt lưu trước còn đang bay thì chưa chấm lượt mới: hai lần bấm liền nhau
    // là hai hàng attempt cho cùng một lần làm.
    if (!hasInput || saving) return;

    check();
  }

  function updateBox(index: number, value: string) {
    const tokens = value.split(/\s+/).filter(Boolean);
    // Có dấu cách trong giá trị nghĩa là đã hết từ: bàn phím ảo/IME commit cả
    // cụm kèm dấu cách trong MỘT sự kiện `input` (không có `keydown` để chặn),
    // nên chuyển ô ở đây thay vì bỏ rơi dấu cách trong ô cũ.
    const separated = /\s/.test(value);
    setBoxes((previous) => {
      const next = [...previous];
      if (tokens.length <= 1) {
        next[index] = tokens[0] ?? "";
      } else {
        // Dán cả cụm thì chia sang các ô gõ được kế tiếp, bỏ qua từ hiện sẵn.
        const at = Math.max(0, editableIndexes.indexOf(index));
        tokens.forEach((token, offset) => {
          const target = editableIndexes[at + offset];
          if (target !== undefined) next[target] = token;
        });
      }
      return next;
    });
    if (separated) {
      const at = Math.max(0, editableIndexes.indexOf(index));
      const target = editableIndexes[at + Math.max(1, tokens.length)];
      // Sau khi React kịp áp state mới: focus ngay trong handler có thể bị lần
      // render của giá trị vừa commit kéo lại ô cũ.
      if (target !== undefined) window.setTimeout(() => boxRefs.current[target]?.focus(), 0);
    }
  }

  function focusEditable(index: number, step: 1 | -1) {
    const at = editableIndexes.indexOf(index);
    const target = at >= 0 ? editableIndexes[at + step] : undefined;
    if (target !== undefined) boxRefs.current[target]?.focus();
  }

  function onBoxKeyDown(index: number, event: React.KeyboardEvent<HTMLInputElement>) {
    if (isComposing(event)) return;
    if (event.key === " " && !event.shiftKey) {
      // Dấu cách là ranh giới giữa các ô, không phải ký tự trong một từ.
      event.preventDefault();
      focusEditable(index, 1);
      return;
    }
    if (event.key === "Backspace" && event.currentTarget.value === "" && index > 0) {
      event.preventDefault();
      focusEditable(index, -1);
      return;
    }
    onKeyDown(event);
  }

  function clearCheck() {
    setResult(null);
    setCheckedText(null);
    setCheckedBoxes(null);
    setCheckedRevealed(false);
    setError(null);
  }

  function chooseDifficulty(next: Difficulty) {
    if (next === difficulty) return;
    setDifficulty(next);
    setBoxes(seedBoxes(expectedWords, next));
    clearCheck();
    // Đổi chỗ gõ thì con trỏ theo: ô trống đầu tiên, hoặc ô nhập của chế độ
    // "cả câu" đang chọn.
    window.setTimeout(() => {
      if (next === "full") {
        if (wordMode) boxRefs.current[0]?.focus();
        else box.current?.focus();
      } else {
        const first = blankMask(expectedWords.length, next).findIndex(Boolean);
        if (first >= 0) boxRefs.current[first]?.focus();
      }
    }, 0);
  }

  function toggleMode() {
    const next = !wordMode;
    prefersWordMode = next;
    if (next) {
      const tokens = typed.split(/\s+/).filter(Boolean);
      setBoxes((previous) => previous.map((_, index) => tokens[index] ?? ""));
    } else {
      setTyped(boxes.join(" "));
    }
    setWordMode(next);
    clearCheck();
    // Đổi chế độ là đổi chỗ gõ; con trỏ phải theo, nếu không người dùng bàn
    // phím phải click chuột giữa một việc đáng lẽ liền mạch.
    window.setTimeout(() => {
      if (next) boxRefs.current[0]?.focus();
      else box.current?.focus();
    }, 0);
  }

  // Có ô thì đối chiếu theo Ô; gõ cả câu mới đối chiếu theo chuỗi.
  const displayDiff = result
    ? checkedBoxes
      ? boxDiff(expectedWords, checkedBoxes)
      : result.diff
    : [];
  const stagger = result !== null && displayDiff.length <= STAGGER_LIMIT_WORDS;
  // Từng ô đại diện cho một từ CỦA ĐÁP ÁN, nên bỏ `extra`: đó là từ người học
  // gõ thừa, không có ô riêng để tô.
  const checkedOps = displayDiff.filter((word) => word.op !== "extra").map((word) => word.op);
  // Con số đọc lên phải khớp bảng đang nhìn thấy: chế độ chỗ trống chỉ đếm
  // những ô người học thật sự phải gõ, không cộng phần câu hiện sẵn.
  const displayedMatched = boxMode
    ? editableIndexes.filter((index) => checkedOps[index] === "match").length
    : displayDiff.filter((word) => word.op === "match").length;
  const displayedTotal = boxMode ? editableIndexes.length : (result?.expected ?? 0);

  return (
    <>
      {error && (
        <div className="mb-4">
          <Alert tone="warn">{error}</Alert>
        </div>
      )}

      <Panel className="p-5">
        {/* Thanh tiện ích: nghe ở góc trái, gợi ý ở góc phải — phần gõ ở giữa
            là trung tâm. Gợi ý có giá: chữ đầu miễn phí, nguyên câu thì lượt
            gõ sau đó không được tính vào tiến độ. */}
        <div className="flex flex-wrap items-center gap-2">
          {item.media ??
            (item.audio_url ? (
              <audio controls src={item.audio_url} className="w-full min-w-0 flex-1" />
            ) : null)}
          {hintLevel < 2 && (
            <Button
              variant="secondary"
              size="sm"
              className="ml-auto"
              onClick={() => setHintLevel(hintLevel === 0 ? 1 : 2)}
              title={
                hintLevel === 0
                  ? "Mở chữ đầu của từng từ"
                  : "Mở cả câu — lượt gõ sau đó không tính vào tiến độ"
              }
            >
              {hintLevel === 0 ? "Gợi ý chữ đầu" : "Xem đáp án"}
            </Button>
          )}
        </div>

        {hintLevel === 1 && (
          <p className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded border border-rule bg-recess px-3 py-2 font-data text-small leading-relaxed text-ink-muted">
            {item.transcript
              .split(/\s+/)
              .filter(Boolean)
              .map((word, index) => (
                <span key={`${word}-${index}`} className="whitespace-nowrap tracking-[0.12em]">
                  {firstLetterHint(word).map((piece, position) => (
                    <span
                      key={position}
                      className={piece.revealed ? "font-semibold text-action" : undefined}
                    >
                      {piece.char}
                    </span>
                  ))}
                </span>
              ))}
          </p>
        )}
        {hintLevel >= 2 && (
          <div className="mt-3 space-y-1 rounded border border-rule bg-recess px-3 py-2">
            <p className="leading-relaxed">{item.transcript}</p>
            {/* Dictation đo được người học có NGHE ra chữ không, chứ không đo họ
                có hiểu không — bản dịch đi cùng lời thoại, và câu chưa dịch thì
                khối này chỉ có tiếng Anh. */}
            {item.transcript_vi && (
              <p className="text-small italic leading-relaxed text-ink-muted">
                {item.transcript_vi}
              </p>
            )}
            <p className="text-small font-medium text-warn">
              Đã xem đáp án — lượt gõ tiếp theo không tính vào tiến độ.
            </p>
          </div>
        )}

        {/* Độ khó đi từ gõ trọn câu xuống các mức có sẵn từ làm mốc. Chế độ
            từng từ chỉ là cách gõ của mức khó nhất, nên nó là một lựa chọn con
            của "Cả câu", không phải mức thứ tư đứng cạnh ba mức kia. Chọn một
            lần rồi giữ cho các câu sau. */}
        <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span
            id={difficultyLabelId}
            className="sr-only text-small font-medium text-ink-muted sm:not-sr-only"
          >
            Độ khó
          </span>
          <div className="flex flex-wrap gap-1.5" role="group" aria-labelledby={difficultyLabelId}>
            {(
              [
                ["full", "Cả câu", "Khó nhất: gõ toàn bộ câu"],
                ["few", "Ít chỗ trống", "Hiện phần lớn câu, chỉ để trống vài từ"],
                ["many", "Nhiều chỗ trống", "Hiện nửa câu, để trống nhiều từ hơn"],
              ] as const
            ).map(([value, label, title]) => (
              <Button
                key={value}
                variant={difficulty === value ? "primary" : "secondary"}
                size="sm"
                aria-pressed={difficulty === value}
                title={title}
                onClick={() => {
                  // Gán trong handler, không trong thân component: đây là bộ
                  // nhớ phiên của lựa chọn, không phải state của lần render.
                  prefersDifficulty = value;
                  chooseDifficulty(value);
                }}
              >
                {label}
              </Button>
            ))}
          </div>
          {difficulty === "full" && (
            <label className="flex cursor-pointer items-center gap-2 text-small text-ink-muted">
              <input
                type="checkbox"
                checked={wordMode}
                onChange={toggleMode}
                className="h-4 w-4 rounded border-rule-strong accent-action"
              />
              Gõ từng từ
            </label>
          )}
          <span className="w-full text-small text-ink-faint sm:ml-auto sm:w-auto">
            {difficultyHint}
          </span>
        </div>

        {boxMode ? (
          <div className="mx-auto mt-6 flex w-full max-w-5xl flex-wrap items-center justify-center gap-x-3 gap-y-3 py-2">
            {boxes.map((value, index) =>
              blank[index] ? (
                <input
                  key={index}
                  ref={(element) => {
                    boxRefs.current[index] = element;
                  }}
                  value={value}
                  onChange={(event) => updateBox(index, event.target.value)}
                  onKeyDown={(event) => onBoxKeyDown(index, event)}
                  onFocus={() => {
                    lastBox.current = index;
                  }}
                  autoFocus={index === 0}
                  autoComplete="off"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  enterKeyHint={
                    editableIndexes[editableIndexes.length - 1] === index ? "go" : "next"
                  }
                  // Trần theo TỪ, không theo câu: mỗi ô là một từ, và bộ chấm
                  // O(n·m) chạy ngay trong tab này.
                  maxLength={64}
                  // Rộng theo từ DÀI NHẤT giữa đáp án và thứ đang gõ: chỉ lấy
                  // độ dài đáp án thì gõ dài hơn sẽ bị cắt mất phần đuôi.
                  size={Math.max(3, (expectedWords[index] ?? "").length, value.length)}
                  aria-label={`Từ thứ ${index + 1}`}
                  className={cx(
                    // Chỉ một thanh ngang dưới chân từ, như dòng kẻ để viết —
                    // khung kín biến chỗ gõ thành một loạt hộp, nặng hơn hẳn
                    // nhịp đọc của câu.
                    "rounded-none border-0 border-b-2 bg-transparent px-1.5 pb-1 pt-0.5",
                    "text-center text-subtitle caret-ink outline-none focus:border-b-action sm:text-title",
                    checkedOps[index] === "match"
                      ? "border-b-ok text-ok"
                      : checkedOps[index] === "missing"
                        ? "border-b-warn text-warn"
                        : "border-b-rule-strong text-ink",
                  )}
                />
              ) : (
                <span key={index} className="text-subtitle text-ink sm:text-title">
                  {expectedWords[index]}
                </span>
              ),
            )}
          </div>
        ) : (
          <div className="relative mx-auto mt-6 w-full max-w-5xl">
            {/*
             * Ô nhập có một lớp phủ nằm dưới để gạch chân những từ gõ sai, ngay
             * tại chỗ người học đang gõ.
             *
             * `<textarea>` không tô màu được từng từ bên trong nó, nên cách duy
             * nhất là: một `<div>` chép lại đúng đoạn chữ đó nằm dưới, và
             * textarea nằm trên với chữ trong suốt — chỉ còn con trỏ và vùng
             * chọn là thật.
             *
             * Hai lớp phải khớp đến từng pixel, nếu không chữ sẽ lệch khỏi gạch
             * chân: cùng cỡ chữ, cùng padding, cùng độ dày viền (lớp phủ dùng
             * viền trong suốt để chiếm đúng chỗ), và `whitespace-pre-wrap` để
             * xuống dòng y hệt nhau. Cuộn cũng phải đồng bộ, vì lớp phủ không
             * tự cuộn theo.
             */}
            <div
              ref={mirror}
              aria-hidden
              className={cx(
                "pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words",
                "rounded border border-transparent px-4 py-3 text-subtitle leading-relaxed",
              )}
            >
              {result ? (
                annotateTyped(typed, wrongSubmittedIndices(result.diff)).map((piece, index) => (
                  <span
                    key={index}
                    className={
                      piece.wrong
                        ? "text-ink underline decoration-warn decoration-wavy decoration-2 underline-offset-4"
                        : "text-ink"
                    }
                  >
                    {piece.text}
                  </span>
                ))
              ) : (
                // Chưa chấm thì chưa biết từ nào sai — chép nguyên văn để chữ
                // vẫn hiện ra bình thường.
                <span className="text-ink">{typed}</span>
              )}
              {/* Ký tự vô hình giữ cho dòng cuối không bị co lại khi kết thúc bằng
                xuống dòng, để lớp phủ và textarea cùng cao. */}
              {"\u200b"}
            </div>

            {/* KHÔNG khoá sau khi chấm: sửa rồi kiểm lại là cách người ta thực sự
              dùng một bài dictation.
              `outline-none` + `focus:border-action` theo đúng lối của ô gõ từ ở
              màn typing: viền ô TỰ đổi màu khi focus. Để vòng `:focus-visible`
              toàn cục thì ô hiện hai viền cùng lúc — viền xám của ô và vòng cam
              cách ra 2px — vì ô nhập văn bản khớp `:focus-visible` cả khi bấm
              chuột, không chỉ khi Tab. */}
            <textarea
              ref={box}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              onKeyDown={onKeyDown}
              onScroll={(event) => {
                if (mirror.current) mirror.current.scrollTop = event.currentTarget.scrollTop;
              }}
              rows={3}
              // `autoFocus` + bộ thuộc tính dưới đây là cho bàn phím điện thoại:
              // câu mới là bàn phím mở sẵn, không tự viết hoa đầu câu, không tự
              // sửa chính tả (sửa lén từ tiếng Anh là chấm sai), và phím Enter
              // hiện chữ "go" thay vì xuống dòng. `maxLength` khớp trần 2000 ký
              // tự của `DictationSubmit.submitted_text` phía máy chủ.
              autoFocus
              autoComplete="off"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              enterKeyHint="go"
              maxLength={2000}
              aria-label="Gõ lại câu bạn vừa nghe được"
              placeholder="Gõ lại những gì bạn nghe được…"
              className={cx(
                "relative w-full resize-y rounded border border-rule-strong bg-transparent px-4 py-3",
                "text-subtitle leading-relaxed text-transparent caret-ink outline-none placeholder:text-ink-faint",
                "focus:border-action",
              )}
            />
          </div>
        )}

        {/* Bảng đối chiếu là hình ảnh; câu này nói kết quả bằng lời cho trình
            đọc màn hình, và `aria-live` để nó tự đọc ngay khi chấm xong. */}
        <div aria-live="polite" className="sr-only">
          {result
            ? result.is_complete
              ? checkedRevealed
                ? "Đã chép đúng, nhưng đáp án đã được xem nên câu này không tính vào tiến độ."
                : "Đúng rồi, đã gõ đúng cả câu."
              : difficulty === "full"
                ? `Chưa đúng. Khớp ${displayedMatched}/${displayedTotal} từ — xem bảng đối chiếu bên dưới.`
                : `Chưa đúng. Khớp ${displayedMatched}/${displayedTotal} chỗ trống — xem bảng đối chiếu bên dưới.`
            : ""}
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
          <Button disabled={!hasInput || saving} onClick={check}>
            <Check size={16} strokeWidth={2} aria-hidden />
            Kiểm tra
          </Button>
          <span className="flex items-center gap-1.5 text-small text-ink-faint">
            {saving ? (
              "Đang lưu…"
            ) : (
              <>
                hoặc nhấn <Kbd>Enter</Kbd>
              </>
            )}
          </span>
        </div>

        {/* Người mới thường chờ nghe trọn câu rồi mới dám gõ, và mất cả câu vì
            một từ. Nói trước rằng gõ dở vẫn có ích: bảng đối chiếu sẽ chỉ đúng
            chỗ còn thiếu. */}
        {!result && (
          <p className="mt-2 text-center text-small text-ink-faint">
            Gõ được bao nhiêu cũng được — phần chưa nghe ra sẽ được che bằng * khi chấm.
          </p>
        )}

        {/* Kết quả nằm NGAY DƯỚI ô nhập, trong cùng một khối — mắt không phải
            rời khỏi chỗ vừa gõ để đọc kết quả của chính nó. */}
        {result && (
          <div className="animate-settle mt-5 border-t border-rule pt-4">
            {/*
             * Câu trả lời là "đúng chưa", không phải "được bao nhiêu phần trăm".
             * Không có con số nào ở đây: 89% không nói cho người học biết nên đi
             * tiếp hay nghe lại, còn hai trạng thái dưới đây thì nói được.
             */}
            {result.is_complete ? (
              <>
                <p
                  className={cx(
                    "flex items-center gap-2 font-semibold",
                    checkedRevealed ? "text-ink-muted" : "text-ok",
                  )}
                >
                  <CircleCheck size={18} strokeWidth={2} aria-hidden />
                  {checkedRevealed
                    ? "Đã chép đúng — nhưng đáp án đã xem nên câu này không tính vào tiến độ."
                    : "Đúng rồi — bạn đã nghe ra cả câu."}
                </p>
                {/* Chấm xong mới mở lời thoại + nghĩa: hiện trước là đưa đáp án.
                  Đã xem đáp án (bậc 2) thì khối gợi ý phía trên đã có sẵn. */}
                {hintLevel < 2 && (
                  <div className="mt-2 space-y-1">
                    <p className="leading-relaxed">{item.transcript}</p>
                    {item.transcript_vi && (
                      <p className="text-small italic leading-relaxed text-ink-muted">
                        {item.transcript_vi}
                      </p>
                    )}
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="text-label font-semibold uppercase text-ink-faint">
                  Chưa đúng — đối chiếu
                </p>

                {/*
                 * Từng từ hiện ra, trái sang phải — vì đó chính là cách người ta
                 * nghe lại câu. Khoảnh khắc dàn dựng DUY NHẤT của cả app (§7).
                 */}
                <p className="mt-2 text-subtitle leading-9">
                  {maskMissing(displayDiff).map((word, position) => (
                    <span
                      key={`${word.op}-${position}`}
                      className={cx(stagger && "animate-settle", DIFF_STYLE[word.op])}
                      style={
                        stagger
                          ? {
                              animationDelay: `${Math.min(position * STAGGER_STEP_MS, STAGGER_CAP_MS)}ms`,
                            }
                          : undefined
                      }
                    >
                      {word.word}{" "}
                    </span>
                  ))}
                </p>

                {/* Chú giải in đúng KIỂU CHỮ của từng trạng thái, không chỉ ô
                    màu: mù màu lục-cam là kiểu phổ biến, nên màu không bao giờ
                    là kênh thông tin duy nhất. */}
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-small text-ink-muted">
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="h-2 w-2 bg-ok" /> đúng
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="h-2 w-2 bg-warn" />
                    <span className="text-warn line-through decoration-2 opacity-70">gõ sai</span>
                  </span>
                  {/* Không có dòng này, dấu sao trông như một lỗi thứ ba. */}
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="font-data text-ink-faint">
                      ***
                    </span>
                    còn thiếu
                  </span>
                </div>
              </>
            )}

            {/* Sửa xong mà chưa chấm lại thì bảng trên đang nói về đoạn chữ
                cũ. Nói ra, thay vì để nó âm thầm sai — kể cả khi bảng đó vừa
                báo "Đúng rồi", vì lúc đó nó đang khen một đoạn chữ không còn
                tồn tại. */}
            {checkedText !== null && current !== checkedText && (
              <p className="mt-3 text-small text-warn">
                Bạn đã sửa lại bài. Bấm Kiểm tra để đối chiếu đoạn hiện tại.
              </p>
            )}

            {(onNext || footer) && (
              <div className="mt-4 flex flex-wrap items-center gap-3">
                {onNext && (
                  <>
                    <Button onClick={onNext}>{nextLabel}</Button>
                    {result.is_complete && (
                      <span className="flex items-center gap-1.5 text-small text-ink-faint">
                        hoặc nhấn <Kbd>Enter</Kbd>
                      </span>
                    )}
                  </>
                )}
                {footer}
              </div>
            )}
          </div>
        )}
      </Panel>
    </>
  );
}
