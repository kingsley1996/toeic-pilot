# Kế hoạch học — lịch theo ngày

**Viết từ source ngày 2026-09-12.** Đây là mô tả **cái đang chạy** — phạm vi và
vì sao chọn path A nằm ở `SPEC-PLACEMENT.md` §1/§5; blueprint đầy đủ của chức
năng là `SPEC-STUDY-PLANNER.md` (V1 đã dựng — xem status của nó); trạng thái
công việc nằm ở `ROADMAP.md`. Mọi con số dưới đây đọc được bằng lệnh ghi kèm.

```
Màn hình        /learn/plan  · apps/web/src/app/learn/plan/page.tsx
                · apps/web/src/components/plan-calendar.tsx
API             GET/PATCH/POST /api/v1/study-plan* · app/api/routes/study_plan.py
Sinh kế hoạch   app/services/study_planner.py (V1 rule) · planner_llm.py (V2)
Bảng            study_plan · study_plan_item · user_profile
                (models, mig 068 + 082..085)
Test            tests/test_study_plan.py — 26 bài + tests/test_placement.py — 14 bài
                (`uv run pytest tests/test_study_plan.py tests/test_placement.py -q`)
```

## 0. Bốn bất biến, mỗi cái hỏng im lặng

1. **Ngày không nằm trong database — nhưng lịch CÓ NEO.** `study_plan.starts_at`
   (mig 085) là ngày duy nhất được lưu; mọi ô lịch suy lúc đọc từ
   `pack(positions, starts_at, phút/ngày, ngày/tuần)`. Hai hệ quả: tick một
   mục **không dịch chuyển mục khác** (người học gọi lịch nhảy theo cú bấm là
   "dồn task", và họ đúng), và "Dời lịch" (POST `/repack`) là đường **tường
   minh** duy nhất để đổi móc neo sau vài hôm nghỉ.
2. **"Hôm nay" là của máy chủ, tính theo `user_profile.timezone`.** Trình duyệt
   tự gọi `new Date()` thì người học múi khác lệch một cột, không lỗi nào báo
   — cùng bài học với streak và lịch hoạt động ở `/profile`.
3. **Ba nguồn "xong", không nguồn nào đè nguồn nào.** Bản ghi học là sự kiện;
   bài nộp là sự kiện; tick tay (`done_at`) là khẳng định. Mục kiểm tra chỉ có
   sự kiện — API từ chối tick với 409.
4. **Mọi chữ trên màn kế hoạch là số truy vấn.** Ước lượng/gap/feasibility/
   top-focus/`why` truy vấn lại lúc đọc từ `placement_result` + nhãn + profile;
   `why` là template. Một câu giải thích bịa số làm cả kế hoạch mất uy tín
   nhanh hơn mọi tiết kiệm prompt nào.

## 1. Kế hoạch xoay vòng theo tuần, lịch đóng gói theo phút

**Sinh** (`generate_plan`): hàng đợi priority (top 5 kỹ năng yếu/theo nhãn)
KHÔNG bị dồn vào đầu lịch. `_weekly_schedule` trải nó: mỗi tuần
`drills_per_week` (1–3 theo số ngày học) buổi luyện **round-robin** qua hàng
đợi — kỹ năng số 1 quay lại sau ~2 tuần, giãn cách thay vì tất-cả-tuần-đầu —
một board từ vựng **xoay chủ đề** (`Ôn từ vựng — Travel`, link thẳng
`/learn/vocabulary/{slug}`), một buổi chép **xoay ngữ liệu**
(`Chép chính tả — Short stories`), bài ngữ pháp rải vài tuần đầu. Hai tuần
cuối: không kỹ năng mới, chỉ đo + nền (§16 cấm nội dung lớn sát ngày thi).
Tuần buffer cuối CHẴN ô đo nhưng vẫn có nền nước rút (`total_weeks` = ceil,
mini chỉ tới `weeks`), và mỗi tuần được lấp nhịp nền tới ~90% ngân sách phút
(cap 2/tuần thường, 4/tuần buffer) — cung luôn đủ để `pack_days` KHÔNG để
lịch trắng trước ngày thi.
Mỗi tuần khép bằng `mini_test` — làm lại test đầu vào (cooldown 7 ngày khớp
một tuần/retake); `mock_test` neo tuần trước ngày
thi 7 ngày — đề **rút ngẫu nhiên từ pool** `mock_pool()`: full published
**và nằm trong collection published**. "Test published" một mình là nghĩa sai:
đề mồ côi hoặc thuộc bộ archived không có URL nào tới được — đưa nó vào select
là CTA dẫn người học vào tường 404 (đã xảy ra: 5/7 đề "published" trên dev
không vào được). Cùng pool nuôi `mock_options` và guard của PATCH — một bộ
lọc, ba chỗ đọc. **Đổi tay được tới lúc nộp** (`{test_id}` qua chính endpoint
tick), đã nộp là khóa. Link nào cũng mang `?plan=mock`: màn chi tiết đề dùng
dấu đó để **khóa "Luyện tập" và tick sẵn toàn bộ part không bỏ được** — thi
thử theo kế hoạch chỉ là thi thử khi nó diễn ra như thi thật. Catalogue trống → nhịp nền nhãn chung (`_filler_items`), không
phải không có gì.

