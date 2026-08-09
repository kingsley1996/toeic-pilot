/**
 * Chấm một bài dictation, ngay trong trình duyệt.
 *
 * Đây là bản port **từng bước** của `apps/api/app/services/dictation.py`. Nó
 * phải cho ra cùng một kết quả với server, vì server vẫn chấm lại mọi bài nộp
 * và điểm được LƯU là điểm của server. Hai bên lệch nhau nghĩa là học viên nhìn
 * một điểm còn hệ thống ghi một điểm khác — kiểu sai không ai báo cáo được vì
 * ai cũng tưởng mình nhìn nhầm.
 *
 * Vì vậy: khi sửa file này, sửa cả file Python, và ngược lại.
 */

export type DiffOp = "match" | "missing" | "extra";
export type WordResult = { op: DiffOp; word: string };

/** `hidden` chỉ tồn tại khi hiển thị — bộ chấm không bao giờ sinh ra nó. */
export type DisplayOp = DiffOp | "hidden";
export type DisplayWord = { op: DisplayOp; word: string };
export type GradeResult = {
  accuracy: number;
  matched: number;
  expected: number;
  diff: WordResult[];
  /**
   * Khớp đáp án từng từ, không thiếu không thừa.
   *
   * Đây là thứ giao diện dùng, không phải `accuracy`. `accuracy` là
   * `matched / expected`, nên gõ đủ câu RỒI GÕ THÊM vẫn ra 100% — một con số
   * nói "hoàn hảo" cho bài rõ ràng chưa hoàn hảo.
   */
  is_complete: boolean;
};

/*
 * Python dùng `\w` với cờ UNICODE, tức chữ cái + chữ số + gạch dưới. `\w` của
 * JavaScript chỉ có ASCII, nên phải viết bằng property escape và cờ `u` — nếu
 * không, mọi ký tự có dấu sẽ bị coi là dấu câu và bị xoá mất.
 *
 * Dấu nháy đơn sống sót vì "don't" và "dont" là hai cách viết khác nhau thật,
 * còn dấu phẩy là thứ người nghe phải đoán.
 */
const STRIP_PUNCTUATION = /[^\p{L}\p{N}_\s']/gu;
const COLLAPSE_SPACE = /\s+/g;

// Dấu nháy cong đến từ PDF và bàn phím điện thoại; người gõ ASCII không đáng bị
// tính là sai vì chuyện đó.
const APOSTROPHES: Record<string, string> = { "’": "'", ʼ: "'", "´": "'" };

/**
 * Rút một dòng về đúng những từ mà dictation thực sự kiểm tra.
 *
 * Bỏ hoa thường và dấu câu, vì nghe thì không biết dấu phẩy đặt ở đâu. Giữ
 * chính tả, vì sai chính tả hoặc là nghe nhầm hoặc là hổng kiến thức viết —
 * cả hai đều đáng báo.
 */
export function normalise(text: string): string[] {
  let out = text.normalize("NFKC");
  for (const [fancy, plain] of Object.entries(APOSTROPHES)) out = out.split(fancy).join(plain);
  // Thứ tự giống hệt Python: hạ chữ thường TRƯỚC rồi mới xoá dấu câu.
  out = out.toLowerCase().replace(STRIP_PUNCTUATION, " ");
  out = out.replace(COLLAPSE_SPACE, " ").trim();
  return out === "" ? [] : out.split(" ");
}

type Block = { i: number; j: number; size: number };
type Opcode = { tag: string; i1: number; i2: number; j1: number; j2: number };

/**
 * `difflib.SequenceMatcher` của Python, phần được dùng ở đây.
 *
 * KHÔNG thay bằng một thuật toán LCS thông thường. difflib đi tìm *khối khớp
 * dài nhất* rồi đệ quy sang hai bên, và với cùng một cặp đầu vào nó cho ra cách
 * ghép khác với LCS — nghĩa là học viên sẽ thấy những từ khác nhau bị tô màu.
 *
 * Phần xử lý "junk" của difflib được lược bỏ có chủ ý: server gọi với
 * `autojunk=False` và không truyền `isjunk`, nên các nhánh đó không bao giờ
 * chạy.
 */
class SequenceMatcher {
  private readonly b2j = new Map<string, number[]>();

  constructor(
    private readonly a: string[],
    private readonly b: string[],
  ) {
    b.forEach((word, index) => {
      const seen = this.b2j.get(word);
      if (seen) seen.push(index);
      else this.b2j.set(word, [index]);
    });
  }

  /** Khối khớp dài nhất; hoà thì lấy khối ở vị trí sớm nhất trong a, rồi trong b. */
  private findLongestMatch(alo: number, ahi: number, blo: number, bhi: number): Block {
    let besti = alo;
    let bestj = blo;
    let bestsize = 0;
    let j2len = new Map<number, number>();

    for (let i = alo; i < ahi; i += 1) {
      const newj2len = new Map<number, number>();
      for (const j of this.b2j.get(this.a[i]) ?? []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) ?? 0) + 1;
        newj2len.set(j, k);
        if (k > bestsize) {
          besti = i - k + 1;
          bestj = j - k + 1;
          bestsize = k;
        }
      }
      j2len = newj2len;
    }
    return { i: besti, j: bestj, size: bestsize };
  }

  private getMatchingBlocks(): Block[] {
    const la = this.a.length;
    const lb = this.b.length;
    const queue: Array<[number, number, number, number]> = [[0, la, 0, lb]];
    const blocks: Block[] = [];

    while (queue.length > 0) {
      const [alo, ahi, blo, bhi] = queue.pop() as [number, number, number, number];
      const block = this.findLongestMatch(alo, ahi, blo, bhi);
      if (block.size > 0) {
        blocks.push(block);
        if (alo < block.i && blo < block.j) queue.push([alo, block.i, blo, block.j]);
        if (block.i + block.size < ahi && block.j + block.size < bhi) {
          queue.push([block.i + block.size, ahi, block.j + block.size, bhi]);
        }
      }
    }
    blocks.sort((x, y) => x.i - y.i || x.j - y.j);

    // Gộp các khối liền kề, y như difflib.
    let i1 = 0;
    let j1 = 0;
    let k1 = 0;
    const merged: Block[] = [];
    for (const { i: i2, j: j2, size: k2 } of blocks) {
      if (i1 + k1 === i2 && j1 + k1 === j2) {
        k1 += k2;
      } else {
        if (k1 > 0) merged.push({ i: i1, j: j1, size: k1 });
        i1 = i2;
        j1 = j2;
        k1 = k2;
      }
    }
    if (k1 > 0) merged.push({ i: i1, j: j1, size: k1 });
    merged.push({ i: la, j: lb, size: 0 });
    return merged;
  }

  getOpcodes(): Opcode[] {
    let i = 0;
    let j = 0;
    const answer: Opcode[] = [];
    for (const { i: ai, j: bj, size } of this.getMatchingBlocks()) {
      let tag = "";
      if (i < ai && j < bj) tag = "replace";
      else if (i < ai) tag = "delete";
      else if (j < bj) tag = "insert";
      if (tag) answer.push({ tag, i1: i, i2: ai, j1: j, j2: bj });
      i = ai + size;
      j = bj + size;
      if (size > 0) answer.push({ tag: "equal", i1: ai, i2: i, j1: bj, j2: j });
    }
    return answer;
  }
}

