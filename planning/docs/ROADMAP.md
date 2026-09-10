# ROADMAP

**Tracker duy nhất.** Không tệp nào khác trong `planning/` mang trạng thái. Đọc trước khi
bắt đầu; cập nhật khi xong việc.

Viết lại từ source ngày **2026-09-01**. Lịch sử bốn mươi sprint đã xong nằm ở
[`archive/ROADMAP-through-2026-09-01.md`](../archive/ROADMAP-through-2026-09-01.md) — giữ vì
phần *vì sao* vẫn đọc được, nhưng bảng trạng thái ở đó sai ở mọi dòng và đó là lý do nó
được thay.

## 1. Đang ở đâu

Đo trên `main`, 2026-09-06. Lệnh đo ghi ở [`SYSTEM-OVERVIEW.md`](SYSTEM-OVERVIEW.md) §1.

| | |
|---|---|
| Test API | **1035 passed**, 4 skipped, 2 `external` deselect |
| E2E | 8 tệp, **22 passed / 4 skipped** |
| Gate CI | 4 job xanh. **Branch protection chưa bật** |
| Bảng · migration | 65 · 66 |
| Endpoint | **231 thao tác** (139 admin) |
| Route web | 61 |
| Nội dung | **6 đề / 855 câu** (834 có giải thích) · **600 từ vựng / 14 chủ đề** · **134 câu dictation / 17 bài** · **ngữ pháp: 18/18 chủ đề published / 20 bài học** · **collocation: 238 published / 13 chủ đề** |
| Media | **5 115 hàng `audio_asset`**; từ vựng và dictation **toàn bộ ở `engine_version` 3** (4 796 + 134 clip) |
| Nhãn | **838/855 câu** đã gắn (989 hàng) |

**Vòng đời nội dung khép kín và chạy thật**: dán hoặc sinh bằng đồ thị → `draft` → audio
sinh ngoài luồng → cổng publish từ chối khi audio lệch → học viên làm bài. Ba đề 200 câu
(`tp-form-06/07/08`) đã qua đường đó.

**Nút thắt vẫn là nội dung, không phải mã** — nhưng đã đổi chỗ: giải thích không còn
chặn RAG (**834/855**, ngưỡng `ADR-003` §3.3 vượt xa), và giáo trình ngữ pháp đã đủ
18/18 chủ đề; cái còn thiếu là **bài practice gắn câu** cho từng chủ đề.

## 2. Đang làm dở