**Retest đi qua HAI cửa, không còn đường tự do.** Kể từ phán quyết thứ hai,
`POST /placement/start` cần (1) cooldown 7 ngày của `_gate` VÀ (2) một ô
`mini_test` còn mở của kế hoạch hiện hành (`checkin_scheduled` trên gate —
đếm cùng công thức khép ô của §2, có loại seed vì `created_at` trên SQLite
chỉ chính xác tới giây). Chưa có kế hoạch / kế hoạch nước rút ≤14 ngày / đã
đo hết ô hẹn ⇒ cửa hai đóng, UI nói đúng từng nguyên nhân. Lượt ĐẦU không
chịu cửa hai — nếu không thì không có gì để sinh kế hoạch. Retake muộn hơn
ô hẹn không sao: ô khép theo thứ tự NỘP, dấu ✓ đứng ở ngày thật. Note cooldown
trên lịch chỉ hiện khi cửa mở MUỘN HƠN chính ô hẹn (`cooldownOpensAfter`) —
"đo lại được từ 14/9" ghi dưới ô hẹn 19/9 là chữ thừa báo một thứ sẽ không
chặn.

**Đọc** (`pack_days`): bốn luật — một ngày ≤ `minutes_per_day` (hard rule
(0) hàng đợi học TRẢI ĐỀU theo ngày thi: nhịp sàn của mục = phút tích lũy /
ngân sách ngày, CHỈ kéo giãn khi hàng đợi kết thúc sớm hơn horizon — cung đủ
thì nhét greedy như cũ (90′/ngày vẫn nhiều mục một ngày), cung thiếu thì
giãn đều thay vì dồn hết vào đầu lịch rồi bỏ trắng tuần cuối
§20); một tuần chỉ `study_days_per_week` ngày học, phần còn lại là **ngày
nghỉ** (không bị đếm "bỏ hôm"); bài kiểm tra **neo** (retake = ngày học đầu
tuần j và chiếm ngày độc quyền, thi thử = ngày cuối tuần trước `exam−7`); và
**một ngày không lặp hai mục cùng kind** — kể cả khi generator xếp hai tuần
nền cạnh nhau, luật này chặn "hai ô ôn từ vựng một ngày" ngay tại packer thay
vì tin thứ tự sinh. Mọi mục (đã xong hay chưa) đều chiếm chỗ → tick không
dịch lịch.

Mỗi mục mang `est_minutes` (grammar/drill 30′, nền 15′, retake 75′, mock 125′)
và `link` **do generator dựng**: drill kèm `?labels=PART_7_INFERENCE` mở màn
luyện đã chọn đúng dạng câu, board từ theo chủ đề, đề thi thử theo
collection/slug. UI chỉ đi theo link; bảng `planItemHref` bên web còn làm
fallback cho hàng cũ thiếu link — hai nguồn nối URL là hai nguồn có thể lệch.

Response `GET /study-plan`: `today`, `starts_at`, `minutes_per_day`,
`study_days_per_week`, `days_left` + header §34 (`estimate`, `gap`,
`weeks_left`, `feasibility`, `top_focus` (kèm `code`+`part` để chip bấm mở
drill đã lọc), `why`); mỗi mục: `day` (hẹn — cố định qua mọi cú tick),
`completed_on` (ngày THẬT của bản ghi/bài nộp/tick), `phase`, `link`,
`manual_done`, `topic_id`.

## 2. Ba nguồn "xong"

| Nguồn | Suy từ | Ngày hiển thị | Bỏ được? |
|---|---|---|---|
| Học thật | `grammar_lesson_completion` (non-revoked); phiên part có ≥1 câu `answered_at` sinh sau `plan.created_at` | ngày của chính bản ghi | Không — checkbox khoá + tooltip |
| Bài nộp | retake placement (`attempt` trên test `kind='placement'`, nộp sau plan) lần theo thời gian — retake thứ k khép `mini_test` thứ k; attempt trên đúng đề khép `mock_test` | ngày nộp | Không — **API 409 với mọi tick trên hai kind này**: tick bài kiểm tra là xưng đã đo mà chưa đo |
| Tick tay | `study_plan_item.done_at` (mig 083) | ngày **được bấm** — chỉ nhịp nền | Có |