/**
 * So bài nộp với đáp án, theo từng từ.
 *
 * Một từ bị thay thế được báo thành HAI mục — từ đáng lẽ phải có (`missing`) và
 * từ đã gõ (`extra`). Gộp lại thành một sẽ giấu mất thứ người học thật sự viết,
 * mà đó mới là nửa hữu ích.
 */
export function grade(transcript: string, submitted: string): GradeResult {
  const expectedWords = normalise(transcript);
  const submittedWords = normalise(submitted);

  const diff: WordResult[] = [];
  let matched = 0;

  for (const op of new SequenceMatcher(expectedWords, submittedWords).getOpcodes()) {
    if (op.tag === "equal") {
      matched += op.i2 - op.i1;
      for (const word of expectedWords.slice(op.i1, op.i2)) diff.push({ op: "match", word });
    } else {
      for (const word of expectedWords.slice(op.i1, op.i2)) diff.push({ op: "missing", word });
      for (const word of submittedWords.slice(op.j1, op.j2)) diff.push({ op: "extra", word });
    }
  }

  const expected = expectedWords.length;
  // Transcript rỗng cho 0 điểm chứ không chia cho 0. Nó không nên tới được đây,
  // nhưng một bộ chấm ném lỗi thì người chịu thiệt là học viên, không phải nội dung.
  const accuracy = expected > 0 ? Math.round((matched / expected) * 10000) / 100 : 0;

  return {
    accuracy,
    matched,
    expected,
    diff,
    // Kiểm trên `diff` chứ không so `matched === expected`: phép so đó bỏ sót
    // đúng cái bẫy `extra`.
    is_complete: expected > 0 && diff.every((word) => word.op === "match"),
  };
}

