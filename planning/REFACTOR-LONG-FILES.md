# Tách những tệp đã quá dài

**Trạng thái: đợt 1 và 2 xong (2026-09-01), đợt 3 chưa bắt đầu.** Đây là kế
hoạch, không phải bản ghi việc đã làm —
`ROADMAP.md` vẫn là nơi duy nhất mang trạng thái. Số đo trong tài liệu này lấy
ngày **2026-09-01** và sẽ mục đi; đo lại trước khi làm.

## 0. Dài không tự nó là lỗi

Đây là điều phải đọc trước, vì nó quyết định phần lớn nội dung bên dưới. Repo
này chống nghi thức thừa: quy ước test nói thẳng rằng một bài kiểm chỉ để nâng
con số là chi phí không có phần thu, và cùng lý lẽ ấy áp cho việc chẻ tệp. Một
tệp 900 dòng khai báo model không có gì sai; một tệp 1 400 dòng trộn hai miền
không liên quan thì có.

Nên tiêu chí là **lý do ngoài con số**:

- **Tách** khi tệp trộn những thứ *đổi vì lý do khác nhau* — dictation và từ
  vựng nằm chung một router; hoặc trộn *dữ liệu người ta chỉnh* với *mã*.
- **Không tách** khi dài mà một mạch: khai báo model, khai báo schema, một vòng
  `requestAnimationFrame` có state đan nhau.

Ba đợt dưới đây xếp theo **giá trị chia cho rủi ro**, không theo số dòng. §4 nói
rõ những tệp dài mà cố ý *không* đụng vào, và vì sao — phần đó dễ bị người đến
sau "sửa nốt cho đều", nên nó có lý do viết ra thay vì để suy đoán.

## 1. Đo được gì (2026-09-01)

`apps/api/app` có 175 tệp, 39 662 dòng. Những tệp trên 800 dòng:

| Tệp | Dòng | Bên trong |
|---|---|---|
| `apps/web/src/app/admin/tests/[slug]/page.tsx` | 1939 | một component 1 043 dòng + 7 component con |
| `apps/web/src/components/petland.tsx` | 1862 | `PetPanel` một mình 1 516 dòng |
| `app/api/routes/admin_tests.py` | 1612 | 28 endpoint, 26 helper |
| `app/api/routes/admin.py` | 1479 | 41 endpoint: **19 dictation + 14 từ vựng** |
| `app/content/exam/blueprint.py` | 1332 | **613 dòng bảng dữ liệu + 719 dòng mã** |
| `app/api/routes/learning.py` | 1317 | 22 endpoint, hai miền tách bạch |
| `apps/web/src/app/learn/attempts/[attemptId]/page.tsx` | 1190 | một component 422 dòng + 11 component con |
| `app/content/exam/check.py` | 1097 | 15 bảng + 18 phép kiểm |
| `apps/web/src/app/admin/progression/page.tsx` | 1088 | 5 cặp `Section` + `Row` |
| `apps/web/src/components/petland-render.ts` | 1040 | lớp vẽ |

## 2. Đợt 1 — Tách router theo tài nguyên

Rủi ro thấp nhất, giá trị cao nhất, và làm trước. Ba tệp to nhất bên API đều là
tệp trộn hai miền không liên quan gì nhau.

| Từ | Thành | Endpoint |
|---|---|---|
| `admin.py` 1479 | `admin_dictation.py` · `admin_vocabulary.py` | 19 · 22 |
| `admin_tests.py` 1612 | `admin_tests.py` (đề + bộ sưu tập) · `admin_questions.py` (câu + cụm + giọng) | 17 · 11 |
| `learning.py` 1317 | `learning_vocabulary.py` · `learning_dictation.py` | 14 · 8 |

**Vì sao an toàn.** Mỗi tệp route tự giữ `APIRouter` của nó và `app/main.py` gắn
phẳng bằng `include_router(..., prefix="/api/v1")`. Tệp mới chỉ cần khai đúng
`prefix="/admin"` và **đúng `tags`** cũ, rồi thêm một dòng `include_router`.
Không URL nào đổi, nên frontend và hợp đồng API không phải sửa gì.

**Bẫy: helper dùng chung.** `admin_tests.py` có 26 helper cho 28 endpoint
(`_question_admin`, `_set_admin`, phép kiểm lời thoại). Helper nào cả hai tệp
cần thì đưa sang một mô-đun riêng — `app/api/routes/_admin_content.py` — chứ
**không** để một router `import` router kia. Router import router là cách nhanh
nhất biến hai tệp thành một tệp có hai cái tên.

### 2b. Đã làm — kết quả và hai thứ không lường trước (2026-09-01)

Ba tệp 4 408 dòng thành sáu tệp cộng hai mô-đun dùng chung:

| Tệp | Dòng |
|---|---|
| `admin_questions.py` | 1076 |
| `admin_dictation.py` | 842 |
| `learning_vocabulary.py` | 836 |
| `admin_vocabulary.py` | 668 |
| `learning_dictation.py` | 519 |
| `admin_tests.py` | 478 |
| `_admin_tests_shared.py` | 145 |
| `_admin_content.py` | 23 |

**Hai thứ không lường trước, cả hai đều là helper dùng chung — đúng loại §2 đã
cảnh báo, chỉ là nhiều hơn dự kiến:**

- `_apply` (gán trường theo `exclude_unset`) nằm ở nửa dictation nhưng nửa từ
  vựng cũng gọi. `ruff` bắt được ngay bằng F821. Nó thành `_admin_content.py`.
- **`pet.py` import thẳng hai hàm từ `learning.py`** — `_apply_review` và
  `record_dictation_attempt`. Một router gọi handler của router khác; lần rà
  trước khi làm đã bỏ sót vì tôi loại trừ chính thư mục `routes/` khỏi lệnh
  grep. Lần này chỉ sửa đường import cho đúng (vẫn là phép dời theo §7); đưa hai
  hàm đó xuống `app/services/` là một **thay đổi**, nên để riêng.

`admin_tests.py` là tệp rối nhất và số đo nói rõ vì sao: 4 helper riêng của nửa
đề, 15 riêng của nửa câu hỏi, **7 dùng chung**. Bảy cái đó trả lời cùng một câu
hỏi ở tầng đề — đề này có tồn tại không, ai được xoá, xoá rồi cụm rỗng đi đâu —
nên chúng thành `_admin_tests_shared.py` chứ không nhân đôi.

**Kiểm.** Bề mặt API giống hệt: 189/189 thao tác, `diff` rỗng trên cả
`(method, path, operationId, params, body, responses)`. `pnpm gen:api-types`
sinh lại **không một byte khác**. `pytest` 949 passed. Và phép kiểm chặt nhất
cho luật "chỉ được là phép DỜI" ở §7: băm AST của **145 hàm** trước và sau —
không hàm nào mất, không hàm nào thêm, **không hàm nào đổi thân**. Chênh lệch
+185 dòng (8,1%) là docstring của tám mô-đun mới cộng các khối import lặp lại.

## 3. Đợt 2 — Tách dữ liệu khỏi mã

**`blueprint.py` 1332 → `exam/mixes.py` (613 dòng bảng) + `blueprint.py` (719
dòng mã).** Hai mươi mốt bảng hằng — `PART1_MIX`, `PART3_MIX`,
`BUSINESS_CONTEXTS`, các pool hình, dàn giọng — là *nội dung người ra đề chỉnh*,
còn `_deal`/`_spread`/`validate` là *mã*. Để chung nghĩa là sửa một bối cảnh
công sở phải mở cùng tệp với thuật toán rải giọng, và ngược lại.

**`check.py` 1097 → tách theo part** dưới `exam/checks/`, giữ `check.py` làm
điểm vào. Ba hàm dài nhất — `_check_set` (156 dòng), `check_blueprint` (151),
`check_graphic` (150) — độc lập nhau.

### 3b. Đã làm — và một chỗ kế hoạch này đoán sai (2026-09-01)

**`blueprint.py` 1332 → `blueprint.py` 756 + `mixes.py` 622.** Đúng như dự tính.
Ranh giới cuối cùng đặt ở **AI CHỈNH**, không ở "có phải hằng số không":
`PEOPLE_SHAPES`, `QUESTIONS_PER_SET` và `GRAPHIC_POSITION` ở lại cùng mã, vì
không ai chỉnh chúng cho một đề khác đi — chúng là bất biến của định dạng mà
`validate` cưỡng chế, và đổi một cái nghĩa là mã sai chứ không phải đề khác.
Không tệp nào bên ngoài phải sửa: mọi thứ nơi khác import từ mô-đun này đều nằm
trong phần ở lại.

**`check.py` 1097 → `check.py` 980 + `check_prompts.py` 168. Và §3 đã đoán sai
về tệp này.** Kế hoạch nói tách theo part; đo ra thì các phép kiểm **gần như
không phụ thuộc part** — chỉ 12 nhánh rẽ theo part trên toàn tệp — nên chẻ theo
part sẽ nhân đôi phần dùng chung thay vì tách được gì. Cái tách được là prompt
gửi cho mô hình, theo đúng ranh giới "chữ người ta chỉnh" đã dùng cho `mixes.py`.

Nên `check.py` ở lại **980 dòng** và đó là kết quả đúng, không phải việc làm dở:
§0 nói không tách khi dài mà một mạch, và cả tệp ấy là một mạch — "nội dung sinh
ra có đạt không". Ép nó thành bốn tệp là làm đúng cái nghi thức thừa mà §0 tồn
tại để chặn.

**Kiểm.** AST: blueprint 44/44 định nghĩa không đổi, check 41/41 không đổi.
`pytest` 949 passed. Và phép kiểm §6 cho đợt này: sinh lại **28 blueprint**
(4 seed × 7 part) trước và sau — băm SHA-256 **giống hệt**, `validate` sạch trên
cả 28.

