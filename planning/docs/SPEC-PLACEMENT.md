# Bài test đầu vào (placement) — SPEC

**Trạng thái: lát 1 + lát 2 ĐÃ DỤNG (2026-09-07).** Script `app/content/make_placement.py`
(path A từ `tp-test-09`, đề `tp-placement-01` 84 câu published), bảng
`placement_result` + `practice_test.is_placement` (migration 067), estimator v1
(tỉ lệ + CI 95% ±~75 điểm) + bảng CEFR ETS trong `services/placement.py`, ba
endpoint `/placement` (gate/start/analyze, cooldown 7 ngày = `RETAKE_COOLDOWN_DAYS`),
màn setup `/learn/placement` + kết quả `/learn/placement/result/[attemptId]`;
máy thi `/learn/attempts/[id]` dẫn thẳng sang phân tích khi đề là placement.

**Lát 2 — planner V1:** `study_plan`/`study_plan_item` (migration 068), planner
rule-based trong `services/study_planner.py` (kỹ năng yếu ≥3 câu mẫu → bài học
ngữ pháp, rồi part drill; ngân sách mục co còn 6 khi ngày thi ≤14 ngày —
không dồn, chỉ cắt), endpoint `/study-plan` (GET kế hoạch hiện hành + tiến độ
suy từ `grammar_lesson_completion` / phiên part sinh sau kế hoạch) và
`POST /study-plan/generate`. Mục tiêu ôn thi là MỘT nguồn sự thật
`user_profile`: form placement prefill từ profile qua gate, submit ghi về —
không còn "hai chỗ thông tin giống nhau". Web: `/learn/plan` (+ `?from=`
sinh từ lượt chỉ định), entry "Tạo kế hoạch học" ở màn kết quả placement.
Lát 3 (path B AI sinh form + LLM planner + so sánh theo §5) còn mở.

## 0. Vì sao 84 câu

Đề thật: Nghe 100 (P1 6 · P2 25 · P3 39 · P4 30), Đọc 100 (P5 30 · P6 16 · P7 54),
120 phút. Placement nằm ở luồng onboarding — bỏ giữa chừng là mất mát lớn nhất, nên
độ dài là thương lượng giữa **độ tin cậy** và **tỉ lệ hoàn thành**:

1. **Độ dài → tin cậy (Spearman–Brown):** mỗi lần rút ngắn, sai số chuẩn phóng lên
   theo √n. 84 câu → dải ước lượng ±~75 điểm TOEIC ở giữa thang (tính ở §2) — đủ
   để đặt băng trình độ. 40 câu sẽ là ±150 điểm: băng mất nghĩa. 120 câu: >70 phút
   mà tin cậy thêm rất ít (lợi nhuận biên của từng câu giảm dần).
2. **Tiền lệ chính chủ:** TOEIC Bridge của ETS là 100 câu / 1 giờ cho đúng mục đích
   xếp lớp. 84 câu ≈ 50 phút nằm cùng vùng.
3. **Cân hai kỹ năng:** Nghe 42 (P1 6 · P2 12 · P3 12 · P4 12), Đọc 42 (P5 20 ·
   P6 8 · P7 14) — mỗi section có sai số tương đương, không bên nào "rẻ hơn".
4. **Phủ kỹ năng cho breakdown:** P5 là part nhiều nhãn ngữ pháp nhất → 20 câu để
   mỗi kỹ năng chính có 2–4 câu. P3/P4 lấy nguyên conversation/talk (không cắt
   cụm), P6 lấy nguyên set 4 câu, P7 lấy 2 cụm đơn + 1 cụm đôi.
5. **Ràng buộc kho:** P1 kho chỉ có 31 câu → lấy 6 (bằng đúng số câu P1 của một đề
   thật) là tối đa hợp lý; P6 68 câu → 2 set.

Đề **cố định**, không random: kết quả của mọi người so sánh được với nhau.

## 1. Hai đường sinh đề (cả hai dựng)

| | A — Pick-up từ đề full | B — AI sinh form riêng |
|---|---|---|
| Là gì | Script chọn tập con từ một đề published, giữ nguyên cụm | Pipeline offline (T3, `app/content/`) lắp một form placement riêng |
| Lợi | Miễn phí nội dung; **có neo**: câu lấy từ form có sẵn `score_conversion` nên phép quy đổi dựa trên đường cong thật | Chọn được theo nhãn + độ khó độc lập với đề hiện có; ra form "thuần placement" |
| Chi phí | Bị giới hạn bởi nội dung từng đề (đề yếu nhãn nào thì thiếu nhãn đó) | Đắt hơn: cần khâu duyệt (draft → publish như nội dung thường) |
| LLM ở đâu | Không có | LLM **chọn từ danh sách đã tra ra** theo ràng buộc phủ nhãn/độ khó (khuôn UC4), con người duyệt. AI KHÔNG sinh câu mới — câu mới là cả pipeline audio/ảnh |