| Việc | Còn gì | Ở đâu |
|---|---|---|
| ~~**Dàn giọng narrator**~~ | **Xong cả dev lẫn production.** Từ vựng + dictation: 2 470 clip thu lại, cả 3 994 clip ở `engine_version` 3, bốn narrator chia đều 965/giọng. Ba đề `tp-form-06/07/08` cũng đã ở v3 trên production. Dư lại 11 clip v1 + 24 clip `-` thuộc hai đề mẫu cũ (`demo-2026-test-1`, `toeic-2024-test-1`), giống hệt nhau ở hai bên | `PHASE2-AUDIO.md` §A4.6 |
| ~~**Đưa đề lên production**~~ | **Xong.** Cả năm đề đã `published` trên production, gồm `tp-form-08`. Đối chiếu 2026-09-02: audio đề ở production khớp từng con số với dev | `SYNC-TEST-TO-PRODUCTION.md` |
| **Tách tệp quá dài** | Đợt 1–3 xong. Nợ: hai trang admin không có e2e | `REFACTOR-LONG-FILES.md` §4b |
| **Gộp tài liệu** | Xong đợt này. Còn: quyết định giữ hay bỏ `PLAN.md` | mục 5 dưới đây |
| ~~**Turnstile ở cửa đăng ký/đăng nhập**~~ | **Xong, tắt mặc định.** Vá đúng lỗ mà `auth.py` tự nhận là có: rate limit theo IP không chặn nổi botnet xoay IP, còn đếm theo tài khoản thì mở đường khoá tài khoản người khác. Turnstile không đếm gì — nó bắt mỗi lần gửi form trả một cái giá tính toán. Bật bằng hai biến môi trường; **một nửa cấu hình thì API từ chối khởi động**. Giá: ~0,5 giây mỗi lần đăng nhập, và **một script bên thứ ba** — xem nợ P1-7b ở §4 | `adr/ADR-015-TURNSTILE.md` |
| ~~**Ba chỉ số nuôi nhau, và một trạng thái đáy**~~ | **Xong.** Đói rút sức, buồn làm sức hồi chậm một nửa, nên "vừa đói vừa buồn mà sức 100%" không còn dựng được. Cả ba chạm đáy thì con thú **ốm**: đứng im, có biểu tượng trên đầu, bản đồ phủ mờ, và một nút giữa bản đồ mở **nhiệm vụ hồi phục một câu** — làn riêng, không dùng chung với khách hay kẻ xâm nhập, và không có dictation. Trần XP ngày cũng đổi từ chặn cứng sang giảm dần cùng đợt. Migration 053, 054 | `ADR-012`, `Evaluate_Pet_TOEIC_Pilot.md` §2.2.1 |
| ~~**Người mới nhận một quả trứng**~~ | **Xong.** Không còn tặng thẳng một con mèo: `pet_state.species` nullable (migration 055), quả đầu miễn phí, và cả bảng Petland lẫn thẻ sidebar có giao diện riêng cho lúc chưa có thú. `GET /pet` trả **204** cho "chưa mở trứng", cùng lý lẽ với `GET /petland/map`. Tám tệp e2e phải nở trứng trước vì chúng đều giả định có sẵn một con | `ADR-012` |
| ~~**Tour chào người mới**~~ | **Xong.** Bốn bước trên trang chủ, tự dựng trên `@floating-ui/react-dom` — không thư viện tour, để lớp phủ theo được ba luật hỏng-im-lặng của hệ thiết kế. Đèn rọi là SVG khoét lỗ chứ không phải `box-shadow`. Mốc "đã xem" nằm ở `user_profile.toured_at` (migration 056) chứ không ở `localStorage`, nên nó không chào lại ở thiết bị thứ hai. `e2e/tour.spec.ts` + `e2e/support.ts` (`skipTour`) | `frontend.md` |
| ~~**Petland ra khỏi chỗ nổi**~~ | **Xong.** Thú cưng có thẻ cố định ở đáy sidebar — con thú thật (thở, vòng sáng theo hạng), ba chỉ số bằng biểu tượng, tên loài lấy từ `PetPublic.label` mới. Thẻ là đường vào duy nhất, nên nút nổi kéo-thả và danh sách sáu route `STUDYING` đã bỏ. Toast và lời thoại bám vào thẻ. `petland.spec.ts` đã trỏ lại và **10/10 xanh**. Còn hở: **trên mobile mất một chạm** (cột trái là `hidden` dưới `lg`, phải mở ngăn kéo trước) | `Evaluate_Pet_TOEIC_Pilot.md` §2.1 |
| ~~**Ngữ pháp — module thứ năm, G1–G5**~~ | **Xong.** Năm bảng (migration 057–060), admin CRUD + màn soạn bài theo trang riêng với ô xem trước, cây học `/learn/grammar`, bài `practice` gắn câu từ kho nhãn hoặc soạn tại chỗ, tiến độ bằng nút hoàn thành ghi bảng (không suy ra từ `attempt` — lý do đảo ở spec), chuỗi `next_topic` nối chủ đề nền tảng không mã với chủ đề theo nhãn. G5 (migration 061–062): một câu đúng = 2 XP tất định theo (người, câu), khe "Học
  ngữ pháp" 3 bài kẹp theo số bài còn lại, completion gỡ dấu bằng `revoked_at`
  chứ không xoá — nên cả câu lẫn bài học đều tính vào chuỗi ngày và quà ruby. G3 (luyện theo nhãn cuối chủ đề) từng dựng rồi **bỏ**. Cổng ≥12 câu đã bỏ —
  publish chỉ cần ≥1 bài. markdown-lite 81 → 242 dòng. Lý thuyết đủ 18 chủ đề,
  5 bài cũ viết lại cùng format | `SPEC-GRAMMAR.md` |
