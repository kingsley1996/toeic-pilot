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
| Test API | **1018 passed**, 8 skipped, 2 `external` deselect |
| E2E | 8 tệp, **22 passed / 4 skipped** |
| Gate CI | 4 job xanh. **Branch protection chưa bật** |
| Bảng · migration | 62 · 62 |
| Endpoint | **217 thao tác** (132 admin) |
| Route web | 55 |
| Nội dung | **6 đề / 855 câu** (834 có giải thích) · **600 từ vựng / 14 chủ đề** · **134 câu dictation / 17 bài** · **ngữ pháp: 18/18 chủ đề published / 20 bài học** |
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

## 3. Việc còn mở, theo thứ tự nên làm

### Nội dung — chặn mọi thứ khác

- [x] ~~**Vá giải thích cho `tp-form-06/07/08`**~~ — **Xong.** Backfill 2026-09-04:
      **834/855** câu có giải thích, chỉ còn 21 trắng. Công cụ:
      `app/content/backfill_explanations.py`, runbook §11b. Ngưỡng RAG (`ADR-003` §3.3)
      đã vượt xa từ lâu; nút thắt nội dung giờ là **chất lượng**, không phải số lượng.
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

- [ ] `GET /practice/parts/{part}` — luyện theo part rời, tôn trọng `question_set`.
      Lý thuyết Part 1–7 (P1 của ngữ pháp) nên ship cùng lát này, không dựng bộ máy
      bài học riêng (`SPEC-GRAMMAR.md` §3)
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