Đếm %: `done_count` (server) và mẫu số UI cùng tính **mục lõi** =
grammar/drill/mini/mock — nhịp nền đứng ngoài. Test ghim:
`test_done_count_ignores_the_rhythm`, `test_weekly_checkin_closes_only_when_a_retake_lands`,
và `test_manual_tick_does_not_slide_the_calendar` (tick xong ngày các mục khác
đứng nguyên).

## 3. Pipeline sinh kế hoạch (`study_planner.py`)

Đầu vào: lượt placement đã phân tích + profile sống (target, exam,
phút/ngày, ngày/tuần). Ánh xạ `SPEC-STUDY-PLANNER`:

| Bước | Bản đang chạy |
|---|---|
| §5–6 skill profile | mọi mã nhãn (`question_type` + `grammar`) của lượt làm, 5 trạng thái theo accuracy, confidence theo băng mẫu (<3 câu = nhiễu, không được kết luận) |
| §11–13 priority | `độ_yếu_smoothing × confidence × relevance_theo_sức_nặng_phần × improvement_potential` — hằng số module, top 5 |
| §14 objective | `label_vi` từ registry + bằng chứng "đúng x/y" — trên nhãn drill, trên chip top-focus, trong `why` |
| §16 đường ống | grammar = `foundation` (rải tuần đầu), drill = `weakness` (xoay vòng), nền + duy trì = `integrated`, mọi kiểm tra = `final`; hai tuần cuối = nước rút |
| §22–23 | không chia đều part (priority dẫn); vùng mạnh nhận ĐÚNG MỘT suất duy trì, không quá |
| §20–21 phút | `EST_MINUTES` per kind; Σ ≤ ngân sách ngày là hard rule của packer; ngày nghỉ thật |
| §10 feasibility | ≤10 điểm/tuần FEASIBLE · ≤25 CHALLENGING · hơn HIGH_RISK; <120′/tuần tụt một bậc. Ngón tay cái, ghi rõ là ước lệ, không hứa |
| §32 đo lại | mỗi tuần một retake; kết quả mới là đầu vào của "Sinh lại" kế tiếp — vòng lặp mở một cú bấm, chưa tự chạy |

**API viết:**
- `POST /study-plan/generate {attempt_id?, source: rule|llm, force}` —
  idempotence cũ giữ nguyên; `force` khi đầu vào profile đổi (TargetForm bấm
  hộ). Start fresh khi sinh lại là quyết định đã chốt: việc đã học VẪN xong
  (suy từ bản ghi), chỉ tick nhịp nền mất.
- `POST /study-plan/repack` — đổi mỗi `starts_at` → hôm nay; nội dung, tick,
  count giữ nguyên. Nút "Dời phần còn lại từ hôm nay" hiện khi có mục hẹn
  trong quá khứ chưa xong.
- `PATCH /study-plan/items/{position} {done}` — 404 mục lạ, **409** trên
  mini/mock, trả cả plan.
- `GET /study-plan` null + `GET /placement/gate` phân biệt "chưa có kế hoạch"
  với "chưa làm test". Màn kết quả placement đọc thêm `/study-plan` chỉ để đổi
  nhãn nút: "Xem kế hoạch học" khi plan hiện hành dựng từ CHÍNH lượt này,
  "Tạo" khi chưa có hoặc khi đây là retake mới (bấm vào là sinh lại từ kết quả
  mới — `?from=` đã lo đường đó).

Planner V2 (`source: "llm"`): `write_plan(with_cadence=True)` nối nhịp tuần
_generic_ vào sau lựa chọn của model; V1 tự xếp lịch xoay vòng nên
`with_cadence=False`. Hỏng bất kỳ đâu đường LLM rơi về rule im lặng; đo
nghiêm ở `/admin/planner-compare`.

## 4. UI

- **Header §34**: điểm ước lượng + dải + CEFR, gap, badge feasibility ba màu,
  `why`. **Block "Theo dạng câu"**: chip top-focus (nhãn + đúng x/y), bấm mở
  drill đã lọc đúng nhãn — taxonomy từng loại câu nằm NGAY trên màn kế hoạch,
  không chỉ trong lý do từng mục.
- **Toolbar**: "Tháng 9 2026 ▾" — `<select>` native phủ trong suốt lên chữ đó;
  `‹ ›`; "Về hôm nay".
- **Ô ngày**: desktop — số + 3 chip chữ (`+n nữa`); mobile — một chấm màu mỗi
  mục: xong `ok` · lõi `action` · **kiểm tra `warn`** · nền `rule-strong`;
  ngày nghỉ trống nền `recess`; ✓ khi sạch việc. `aria-label` liệt kê hết nhãn.
- **Chi tiết ngày**: checkbox theo §2 (khoá với derived, khoá vĩnh viễn với
  test), label + reason + `est_minutes`, `ButtonLink` theo `item.link`.