Chạy A trước (nhanh, có neo), B song song khi A thiếu nhãn. Đề cuối cùng vẫn là
một `practice_test` (`kind='mini'`) với slug cố định — đường vào phiên là máy thi
thật, không code thi mới.

## 2. Ước lượng điểm (tất định, không LLM — N1/N4)

**V1 — Tỉ lệ + dải tin cậy.** Với mỗi section: raw ước tính trên thang 100 =
`mini_raw / mini_n × 100`, tra `score_conversion` của form gốc (path A) hoặc bảng
default (path B). Dải tin cậy từ sai số nhị thức: `SE = √(p(1−p)/n)`, CI 95% ≈
±1.96·SE·(hệ số quy đổi). n=42, p=0.5 → ±~75 điểm TOEIC. UI **bắt buộc** hiện
dải "ước lượng 350–500", không hiện một con số giả chính xác.

**V2 — IRT (để sau, khi đủ dữ liệu):** hiệu chuẩn tham số câu (3PL) từ
`attempt_item` thật trên nền tảng → ước lượng θ của người làm → tra qua đường đặc
tính của form 200 câu. Đúng trắc psychometrics hơn nhưng cần ≥~200 lượt trả lời
mỗi câu; không dựng lúc kho dữ liệu còn mỏng. Ghi ở đây để đường nâng cấp rõ ràng.

## 3. CEFR — bảng ETS chính thức

Nghiên cứu chuẩn hoá của ETS (Tannenbaum & Wylie 2006) map **từng section** sang
CEFR, không map tổng điểm:

| CEFR | Nghe | Đọc |
|---|---|---|
| A1 | 60–105 | 60–110 |
| A2 | 110–270 | 115–270 |
| B1 | 275–395 | 275–380 |
| B2 | 400–485 | 385–450 |
| C1 | 490–495 | 455–495 |

**C2 không tồn tại trong mapping của TOEIC L&R** — trần của chuẩn-set panel ETS là
C1. Không phát minh băng C2 riêng (N4); UI trần ở "C1 (trần của TOEIC)". Mức tổng
thể hiển thị = section YẾU hơn (bảo thủ); hai section vẫn hiện riêng.

## 4. Kết quả lưu gì (snapshot, cùng lý `is_correct`)

Bảng `placement_result` (một hàng / lượt làm placement):
`attempt_id` (FK, PK) · `estimator_version` · `listening_raw/reading_raw` ·
`listening_low/high`, `reading_low/high` (dải ước lượng) · `cefr_listening`,
`cefr_reading`, `cefr_overall`.

Vì sao không suy ra lúc đọc: ước lượng phiên bản v1 và v2 (IRT) cho cùng một lượt
làm sẽ khác nhau — kết quả lịch sử phải giữ đúng phán quyết của thời điểm nó được
chấm, như `attempt_item.is_correct` không tính lại khi nội dung đổi.

Placement hiển thị **riêng**, không trộn vào lịch sử đề thi (nó không phải điểm
TOEIC thật) — trừ khi người dùng bấm "dùng làm điểm hiện tại" cho planner.

## 5. Hai planner, so sánh hiệu quả

| | V1 — Rule-based | V2 — LLM (UC4, T2) |
|---|---|---|
| Cách làm | Map tĩnh: kỹ năng yếu `GRAMMAR_*` → bài học ngữ pháp qua `grammar_topic_slug`; yếu part → part drill; thiếu nội dung → bỏ mục (N4) | Structured output, model **chọn từ danh sách ứng viên đã tra** (bài học, drill) theo placement + target + thời gian/ngày; tầng ghi từ chối tham chiếu treo |
| Ưu | Miễn phí, tức thời, test được từng nhánh | Cá nhân hoá theo bối cảnh (thời gian/ngày, exam date, trần target) |
| Nhược | Cứng, không giải thích "vì sao thứ tự này" | Đắt, chậm, cần eval |
| Bật khi nào | Mặc định | Nút "Thử xếp lại bằng AI" trên `/learn/plan`; hỏng ở BẤT KỲ bước nào → rơi về V1, không lỗi |