| ~~**Video bài giảng cho lesson ngữ pháp**~~ | **Xong code (2026-09-09).** `grammar_lesson` hai cột nullable (migration 077), `MediaKind="video"` — ticket/confirm/delete đúng luồng ADR-006, byte PUT thẳng object store, Cloudinary bị chặn cho video (băng thông ăn credit ảnh), driver đi chung lựa chọn với audio, `VIDEO_PUBLIC_BASE_URL` cấu hình riêng, vùng khoá `grammar-video/`. Màn soạn: khối "Video bài giảng" chỉ với lesson theory đã lưu; người học: `<video controls preload="metadata">` trên body. 8 bài test `test_grammar_video.py`. Còn lại: đụng `ADR-006` §2.2 (điều kiện spec §1), cấu hình Supabase public bucket + `VIDEO_PUBLIC_BASE_URL` ở production, và chạy `alembic upgrade` | `SPEC-GRAMMAR-VIDEO.md` |
| ~~**Collocation — là từ vựng, không phải module thứ sáu**~~ | **Xong cả spec, dựng lẫn sync production (2026-09-09).** Migration 079 chỉ tạo `collocation_detail` 1:1 với `vocabulary_entry` (`part_of_speech='phrase'`); 7 pattern (ADJ_NOUN + VERB_ADJ thêm cùng đợt nội dung đầu — 53/182 cụm nằm ở đó). SM-2/audio/XP/ruby/streak/publish gate đi **trọn** hệ từ vựng, không bảng mới nào khác. Import qua `parse_collocation` (WARNING heuristic điền-thử distractor — tách field riêng, không chặn commit), PATCH sửa-sau-commit, discovery `GET /vocabulary-collocations`, slot-fill quiz `collocation=1` chấm server-side stateless bằng `gap_word`, `renderGap()` theo token. Admin `/admin/collocation`. 238 published: 179 nhập từ file wrap + 59 entry phrase legacy nâng tay (distractor particle tránh cặp đối nghĩa thật). Cây: cuốn **"300 collocations hay gặp trong TOEIC"** trong bộ Từ vựng TOEIC, 13 chủ đề nhóm theo họ từ (TAKE/MAKE/DO/GET/GO/COME/CATCH/BREAK, KEEP-PAY-SAVE, adj+noun, noun compound, phrasal, prep phrase). Audio 1 432 clip v3 đã lên object store; **production đã sync** qua `scripts/export-collocation.sh` (ON CONFLICT DO UPDATE/DO NOTHING, idempotent) | `SPEC-COLLOCATION.md` |

## 3. Việc còn mở, theo thứ tự nên làm

### Nội dung — chặn mọi thứ khác

- [x] ~~**Vá giải thích cho `tp-form-06/07/08`**~~ — **Xong.** Backfill 2026-09-04:
      **834/855** câu có giải thích, chỉ còn 21 trắng. Công cụ:
      `app/content/backfill_explanations.py`, runbook §11b. Ngưỡng RAG (`ADR-003` §3.3)
      đã vượt xa từ lâu; nút thắt nội dung giờ là **chất lượng**, không phải số lượng.
- [x] ~~Chuẩn hoá prompt Part 2–7 theo learner-guide + siết độ khó~~ — **Xong
      (2026-09-10).** Mỗi `partN_system.md` đối chiếu `content/parts/part-N.md`;
      `part-5.md` vốn là bản copy của part-4 nên viết lại. Explanation: mọi đáp án
      nhiễu **khớp chữ** phải trích đúng cụm bị mượn và nói chữ nào bị bẻ (ngày,
      người, chỗ, chiều hành động), "not mentioned" chỉ dành cho đáp không có thật
      trong ngữ liệu. D3 (phần Nghe chỉ có MỘT dạng câu khó, MỘT khuôn): mix rải
      `*_IMPLICATION` 3→6 cụm mỗi part, thêm `implication_kind` quay 4 biến thể (y
      `how_variant`). D2 và D5 đã xem và **quyết không làm** — lý do ở
      `SPEC-EXAM-DIFFICULTY` §10. 1155 test API xanh.
- [x] ~~Soạn ≥ 50 câu dictation~~ — **134 câu / 17 bài / 3 chủ đề**. Chủ đề `Announcements`
      thêm ở đợt này vì dạng độc thoại (thông báo, tin nhắn thoại) là Part 4 và cây cũ
      không có bài nào thuộc dạng đó
