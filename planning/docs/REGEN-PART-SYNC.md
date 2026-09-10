# Thay một Part của đề đã publish, rồi đồng bộ lên production

Runbook cho thao tác: **một đề đã load + publish, nhưng một Part (ở đây Part 1) có
chất lượng kém / trùng với các đề khác** → sinh lại Part đó, làm lại media, và cập
nhập đúng đề đó trên production **mà không đụng các Part còn lại**.

Khác hai runbook anh em:
- `EXAM-GENERATION-RUNBOOK.md` — dựng **đề mới** từ đầu.
- `SYNC-TEST-TO-PRODUCTION.md` — đưa **đề mới** dev → prod.

Cái này là **thay nội dung một phần của đề đã có**, nên hai chỗ không có ở đề mới:
`load` chỉ **cộng thêm** (phải xử lý hàng cũ), và production **đã có attempt** cho đề
đó (phải xử lý ràng buộc FK).

## 0. Điều kiện và khoá

- Stack dev chạy (`postgres`, `redis`, `api` ở `ENVIRONMENT=development`).
- Khoá `$SUPABASE_URL` (prod, **thực ra đang là staging alpha** — attempt là data
  thử, chấp nhận mất; xem §5 trước khi đổi giả định này).
- Token editor: mint JWT **ngay trong container `api`** để đúng `SECRET_KEY` với API
  đang phục vụ. `require_role` chỉ cần `sub` = id một user `editor`/`admin`:

  ```bash
  docker compose -f docker/docker-compose.yml exec -T api sh -c \
    'uv run python -c "from app.core.security import create_access_token; print(create_access_token(\"<user-id>\"))"'
  ```

  Token hết hạn sau `ACCESS_TOKEN_EXPIRE_MINUTES`; mint lại khi cần. **Không** commit
  token hay `$SUPABASE_URL`.

## 1. Sinh lại Part 1 (bốn chặng cục bộ trên tệp)

```bash
cd apps/api
S=tp-form-07
mv content/generated/$S/paste/p1-0?.txt <thư-mục-backup>   # write chỉ sinh Ô CÒN THIẾU
uv run python -m app.content.generate_exam plan   --slug $S --part 1 --model bai/mimo-v2.5
uv run python -m app.content.generate_exam write  --slug $S --part 1 --model bai/mimo-v2.5
uv run python -m app.content.generate_exam balance --slug $S --part 1
uv run python -m app.content.generate_exam check   --slug $S --part 1
```

**Vì sao `balance` không thể bỏ.** `write` đổ hết đáp án về một vị trí (đo trên
`tp-form-07`: 6/6 `Answer: A`). Một đề có sáu câu Part 1 cùng đáp án thì người học
đoán được mà không cần nghe. `balance` rải lại A/B/C/D và — nhờ thiết kế Explanation
"một segment mỗi phương án, chữ cái đi theo phương án" — giải thích vẫn đúng sau khi
đổi chỗ (`check` xác nhận).

**Cơ chế chống trùng liên-đề (Part 1).** `plan --model` đọc bối cảnh Part 1 của
`PART1_AVOID_WINDOW` (=8) đề **gần nhất** theo `mtime` — trừ chính đề đang chạy —
gom về **motif** qua `PART1_MOTIF_KEYWORDS`, rồi đưa vào `plan_part1_scenes` hai khối:
`{avoid}` (motif đã dùng → tránh) và `{lean}` (motif chưa dùng gần đây → ưu tiên thử).
Gom **motif** chứ không liệt câu văn: trùng lặp nằm ở chủ đề, hai câu khác từng chữ
cùng một nguyên mẫu ("thêm biến thể công trường nữa") vẫn là trùng. Cửa sổ trượt để
`sau ~10 đề` không rơi vào trạng thái "tránh cả thế giới, không còn gì để lean".

## 2. Ảnh Part 1 — vẽ lại, XEM, rồi mới gắn