- **TargetForm**: bốn ô = bốn đầu vào planner (điểm, ngày thi, phút/ngày,
  ngày/tuần) → `PATCH /profile` + `generate {force}`. Để trống = null = xoá.
- **Missed + Dời lịch**: lịch không tự trôi, nên trễ vài hôm là thật — hàng
  nhắc hiện khi có mục hẹn quá hạn, kèm nút repack.

Đã thử `react-day-picker` và **bỏ**: nó là date picker; ép làm lịch sự kiện là
đánh nhau với style của nó ở mọi dòng CSS.

## 5. Chỗ nào sửa là hỏng im lặng

| Nếu bạn… | Thì… | Ghim ở |
|---|---|---|
| Lưu ngày từng mục vào DB | ngày thành xác chết khi đổi quỹ thời gian; `starts_at` là móc neo DUY NHẤT được phép | `test_days_are_derived_at_read_time_not_stored` |
| Cho lịch trôi theo từng cú tick | "dồn task" — chính cái bị người học bác; tick xong mọi ô sau nhảy lùi | `test_manual_tick_does_not_slide_the_calendar` |
| Bỏ luật một-ngày-một-kind khỏi packer | hai board từ vựng chung một ô ngày khi tuần nước rút xếp hai nền cạnh nhau | `test_topics_rotation_labels_vocabulary_by_subject` |
| Dùng `datetime.now(UTC).date()` làm "hôm nay" | người học tối thấy lịch lệch một cột | `local_today(..., profile.timezone)` |
| Cho tick tay đè derived / tick bài kiểm tra | un-tick xoá sự kiện đã học; tick=test thành "đã đo" giả | cột `manual` riêng · API 409 |
| Xếp drill dồn hết vào tuần đầu rồi tới nhịp nền lặp vô tận | đúng phàn nàn 2026-09-12: "những ngày sau toàn ôn từ + chép" | `_weekly_schedule` round-robin |
| Tính `done_count` cả nhịp nền | "8/3 mục đã xong" | filter lõi cùng định nghĩa hai bên |
| Đọc target từ snapshot plan làm header | xoá mục tiêu rồi vẫn "cách mục tiêu 610 điểm" | `plan_insights` đọc profile sống |
| Cho `filler_per_week` theo BUỔI thay vì phút | lệch packing mỗi loại profile | `_week_cadence` tính theo phút |
| Bỏ nhịp sàn kéo giãn trong `pack_days` | đề thi xa: lịch trắng hẳn trước kỳ thi (hàng đợi cạn từ tuần 5) | `test_week_buffer_before_exam_still_has_content` |
| Bỏ filler lấp tuần / cho mini rơi vào tuần buffer | tuần cuối trống hoặc đo sát ngày thi không còn chỗ sửa | cùng test trên + `total_weeks` vs `weeks` |
| Tự nối URL trong cell thay vì theo `link` | drill mất bộ lọc nhãn, board mất chủ đề (bug lesson-id→topic là tiền lệ) | `item.link` + bảng fallback một chỗ |
| Đổi đề `mock_test` sau khi đã nộp | bài đã làm bị gán cho một đề khác | `_retarget_mock` đếm attempt, 409 |
| Cho lịch tự dời ô `mini_test` khi đang cooldown | hết là "lời hẹn đọc được", thành khối nhảy né cửa — đúng thứ vừa bị bác | CTA ghi `next_available_at`, ngày không đổi |
| Thêm CTA "đo lại" mới ngoài lịch | hai chỗ làm test đầu vào, một trong hai chắc chắn dính cooldown | panel allDone chỉ còn đề thi thử; nhịp đo do `mini_test` sở hữu |
| Cho `POST /placement/start` chỉ kiểm cooldown | quay lại thời "tự bấm test lại" — kế hoạch mất quyền định nhịp đo | `test_retest_follows_the_plan` (cửa 2 + loại seed cùng công thức ✓) |

## 6. Hàng xóm và phần chưa dựng

`Daily Tasks` (khe XP cố định) **không đổi gì** khi có lịch: lịch là la bàn,
tasks là XP — lịch không cấp XP, kể cả ngày có đề thi thử. Điểm chạm duy nhất
với SM-2: chip `Ôn từ vựng — {chủ đề}` dẫn vào đúng board topic của
`/learn/vocabulary`; hàng đợi trong đó do `srs.py` quyết.

**Chưa dựng so với spec:** weekly evaluation có số so sánh (§31), UI lịch sử
versions (§29 — rows cũ còn nguyên, mới có con trỏ `is_current`), auto-replan
(§32 — giờ là retake tuần + nút Sinh lại), và relevance theo `difficulty`
(cột chưa có dữ liệu thật — toàn bộ đang = hằng số).