- [x] ~~Bộ "600 từ vựng thiết yếu" đủ 600 từ~~ — **600 từ / 14 chủ đề**. Ba chủ đề thêm ở
      đợt này (`Restaurants & Dining`, `Health & Medical`, `Manufacturing & Quality`) chọn
      theo mảng TOEIC thật sự hay hỏi mà bộ cũ trống hoàn toàn, không phải nhồi cho tròn số
- [ ] Ảnh Part 1 chọn tay, ghi giấy phép (`ADR-004` §2.1)
- [ ] `question.source` điền đúng từng hàng — **không** chép đề ETS thật

### Bảo mật và vận hành

- [ ] **Bật branch protection** — treo từ Sprint 0, cần quyền admin repo. 4 gate không ai
      bắt buộc thì chỉ là gợi ý
- [ ] **Xoay mật khẩu database production** — đã lộ trong một phiên làm việc (2026-09-01)
- [ ] Cron ping giữ Supabase khỏi ngủ sau 7 ngày. Kiểu hỏng là **chỉ audio 404**
- [x] ~~Giới hạn đăng nhập đếm theo **tài khoản**~~ — **không làm, và không cần nữa.** Thế
      lưỡng nan là thật: đếm theo IP không chặn được botnet xoay IP, đếm theo tài khoản thì
      ai cũng khoá được tài khoản người khác. Turnstile là lối ra thứ ba — nó không đếm gì
      cả, nó bắt mỗi lần gửi form trả một cái giá tính toán (`ADR-015` §1)
- [ ] **Mua một tên miền.** Nó đang chặn BA thứ cùng lúc, và đó là dữ kiện đáng chú ý hơn
      từng thứ riêng lẻ: R2 (`ADR-006` §2.8a), toàn bộ nửa proxy của Cloudflare — chống
      DDoS, WAF, giấu IP gốc (`ADR-015` §0, §8) — và đăng nhập Apple. Kèm một cái bẫy hỏng
      im lặng phải xử lý cùng lúc với việc trỏ nameserver: `client_ip()` đọc hop cuối của
      `X-Forwarded-For`, mà sau Cloudflare hop cuối là IP CỦA Cloudflare, nên cả thế giới
      dùng chung một khoá rate limit (`ADR-015` §8)
- [ ] Monitoring và deploy — phương án chốt ở `adr/ADR-014-DEPLOY-FREE.md`, chưa dựng

### Lớp AI

- [ ] **Eval harness** — chưa có. `AI-ENGINEERING-PLAN` §7e nói phải làm *cùng lúc* với
      tính năng; bốn tính năng AI đã ship trước nó, nên đây là nợ có thật
- [ ] Viết lại `AI-ENGINEERING-PLAN` §9b — ngưỡng ở đó hiệu chỉnh cho bộ 8 nhãn, bảng thật
      có **72 mã**, nên "nhãn nhỏ nhất ≥5%" sẽ báo động mọi thứ
- [ ] Gắn nhãn nốt: **838/855** câu đã có — còn 17
- [ ] Prompt caching — đòn bẩy chi phí lớn nhất chưa dùng
- [ ] Structured output cho study plan
- [ ] AI Study Planner — **chặn bởi dữ liệu**: `target_score` mới điền trên 3/53 hồ sơ

### Tính năng còn thiếu