**Đã dựng (2026-09-07):** V2 trong `services/planner_llm.py` — model chỉ nhận
danh sách ứng viên (id ngắn + lý do dữ liệu), trả JSON `{items: [{id, reason}]}`;
mỗi id được tra ngược ứng viên, ref trùng/launched ngoài danh sách bị bỏ.
Prompt `plan_select.md` (runtime registry, version = hash nội dung), feature
`study_plan` qua `AiFeatureConfig` (tắt → FeatureDisabled → fallback rule).
Nguyên tắc sinh-lại: cùng lượt + cùng source = no-op trả kế hoạch hiện có;
lượt CŨ hơn không được thay kế hoạch từ lượt mới hơn; đổi source (rule ↔ llm)
= sinh lại — người dùng muốn nhìn planner khác đọc cùng một kết quả.

**Thiết kế so sánh (N5):** cùng một bộ hồ sơ golden (placement result + target +
thời gian) → cả hai planner → đo:
1. tỉ lệ hoàn thành kế hoạch (mục đã học / mục đề ra) sau 14 ngày,
2. giữ chân 14 ngày,
3. hiệu số giữa băng placement và điểm đề full kế tiếp,
4. chi phí + độ trễ mỗi kế hoạch,
5. eval tự động: mọi mục kế hoạch trỏ tới nội dung thật (deterministic check);
   con số nêu trong lời giải thích của LLM phải khớp truy vấn (UC3).

Quyết định "LLM có đáng không" = (1)–(3) thắng đủ xa so với chi phí (4).

## 6. Kế hoạch học hiển thị thế nào

- `study_plan` + `study_plan_item` (ADR-001 Phần C) — bảng chưa dựng, dựng trong
  lô này.
- Mục kế hoạch = một nội dung thật (bài ngữ pháp / part drill / đề) + lý do một
  dòng ("yếu câu hỏi suy luận 4/14") + trạng thái xong/chưa.
- Nguồn sự thật tiến độ = bản ghi học thật (completion, part session), không phải
  cột tick trên kế hoạch — cùng nguyên tắc §4 SPEC-GRAMMAR.

## 7. Các lát cắt triển khai

1. **Lát 1 — Đề + chấm:** path A (pick-up script, duyệt qua admin), máy thi tái
   dùng, `placement_result` v1 (tỉ lệ + CI), bảng CEFR, màn kết quả.
2. **Lát 2 — Planner V1:** bảng `study_plan*`, map tĩnh, onboarding prompt (bỏ qua
   được) + dashboard.
3. **Lát 3 — So sánh:** path B (AI sinh form), eval harness, bật LLM planner sau
   flag, chốt theo số liệu.

## 8. Chốt 2026-09-07 (trước khi code lát 1)

- **Retake:** 1 tuần 1 lần — check bằng `placement_result` mới nhất của người dùng
  (`attempt.started_at >= now - 7 days` → từ chối tạo lượt mới). Hằng số
  `RETAKE_COOLDOWN_DAYS = 7` trong code, không bảng config — config chỉ khi có
  yêu cầu thứ hai cho nó.
- **Đề mẫu: `tp-test-09`** (không có `tp-form-09` trong DB; đề full published
  200 câu, `score_scale_slug='default'`, 120 phút). Đã đo trên đề:
  - đủ cấu trúc 6/25/39/30/30/16/54 — cắt được đúng định mức §0 (P3 39→12: 4 cụm;
    P4 30→12: 4 talk; P7 54→14: 2 cụm đơn + 3 câu cụm đôi — **lưu ý P7 cụm đôi có
    5 câu/cụm, 3 câu từ một cụm đôi là một nửa cụm**: chấp nhận làm hỏng một cụm
    trong đề mẫu, hoặc chỉnh định mức thành 2 cụm đơn + 1 cụm đôi nguyên (5+5=10)
    + 4 câu đơn khác; chốt khi viết script)
  - P5 nhãn `question_type` mỏng (3 mã) — breakdown P5 phải đọc nhãn `grammar`
    (12 mã, 5–1 câu/mã: Tense 5, Voice 4, Preposition 4, Pronoun 4...) mới đủ dày.
    Định mức P5 20/30 đảm bảo mỗi nhãn `grammar` hiện diện ít nhất 1 câu.
- **Nhập điểm mốc trước khi làm:** đầu phiên placement có bước tự khai
  *điểm TOEIC hiện tại (nếu đã thi thật) + target score* (dùng check constraint
  của `user_profile`, 10–990 bước 5). Điểm khai là **mốc so sánh** cho màn kết quả
  (ước lượng cao hơn/thấp hơn tự khai bao nhiêu) và là đầu vào planner — KHÔNG
  ghi đè `user_profile.target_score`, chỉ điền giúp ô trống nếu người dùng bấm
  đồng ý ở màn kết quả.