```bash
rm content/generated/$S/images/p1-0?.png            # hàng đợi là truy vấn: không PNG = cần vẽ
uv run python -m app.content.generate_exam photo --slug $S
# >>> DỪNG LẠI. Người xem từng tấm. Sửa/tái sinh tấm nào chưa đạt. <<<
uv run python -m app.content.generate_exam attach-images --slug $S --part 1 --commit
```

- Ảnh chỉ lên Cloudinary **khi `attach-images --commit`**; `photo` chỉ vẽ ra đĩa.
- `--commit` **từ chối** khi còn "file thừa hoặc ô trống": một file `p1-01-draft.png`
  lạc giữa `images/` sẽ bị khớp nhầm vào ô rồi chặn cả lô. Dọn file rác trước.
- Hàng đợi `photo` = **`photos/p1-XX.txt` có mà `images/p1-XX.png` thiếu**, và `write`
  mới là chặng ghi `photos/p1-XX.txt`. **Đừng dời/xoá `photos/` sau `write`** — làm vậy
  xoá luôn thứ tự vẽ, `photo` báo "0 cần vẽ". Muốn vẽ lại một tấm chỉ `rm images/p1-XX.png`.
  (Một lần render lẻ thi thoảng ghi file rồi biến mất; `photo` bắt lại đúng ô trống đó.)
- **Reload trọn đề (§3) xoá luôn liên kết ảnh của các Part graphic (3/4/7).** Các
  `attach-images --commit` cho Part 1 KHÔNG khôi phục chúng. Phải chạy nốt:

  ```bash
  for p in 3 4 7; do uv run python -m app.content.generate_exam attach-images --slug $S --part $p --commit; done
  ```

  (File graphic vẫn còn trên đĩa; chỉ mất liên kết trong DB. `check` trước khi
  `--commit` cho thấy đúng `N khớp · 0 file thừa`.)

## 2b. Biệt lệ Part 2 (Question-Response)

Luồng y hệt, khác bốn chỗ (đã chạy thật trên `tp-form-07`):

- **Không có ảnh.** Part 2 chỉ nghe. `attach-images --part` không nhận `2`; **bỏ hẳn
  §2**. Reload vẫn phải attach lại 1/3/4/7 (chúng mất liên kết), nhưng Part 2 đóng góp 0 ảnh.
- **Ba phương án A/B/C.** `balance` biết điều đó (`balance.py`: không gán đích `D` cho
  Part 2), nên phân bố đọc kiểu `A=8 B=8 C=9 · D=0`.
- **Câu hỏi nằm ở `question.audio_script`** (không phải `prompt_text` — đề không in gì),
  mỗi câu **4 lượt nói** = 1 hỏi + 3 đáp → `backfill_audio --only questions` phủ Part 2,
  và regen 25 câu = ~25 tổng hợp (không reuse được như part khác vì nội dung đổi hết).
- **Cổng chất lượng là `check`**: "nhiễu Yes/No cho câu WH > 30%". `part2_system.md` đã
  có luật (sai ngay cả khi bỏ chữ Yes/No đầu câu), nhưng mimo vẫn lơ một phần. 07 đi từ
  **80% → 33% sau regen trọn → 27% sau khi re-roll đúng 1 ô** `check` gọi tên
  (`mv paste/p2-XX.txt` rồi `write` lại, nó chỉ sinh ô thiếu). Không cần re-plan cả part
  cho lần siết cuối.

## 3. Reload dev: xoá theo slug rồi nạp lại TRỌN đề

`load` **cộng thêm** (`commit_part` không thay thế) — nạp Part 1 vào đề còn nguyên
Part 1 sẽ thành 12 câu. Và `attempt` tham chiếu `question.id` của cả 6 câu cũ bằng
RESTRICT, nên "xoá đúng 6 câu Part 1" vướng FK. Đường gọn và khớp với prod (vẫn
export nguyên đề): **xoá trọn đề, nạp lại**.

```bash
TOK=$(cat /tmp/editor_token.txt)
curl -X DELETE -H "Authorization: Bearer $TOK" "http://localhost:8000/api/v1/admin/tests/$S?force=true"
uv run python -m app.content.generate_exam load --slug $S --token "$TOK"
uv run python -m app.content.backfill_audio --only questions --test $S
```