- [x] ~~Bài test đầu vào + planner V1~~ — **Xong (2026-09-07).** Đề
      `tp-placement-01` 84 câu pick theo nguyên cụm từ `tp-test-09` qua
      `app/content/make_placement.py` (định mức §0 của spec), máy thi tái dùng
      đường `/attempts`, `placement_result` (067) với estimator v1 (tỉ lệ + CI
      95% ≈ ±75 điểm, CEFR theo bảng ETS từng section, trần C1 — không phát minh
      C2), cooldown retake 7 ngày, mốc điểm tự khai trước bài, màn setup + kết
      quả tại `/learn/placement`; dashboard có CTA viền gradient (ngoại lệ §6)
      + bước đầu tiên của tour. Planner V1 rule-based: `study_plan`/`study_plan_item`
      (068), kỹ năng yếu → bài học grammar / part drill, exam_date co ngân sách
      mục, tiến độ suy từ bản ghi học thật, `/learn/plan`; mục tiêu ôn thi là
      MỘT nguồn `user_profile` (form placement prefill + ghi về). Lát 3:
      planner V2 LLM (`study_plan` qua `AiFeatureConfig`, chọn từ danh sách
      ứng viên, fallback rule khi hỏng/tắt) + màn admin so sánh
      `/admin/planner-compare` (chạy V1/V2 cùng input, lưu `planner_eval`
      069, tổng hợp cost/trễ từ sổ `ai_interaction`) — `SPEC-PLACEMENT.md`.
      **Review 2026-09-07 (§9 của spec):** màn kết quả nay hiện DẢI tổng chứ
      không một con số; migration 070 thêm `listening_scaled`/`reading_scaled`
      vì trung điểm dải lệch điểm quy đổi thật tới 22 điểm/section; lượt bỏ dở
      không thành phán quyết A1 và không tiêu cooldown; `POST /attempts` từ chối
      đề placement; `is_placement` sửa `server_default` (chuỗi trần làm MỌI đề
      đọc ra là placement trên SQLite); `POST /placement/start` có test.

- [x] ~~Màn quản trị thành viên~~ — **Xong (2026-09-07).** `/admin/users` +
      `admin_users.py` (6 endpoint, mọi thứ `require_role("admin")`): danh sách
      kèm số dư ruby / hoạt động cuối / số đề đã làm (UNION sáu bảng hoạt động),
      thống kê tăng trưởng 30 ngày gom theo Python (không `date_trunc` — SQLite
      của bộ test không có), tạo tài khoản có mật khẩu, đổi quyền, xoá (chặn
      tự-thao-tác trên chính mình), cấp ruby qua sổ cái `admin_grant` — không có
      ô sửa số dư.

- [x] ~~`GET /practice/parts/{part}`~~ — **Xong, cả khu.** Bảy endpoint
      (`/practice/parts`, tactics, CRUD phiên: POST sessions, GET list/detail,
      answers, finish), phân loại theo nhãn taxonomy thật (checkbox nhiều nhãn,
      rỗng = tất cả), passage đi kèm một
      lần mỗi cụm, hai tầng published. Một phiên lấy **toàn bộ** kho của
      part/nhãn + đồng hồ tự chọn (không giới hạn hoặc 5–135 phút, bước 5) —
      theo khuôn khu luyện thi: server tính `remaining_seconds`, hết giờ thì
      đọc/ghi tiếp theo chốt phiên `expired`. Chiến thuật Part 1–7 vào DB
      (`part_tactics`, 063; phiên + cột giờ + labels JSON: 064/065/066) — nguồn soạn vẫn là
      `apps/web/content/parts/*.md`, đồng bộ một chiều bằng
      `scripts/sync-parts.sh [--prod]`. Chưa có XP/streak cho drill part —
      quyết định sản phẩm mở, không phải dây nối còn thừa.
- [ ] **Ngữ pháp: bài practice cho các chủ đề taxonomy** — lý thuyết đủ 18/18;
      mới có "Luyện tập 1" (Danh từ). Gắn câu từ kho theo nhãn qua admin, mỗi
      chủ đề một bài là đủ dùng (`SPEC-GRAMMAR.md` §2)
- [ ] `streak_bonus` — nguồn XP duy nhất của `USER-ROAD.md` §2.3 chưa dựng
- [ ] Đăng nhập Apple — cần tài khoản Apple Developer và domain HTTPS
- [ ] Gỡ liên kết nhà cung cấp + đặt mật khẩu lần đầu, trong trang hồ sơ
- [x] ~~**Trần XP giảm dần** thay cho `DAILY_XP_CAP = 30` chặn cứng~~ — xong. 30 điểm đầu
      ăn đủ suất, phần sau ăn một phần năm. Đường cong đo trên **tổng thô của ngày**
      (`pet_owned.xp_raw_today`, migration 053), không trên từng lượt: chia tỉ lệ mỗi lượt
      thì một lượt đáng một điểm sau mốc thành `1 // 5 = 0`, tức lại là trần cứng, chỉ
      khác chỗ đặt. Chọc cũng thôi trả XP khi tinh thần đã cao