## 9. Review 2026-09-07 — tám chỗ đã sửa

Đọc lại toàn bộ lát placement sau khi dựng xong. Sáu chỗ hỏng, hai chỗ nợ.

**Màn kết quả in một con số điểm, đúng thứ §2 cấm.** Nó cộng trung điểm hai dải
ra `612 / 990`. Nay hiện **dải tổng** như §2 đòi, và con số sát nhất đứng nhỏ
bên dưới.

**Trung điểm của dải không phải điểm quy đổi.** Đường cong `score_conversion`
dốc khác nhau từng khúc và dải bị kẹp ở `0` và `n`, nên trung điểm luôn bị kéo
về giữa thang: Nghe 40/42 quy đổi thật là **490**, dải 440–495, trung điểm
**468** — lệch 22 điểm một section, cùng chiều ở cả hai. Migration 070 thêm
`listening_scaled` / `reading_scaled` (điểm tại tỉ lệ đúng thật) và cả hai màn
đọc cột đó. Comment ở dashboard trước đây khẳng định ngược lại.

**Một lượt bỏ dở không được thành phán quyết.** `_finalise` chấm ô trống là sai
— đúng cho đề thi — nên mở bài rồi đóng tab tới hết giờ ra A1 với 0 câu đúng,
ghi vĩnh viễn và khoá bảy ngày. Nay `analyze` từ chối lượt không có câu trả lời
nào (409), và `_settle_pending` ở đầu `POST /start` dọn hàng "pending" của lượt
đã chốt: không câu trả lời nào thì **xoá**, có thì **chấm ngay**. Cooldown đếm
giữa hai *phán quyết*, không giữa hai lần bấm nút — hàng "pending" không còn
tiêu bảy ngày. `in_progress_attempt_id` chỉ báo lượt thật sự còn dở.

**`POST /attempts` nhận slug đề placement.** Vào thẳng máy thi là đi vòng qua cả
cổng lẫn hàng "pending" giữ mốc tự khai. Route nay trả 409 cho đề `is_placement`;
`/placement/start` gọi `open_attempt` — cùng thân hàm, tách khỏi cổng.

**`is_placement` mang `server_default="false"` dạng chuỗi trần.** Postgres ép về
boolean nên không lộ; SQLite lưu đúng chuỗi `'false'`, truthy trong Python, tức
**mọi đề đọc ra là đề placement trên cả bộ test**. Đó là lý do `analyze_attempt`
từng phải viết `is not True`. Nay `text("false")` + `default=False` như mọi cột
Boolean khác.

**`_whole_sets` có tham số `want` là mã chết** — giảm rồi không ai đọc, và số
trùng nhau che mất (cụm P3 đúng 3 câu nên 12 câu vừa đúng 4 cụm). Nay chặn thật.
`build()` cũng kiểm tổng đúng 84 câu trước khi xuất bản: `_pick_by_labels` bỏ
qua câu không nhãn và thoát êm, nên một đề 79 câu published được và con số ±75
in trên màn kết quả lặng lẽ sai.

**`score_scale_slug` ghi cứng `"default"`** — mâu thuẫn với chính lý do chọn path
A ở §1 ("có neo… dựa trên đường cong thật"). Nay lấy của đề nguồn.

**Khe giữa hai băng CEFR nay nổ thay vì rơi về A1.** Không có khe nào hôm nay
(mọi điểm quy đổi là bội của 5, các băng liền nhau ở bội 5); một bảng quy đổi
tương lai trả 452 thì đó là người đọc gần B2.

**Test.** `POST /placement/start` trước đó không có một dòng test nào — bốn
nhánh, gồm cả lời khẳng định "một nguồn sự thật" của §5. Nay có: mốc tự khai
sống sót qua `analyze`, mục tiêu chạy về `user_profile`, lượt đang dở trả lại
chính nó, 409 khi còn cooldown, lượt trắng không thành phán quyết, đề placement
bị máy thi từ chối, và phép quy về thang 100 (bỏ nó đi thì `low <= high` vẫn
đúng — phép kiểm duy nhất trước đây — trong khi cả dải tụt xuống 85–140 thay vì
185–325).

**Còn nợ:** `exam_date` vẫn kiểm ở tầng schema, nay khoan dung một ngày vì
schema không biết múi giờ hồ sơ; đúng ra phải tính "hôm nay" theo
`user_profile.timezone` như `profile_stats` làm cho streak. Và `/learn/placement`
chưa có e2e spec.