**`load` trọn đề tự gắn nhãn từ blueprint.** Xoá trọn đề kéo theo mọi `question_label`
rơi theo CASCADE (FK `ondelete`), và `export-test.sh` chỉ chép nhãn của dev — nên nếu
dev không nhãn thì prod cũng mất nhãn, và `make_placement` + màn phân tích kỹ năng câm
lặng hỏng. `cmd_load` gọi `apply_labels` khi nạp nguyên đề (không gọi khi `--part`/`--slot`,
vì các ô chưa nạp sẽ báo "chưa nạp câu"). Không còn bước nhãn thủ công.

**Không tốn TTS cho Parts 2–7.** `audio_asset` nội-dung-địa-chỉ (`source_hash`), và
`backfill_audio` tra theo hash trước khi gọi máy (`--dry-run` trên 07: `6 synthesised
· 48 reused · 48 linked`). Chỉ 6 câu Part 1 mới thực sự tổng hợp.

## 4. Push media rồi kiểm người học nghe/xem được

```bash
uv run python -m app.content.generate_exam media --slug $S --push
# ĐỌC provider bằng curl — hàng DB đúng không chứng minh object tồn tại:
curl -s -o /dev/null -w '%{http_code}\n' "$AUDIO_PUBLIC_BASE_URL/<storage_key>"
curl -s -o /dev/null -w '%{http_code}\n' "$IMAGE_PUBLIC_BASE_URL/$CLOUDINARY_FOLDER/<storage_key>"
```

Đường dẫn ảnh **phải có `$CLOUDINARY_FOLDER`**; thiếu đoạn đó ra 404 y hệt một ảnh
chưa đẩy.

## 5. Publish dev rồi export → prod

`load` để **draft**, và export-test.sh chép **nguyên `status`** → nếu không publish,
prod nhận về một đề draft (học viên không làm được). Có **hai** endpoint, chạy theo thứ
tự (mình đã dùng cho 07 và 08 — `load` đi qua HTTP nên tự khớp schema `practice_test`):

```bash
# (a) publish từng câu ĐẠT cổng `validate_question` (kèm cụm của nó); câu nào hỏng
#     thì nó bỏ qua và NÓI RÕ trong `skipped`, không im lặng:
curl -X POST -H "Authorization: Bearer $TOK" "http://localhost:8000/api/v1/admin/tests/$S/questions/publish"
# (b) publish cả đề — route này TỪ CHỐI 409 nếu còn câu draft, nên (a) phải sạch trước:
curl -X POST -H "Authorization: Bearer $TOK" "http://localhost:8000/api/v1/admin/tests/$S/publish"

./scripts/export-test.sh $S /tmp/$S.sql
docker run --rm -i postgres:17 psql "$SUPABASE_URL" --single-transaction -v ON_ERROR_STOP=1 < /tmp/$S.sql
```

**Đừng xuất bản bằng `UPDATE question SET status` viết tay.** Một bulk-publish bỏ qua
`validate_question` là cách chắc chắn nhất để một câu thiếu bản thu lọt ra ngoài.

**Luôn `--single-transaction`.** Tệp gồm nhiều COPY/INSERT autocommit; một statement
fail giữa chừng để prod nửa vời. Một transaction = all-or-nothing. (Lần đầu của chính
runbook này fail vì FK và **prod không hề đổi** — xem §6.)

**Kiểm sau khi áp** (đọc prod, schema `practice_test`): `practice_test.status='published'`,
đủ 200 câu **qua bảng nối** `practice_test_question` (không có `question.test_id` nữa),
Part 1 `is_correct` khớp bản đã balance, và `curl` một audio/ảnh URL trả **200**. Part 1
mang `audio_asset_id`/`image_asset_id` trên `question`; **Parts 3/4/7 mang media trên
`question_set`** (`audio_asset_id`, `passage_image_id`) nên `count(question.image_asset_id)`
bằng 0 ở ba part đó là **đúng**, không phải mất ảnh.