## 4. Đợt 3 — Frontend: kéo component ra khỏi page

Next.js chỉ cần `page.tsx` export default, nên component con để cạnh nó trong
`_components/`: thư mục có tiền tố `_` không thành route.

Thứ tự trong đợt này quan trọng, vì độ khó chênh nhau rất xa:

1. **`admin/progression/page.tsx` 1088** — dễ nhất, làm trước để chạy thử quy
   trình. Năm cặp `Section` + `Row` (rates, curve, slots, frames, badges) thành
   năm tệp; page còn lại là khung và state chung.
2. **`learn/attempts/[attemptId]/page.tsx` 1190** — 11 component thuần trình bày
   (`Countdown`, `PartTabs`, `QuestionCard`, `StimulusBlock`, `ResultScreen`…).
   `AttemptRunnerPage` còn khoảng 420 dòng, chấp nhận được.
3. **`admin/tests/[slug]/page.tsx` 1939** — nặng nhất, làm **cuối**, và **chia
   làm hai commit**: (a) chuyển 7 component con ra ngoài, (b) mới tách state của
   `AdminTestPage` (1 043 dòng). Gộp hai bước là tự bỏ khả năng bisect đúng lúc
   cần nó nhất.

## 5. Những tệp dài cố ý KHÔNG đụng

- **`petland.tsx` 1862.** `PetPanel` là một vòng `requestAnimationFrame` với
  state đan nhau, và hai cái bẫy ở đúng chỗ đó đã được ghi lại: mascot phải đọc
  qua `ref` chứ không qua closure (closure giữ mascot cũ mãi mãi, bộ chọn trông
  như chết), còn đưa `mascot` vào deps thì `frameAcc` reset và con thú nhảy giật
  đúng lúc người dùng bấm. Tách nó là chạm vào chỗ dễ hỏng nhất để đổi lấy một
  con số đẹp hơn. Thêm nữa, `scripts/check-petland-layers.mjs` sẽ phải có luật
  cho mọi tệp mới — chi phí thật, không phải giả định.
- **`models/pet.py` 812, `schemas/admin.py` 629, `petland-render.ts` 1040.**
  Khai báo và một lớp vẽ; dài là bản chất của chúng.
- **`tests/test_exam_generation.py` 1669.** Test được đọc bằng tìm kiếm, không
  đọc từ trên xuống.

## 6. Cách kiểm từng bước

Mỗi đợt có một phép kiểm riêng, và không đợt nào được nhận là xong nếu chỉ dựa
vào việc đọc diff.

**Router (đợt 1).** So tập `(method, path, operationId, response schema)` trước
và sau bằng một script dùng một lần — phải giống hệt. Rồi `pnpm gen:api-types`:
diff duy nhất được phép là thứ tự khoá `paths`, và phải xem tận mắt chứ không
commit nhắm mắt. Cộng `uv run pytest` đầy đủ.

**Dữ liệu (đợt 2).** `pytest tests/test_exam_generation.py` phủ dày phần này;
thêm một phép kiểm bằng tay: sinh lại blueprint của một đề với **cùng seed** rồi
so JSON — phải giống hệt từng byte.

**Frontend (đợt 3).** `tsc --noEmit` bắt được sai kiểu props nhưng **không** bắt
được state vốn nằm trong closure nay phải truyền xuống. Nên mỗi bước phải chạy
`pnpm --filter @toeic-pilot/web test:e2e` với docker stack đang chạy: mọi lỗi
frontend dự án này từng gặp đều nằm ở đường nối, và đó đúng là loại lỗi e2e tồn
tại để bắt.

## 7. Ba luật chung

- **Mỗi tệp một commit.** Tám commit nhỏ, không phải một commit năm nghìn dòng.
  Một hồi quy phải bisect được.
- **Chỉ được là phép DỜI.** Không sửa logic, không đổi tên, không "tiện tay dọn
  luôn". Thấy chỗ cần sửa thì ghi lại và sửa ở commit riêng sau đó — trộn vào
  đây là làm mất tính chất khiến cả việc này an toàn.
- **`git diff --stat` phải gần cân bằng.** Số dòng thêm xấp xỉ số dòng bớt. Lệch
  nhiều nghĩa là đã viết lại chứ không dời, và phép kiểm ở §6 không được thiết
  kế cho việc viết lại.

## 8. Thứ tự đề nghị

1. `admin.py` → 2. `learning.py` → 3. `admin_tests.py` → 4. `blueprint.py` →
5. `progression/page.tsx` → 6. `attempts/[attemptId]/page.tsx` → 7. `check.py` →
8. `admin/tests/[slug]/page.tsx`

Ước lượng thô: đợt 1 nửa ngày, đợt 2 nửa ngày, đợt 3 một ngày — riêng
`admin/tests/[slug]` chiếm phần lớn của đợt cuối.