- [x] ~~Tấm ghép sinh vật thứ hai~~ — **Xong (2026-09-07).** `pet_species.sheet` (migration 072) + `CreatureSheetId` khai ở API để đi qua OpenAPI thành union TS; `petland-sprite.ts` nay là nơi DUY NHẤT biết đường dẫn và số cột (trước đó `creatures.png` viết cứng ở bốn tệp). `app.content.pack_sprites` đóng ảnh sinh ra thành tấm 16×16 ép về đúng 22 màu — nền nhận bằng **liên thông từ mép**, không bằng ngưỡng màu. Hai tấm mới: `dinos.png` 16 ô, `myth.png` 32 ô. Màn `/admin/pet` có nút thêm loài và **lưới chọn ô bằng mắt** thay cho ô nhập số. **Còn nợ: giấy phép của hai tấm mới chưa xác định** (`public/pet/CREDITS.md`) — `PETLAND-SPRITE-PROMPTS.md`
- [ ] Petland lát 5 — nhiệm vụ trắc nghiệm, **chờ nội dung** (`ADR-012` §8.3)
- [ ] Lối vào `MatchGame` từ trang chủ đề (vẫn tới được bằng URL trực tiếp)
- [ ] Test component/frontend — **cố ý chưa làm**: mọi lỗi giao diện của dự án này đều ở
      chỗ nối, và e2e mới bắt được chúng

## 4. Nợ kỹ thuật đang mở

| Mục | Ở đâu | Ghi chú |
|---|---|---|
| Hai trang admin không có e2e | `REFACTOR-LONG-FILES.md` §4b | `/admin/progression`, `/admin/tests/[slug]` |
| Token trong `localStorage` | P1-7b, `ADR-015` §6 | **Nợ mở, không còn lý lẽ.** Lý do hoãn là "không script bên thứ ba nào"; Turnstile đã nhúng một cái vào đúng các trang ghi token. ADR-008 §1 đòi trả nợ này TRƯỚC — thứ tự ấy đã bị đảo có ý thức, không phải bỏ sót |
| Ảnh không tái tạo được | `MEDIA-PIPELINE.md` §10.3 | Đầu vào là URL của người khác; `media/` bị gitignore ⇒ thư mục media là **bản sao duy nhất** |
| `seed` không bao giờ xoá | `MEDIA-PIPELINE.md` §10.4 | Xoá dòng khỏi manifest ⇒ hàng DB ở lại vĩnh viễn |
| Không gì kiểm media còn phục vụ được | `MEDIA-PIPELINE.md` §10.8 | Sai `AUDIO_PUBLIC_BASE_URL` ⇒ mọi media 404 mà container vẫn healthy |
| Bảng quy đổi điểm là **xấp xỉ** | `score_scale.source_note` | Không phải bảng chính thức của ETS |
| Bản quyền đề ETS | `adr/ADR-005` §2 | `question.source` phải đúng ở **từng hàng** |
| ~~1 125 clip ở tốc độ đọc cũ~~ | `PHASE2-AUDIO.md` §A4.6 | Xong. Kho dev đồng nhất một phiên bản; **production thì chưa** |
| ~1 500 hàng asset mồ côi | `reconcile_media` | Toàn `tts`, sinh lại được từ manifest |

## 5. Cách cập nhật tệp này

- **Chỉ tệp này mang trạng thái.** ADR mang quyết định, `SYSTEM-OVERVIEW`/`MEDIA-PIPELINE`/
  `EXAM-GRAPH` mang hành vi hiện tại, `archive/` mang lịch sử.
- **Số đo phải kèm lệnh đo.** Bảng §1 sai ở mọi dòng suốt hai tuần vì không ai đo lại được
  mà không đọc source. Nếu thêm một con số, thêm cả cách lấy nó.
- **Việc xong thì xoá khỏi §3, không tick rồi để đó.** Bản cũ có 432 ô đã tick trên 470 —
  tỉ lệ đó là lý do không ai đọc nó nữa.
- **Sprint đã đóng thì chuyển sang `archive/`**, kèm banner nói rõ nó không còn được cập
  nhật.