## 6. Ba bug RESTRICT đã gặp — và đã vá

Cả ba cùng một hình dạng: bảng lịch sử học viên **mới hơn** giữ `question_id`/`option_id`
kiểu `ondelete=RESTRICT`, và các đường xoá viết trước đó không biết tới chúng. Cả ba chỉ
lộ khi đề **đã có người làm / đã vào pool** — lần import đầu tiên không có attempt nên
không nổ.

1. `admin_tests.py::_delete_test_core` (route `DELETE /tests/{slug}?force`) chỉ purge
   `attempt`, bỏ quên `part_session_item` và `grammar_attempt` → `DELETE FROM question`
   nổ IntegrityError, trả **500**. Vá bằng `_purge_sessions_of_questions(db, doomed)`
   gọi trước khi xoá câu.
2. `scripts/export-test.sh` khối reset xoá `question_option` **trước** `attempt`;
   prod có `attempt_item` tham chiếu option RESTRICT → vi phạm FK. Vá bằng thứ tự
   con→cha: `attempt` → `part_session_item` → `grammar_attempt` → `question_option` …
3. **Pool placement** (ADR từ commit "publishing a form adds it to the pool"). Một đề đã
   publish bị `tp-placement-*` **tham chiếu đúng hàng `question` của nó** (không copy id),
   qua `practice_test_question` (test_id = đề placement) và `attempt_item` của attempt
   placement. Full-reload đổi **toàn bộ id** của đề → khối reset phải gỡ các liên kết
   phái sinh **ở mọi đề khác** chứ không chỉ `test_id = slug`. Vá: `DELETE FROM
   attempt_item` theo `question_id IN _tp_q OR selected_option_id IN (options của _tp_q)`;
   `practice_test_question … OR question_id IN _tp_q`; thêm `grammar_lesson_question`.
   Dấu hiệu nhận biết: import fail `violates … _fkey on table "practice_test_question"`
   ngay sau khi lỗi option đã hết. **Chỉ an toàn vì placement ở prod là archived/thử.**

`DELETE FROM attempt WHERE test_id=…` trong cả hai đường là **cố ý** và có chủ đích
phá lịch sử làm bài của đề đó. Nó chỉ an toàn vì prod đang là staging. Ngày đề có học
viên thật, đừng chạy đường này cho part-swap — dùng hướng "UPDATE tại chỗ, giữ nguyên
`question.id`" (`export-explanations.sh` là khuôn mẫu).

## 7. Bẫy của `cmd_plan` (đã sửa)

`cmd_plan` từng `validate` **toàn bộ blueprint đã merge**. Một đề có lỗi ở Part 4
(hợp lệ lúc ra đời, phạm quy sau khi luật accent siết) sẽ **chặn đứng việc regen bất
kỳ Part nào khác**, và `--model` vứt luôn nội dung vừa sinh vì `return 1`. Vì mọi bất
biến của `validate` đều per-part, `cmd_plan` giờ chỉ validate part vừa build; phần còn
lại của form vẫn do `check` và cổng publish giữ.

## Ghi chú tái sử dụng

- Đổi `S` sang đề khác. Ba đề đã đi qua đường này: `tp-form-07`, `tp-form-08`,
  `tp-test-09` (tên là `test` nhưng nó là đề `full` đã publish thật, **không phải**
  artifact). `tp-form-09` thì không tồn tại.
- **Đề đã vào pool placement thì phải có các DELETE §6.3** — nếu không import fail vì
  `practice_test_question`/`attempt_item` của đề placement RESTRICT-trỏ vào câu đề này.
- `--model` cho Part 1: gemini free (`google/gemini-3.7-flash`) hoặc `bai/mimo-v2.5`.
  `--model` cho `write` có thể khác; chạy chậm (mimo ~60–225s/câu), cứ để nền.
- Paste + `blueprint.json` + `.prompt.txt` là **tệp commit** (nguồn tái tạo); `.mp3`,
  `.png` gitignore (đã ở provider).