/**
 * Che những từ học viên chưa gõ tới.
 *
 * Không có nó, bấm Kiểm tra khi mới gõ 4 trên 10 từ sẽ in ra cả 10 — tức là
 * phát đáp án cho đúng phần người ta chưa nghe ra. Bài tập mất nghĩa ngay từ
 * lần bấm đầu tiên.
 *
 * Ranh giới là **số từ học viên đã gõ**, tính theo vị trí trong câu đáp án:
 * từ `missing` nằm ở vị trí thứ `i` bị che khi `i >= số từ đã gõ`.
 *
 *     đáp án : we need to make a reservation before visiting the restaurant
 *     đã gõ  : we need to maek                        (4 từ)
 *     hiện   : we need to make maek * *********** ****** ******** *** **********
 *                          ^^^^ vị trí 3 < 4 nên KHÔNG che: đã thử, đã sai
 *
 * Ranh giới này **không** suy ra được từ vị trí trong `diff`. Cách hiển nhiên —
 * "che mọi thứ sau mục cuối cùng học viên đóng góp" — sai, vì
 * `SequenceMatcher` gom cả đoạn còn lại vào MỘT khối `replace`, đặt toàn bộ
 * `missing` trước `extra`; với ví dụ trên nó sẽ che 0 từ và in nguyên đáp án.
 * Sai đúng ở ca hay gặp nhất: gõ dở và gõ sai từ cuối.
 *
 * Số từ đã gõ tự suy ra được từ chính `diff`: mỗi từ học viên nhập vào hoặc
 * khớp (`match`) hoặc thừa (`extra`), không có khả năng thứ ba.
 *
 * Số dấu sao bằng số ký tự của từ. Đó là gợi ý có chủ ý — biết từ tiếp theo dài
 * mấy chữ là một điểm tựa quen thuộc của dictation — và nó giữ cho dòng chữ
 * không nhảy khi từ được mở ra.
 *
 * **Đây thuần tuý là hiển thị.** Nó chạy trên kết quả của `grade()` chứ không
 * nằm trong đó: `accuracy` vẫn tính trên toàn bộ câu, nên con số học viên nhìn
 * thấy vẫn khớp với con số server ghi lại. Đưa việc che vào `grade()` sẽ phá
 * đúng sự khớp đó.
 */
export function maskUnreached(diff: WordResult[]): DisplayWord[] {
  const typedCount = diff.filter((word) => word.op === "match" || word.op === "extra").length;

  let position = -1;
  return diff.map((word) => {
    // `extra` là từ học viên gõ ra, không chiếm vị trí nào trong câu đáp án.
    if (word.op === "extra") return word;
    position += 1;
    return position >= typedCount && word.op === "missing"
      ? { op: "hidden" as const, word: "*".repeat(word.word.length) }
      : word;
  });
}

/**
 * Những từ NGƯỜI HỌC GÕ mà không khớp đáp án, theo vị trí trong bài nộp.
 *
 * Dùng để gạch chân ngay trong ô nhập, nơi họ đang gõ — chỉ ra chỗ sai tại đúng
 * chỗ nó xảy ra, thay vì bắt mắt chạy xuống bảng đối chiếu rồi dò ngược xem từ
 * nào ứng với từ nào.
 *
 * Suy ra được từ `diff` nên `grade()` không phải đổi: mỗi từ trong bài nộp xuất
 * hiện đúng một lần ở `diff` dưới dạng `match` (khớp) hoặc `extra` (không khớp);
 * `missing` là từ của ĐÁP ÁN mà người học chưa gõ ra, nên nó không chiếm vị trí
 * nào trong bài nộp.
 */
export function wrongSubmittedIndices(diff: WordResult[]): Set<number> {
  const wrong = new Set<number>();
  let index = -1;
  for (const word of diff) {
    if (word.op === "missing") continue;
    index += 1;
    if (word.op === "extra") wrong.add(index);
  }
  return wrong;
}

/**
 * Cắt văn bản thô thành từng mảnh kèm cờ đúng/sai, giữ nguyên khoảng trắng.
 *
 * Khoảng trắng và dấu câu phải được giữ y nguyên để lớp phủ nằm khít với chữ
 * thật trong ô nhập. Một tiếng thô có thể chuẩn hoá ra nhiều từ (`foo—bar` →
 * `foo` `bar`) hoặc không ra từ nào (`...`), nên mỗi tiếng tiêu thụ đúng số từ
 * mà `normalise` sinh ra từ nó — đếm theo dấu cách sẽ lệch ngay ở dấu gạch nối.
 */
export function annotateTyped(
  text: string,
  wrong: Set<number>,
): Array<{ text: string; wrong: boolean }> {
  const pieces: Array<{ text: string; wrong: boolean }> = [];
  let wordIndex = 0;

  for (const chunk of text.split(/(\s+)/)) {
    if (chunk === "") continue;
    if (/^\s+$/.test(chunk)) {
      pieces.push({ text: chunk, wrong: false });
      continue;
    }
    const produced = normalise(chunk).length;
    let isWrong = false;
    for (let step = 0; step < produced; step += 1) {
      if (wrong.has(wordIndex + step)) isWrong = true;
    }
    wordIndex += produced;
    pieces.push({ text: chunk, wrong: isWrong });
  }
  return pieces;
}
