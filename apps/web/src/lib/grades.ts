/**
 * Năm mức tự chấm, và đây là **bảng duy nhất** cho mọi màn có nút chấm.
 *
 * Trước đây `/learn/review` và thẻ lật trong chủ đề mỗi nơi giữ một bảng riêng,
 * và hai bảng đã trôi khỏi nhau: mức 0 là "Quên" ở một nơi và "Học lại" ở nơi
 * kia, mức 4 là "Được" và "Tốt", mức 5 tô hai màu khác nhau — và trang ôn
 * **thiếu hẳn mức 6**. Người học tự chấm cùng một từ ở hai màn và được hỏi bằng
 * hai bộ chữ khác nhau; tệ hơn, ở màn ôn họ không có cách nào nói "thuộc rồi".
 *
 * Dãy số nhảy 0 → 3 vì SM-2 gốc có sáu mức mà 0, 1, 2 đều nghĩa là "quên" và
 * không ai phân biệt được ba mức đó một cách đáng tin. Mức 6 không thuộc SM-2:
 * nó là quyết định chủ động đưa thẻ thẳng lên mốc đã thuộc. Cả năm giá trị soi
 * chiếu `GRADES` ở `app/services/srs.py`; API mới là nguồn sự thật, và bất kỳ
 * mức nào thiếu ở đây là một mức người học không với tới được.
 *
 * **Thang này là THỨ TỰ (kém → tốt), không phải phân loại**, nên màu chạy thành
 * một dải liên tục chứ không phải năm sắc rời rạc — hai mức tốt nhất dùng cùng
 * một xanh, khác nhau ở độ đậm. Và **không mức nào dùng chu sa**: màu hành động
 * chỉ dành cho "việc cần làm", tô nó lên một nút chấm là bắt nó mang hai nghĩa.
 * Màu ở đây là mã hoá DƯ THỪA; chữ mới là thứ mang nghĩa.
 */
export type GradeOption = {
  grade: number;
  label: string;
  hint: string;
  /** Phím tắt, cũng là thứ tự trái sang phải. */
  key: string;
  /** Vạch màu bên trái nút. */
  bar: string;
};

export const GRADE_OPTIONS: readonly GradeOption[] = [
  { grade: 0, label: "Học lại", hint: "chưa nhớ", key: "1", bar: "bg-alert" },
  { grade: 3, label: "Khó", hint: "chật vật", key: "2", bar: "bg-warn" },
  { grade: 4, label: "Tốt", hint: "nhớ ra", key: "3", bar: "bg-ink-muted" },
  { grade: 5, label: "Dễ", hint: "nhớ ngay", key: "4", bar: "bg-ok/55" },
  { grade: 6, label: "Thành thạo", hint: "thuộc luôn", key: "5", bar: "bg-ok" },
];
