# Luồng sinh đề bằng đồ thị — mô tả hành vi hiện tại

Đây là **mô tả cái đang chạy**, không phải bản ghi quyết định. Cùng loại với
`ARCHITECTURE.md` và `MEDIA-PIPELINE.md`: đọc để định hướng, còn `ROADMAP.md`
vẫn giữ trạng thái. Mọi con số dưới đây lấy từ chính mã (`build_part*`,
`QUESTIONS_PER_SET`, `GRAPHIC_POSITION`, `letters_for`) chứ không chép tay, và sẽ
sai đi khi các bảng đó đổi.

Đo ngày 2026-08-31.

---

## 0. Hai cửa vào

| lệnh | làm gì | dùng khi |
|---|---|---|
| `app.content.exam_agents.full` | `plan → slotloop → balance → spread` | sinh trọn đề từ một `--slug` |
| `app.content.exam_agents.graph` | chỉ `slotloop` | blueprint đã có, chỉ viết ô còn thiếu |

`full` gọi lại `run_pending` của `graph` chứ không có bản sao — vòng per-slot chỉ
tồn tại một chỗ.

```bash
cd apps/api

uv run python -m app.content.exam_agents.full \
  --slug tp-form-08 --model bai/glm-5.3-flash [--part N] [--verify]

uv run python -m app.content.exam_agents.graph \
  --slug tp-form-08 --model bai/glm-5.3-flash [--part N] [--limit N] [--verify]
```

---

## 1. Đồ thị ngoài — cả đề

```
START → plan → slotloop → balance → spread → END
```

**`plan`** — có blueprint rồi thì **bỏ qua và không gọi model lần nào**. Đây là
cơ chế chạy lại giữa chừng: một lượt `full` bị Ctrl-C rồi chạy lại sẽ không đốt
quota để dựng lại thứ đã có. Chưa có thì gọi `plan_blueprint` cho lần lượt bảy
part, mỗi part hai lượt gọi (bối cảnh, và brief hình với part 3/4/7). Lượt gọi
hỏng thì **rơi về bảng cấu hình** `PART*_MIX` chứ không làm chết cả lượt chạy.

**`slotloop`** — vòng per-slot, mô tả ở §2.

**`balance`** và **`spread`** — hai bước của cả đề, mô tả ở §6. Bỏ qua khi không
ô nào được viết, và `spread` còn bỏ qua khi đề chưa đủ ô.

---

## 2. Đồ thị trong — một ô

```
START → write → check ─┬─ sạch ────────────→ accept → END
                       │
                       └─ hỏng → critic ─┬─ còn vòng → write
                                         └─ hết vòng → escalate → END
```

`MAX_REVISIONS = 3`. Ba vòng hỏng cùng một kiểu nghĩa là lỗi nằm ở prompt hoặc ở
brief chứ không ở lượt viết, nên quay tiếp chỉ đốt quota.

**Hàng đợi là một truy vấn trên thư mục, không phải bảng job.** `pending()` hỏi
"ô nào chưa có tệp dán". Chạy lại là tìm thấy ít việc hơn, và đó là toàn bộ cơ
chế phục hồi — không có trạng thái retry, không có bảng, không có gì để dọn.

**Ghi xuống đĩa ngay sau mỗi ô**, không gom cuối lượt: 103 ô là hàng giờ, và một
lần Ctrl-C không được phép vứt sạch.

### Các node

**`write`** — một lượt gọi. Nhận system prompt theo part và user prompt dựng từ
ô. `fix_hint` của vòng trước đi kèm; đó là toàn bộ điểm của đồ thị so với vòng
`write → check → prune` thủ công — sửa theo lý do, không sinh lại mù. Đầu ra bị
cắt giữa chừng thành `MissingBlock`, và nó được ghi vào `log` như một trạng thái
chứ không ném ra ngoài.

**`check`** — **nguồn duy nhất được điền `blocked`**. Chạy `check_blueprint` trên
cả part của ô rồi lấy report của đúng ô đó; dùng chung hàm với lệnh `check`, vì
một bản kiểm riêng sẽ trôi khỏi parser thật. Ghi **một dòng mỗi vòng** vào `log`
— thứ trả lời câu hỏi đáng hỏi khi một ô bị giao người: ba vòng hỏng cùng kiểu
hay ba kiểu khác nhau? Nhìn riêng vòng cuối thì hai ca đó giống hệt nhau.

**`critic`** — một lượt gọi, model **chấm chứ không viết lại**, trả một đoạn tối
đa 40 từ nói phải sửa gì. `CRITIC_MAX_TOKENS = 4000`, rộng hơn nhiều so với 40 từ
nó xin: model bắt buộc suy luận tiêu trần vào phần nghĩ trước khi trả lời, và
trần bằng cỡ câu trả lời làm nó chết đói — sau khi `write` đã tốn một lượt gọi.

**`accept` / `escalate`** — chỉ đặt `outcome`. Ô bị giao người **vẫn còn tệp dán
trên đĩa**; nó không được viết lại, nên `pending()` sẽ không nhặt lại nó ở lượt
sau. Muốn viết lại thì xoá tệp, hoặc chạy `prune`.

---

## 3. Khác nhau theo part

Đây là bảng nói vì sao "chạy graph" không phải một việc đồng nhất.

| part | ô | câu/ô | câu | dải số | hình | câu hỏi hình | chữ cái |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 1 | 6 | 1–6 | 0 | — | ABCD |
| 2 | 25 | 1 | 25 | 7–31 | 0 | — | **ABC** |
| 3 | 13 | 3 | 39 | 32–70 | 3 | câu thứ **3** | ABCD |
| 4 | 10 | 3 | 30 | 71–100 | 2 | câu thứ **2** | ABCD |
| 5 | 30 | 1 | 30 | 101–130 | 0 | — | ABCD |
| 6 | 4 | 4 | 16 | 131–146 | 0 | — | ABCD |
| 7 | 15 | **2–5** | 54 | 147–200 | 5 | — | ABCD |

**103 ô, 200 câu.**

Những chỗ dễ sai:

- **Part 2 chỉ có ba lựa chọn.** `letters_for(2)` trả `ABC`. Mọi thứ đếm bốn chữ
  cái đều sai ở đây, kể cả `balance`.
- **Part 3 hỏi hình ở câu thứ ba, Part 4 ở câu thứ hai.** Lấy cứng `questions[-1]`
  thì Part 4 đang kiểm nhầm câu — và câu bị kiểm nhầm vẫn có bốn lựa chọn hợp lệ,
  nên cổng vẫn ra kết luận, chỉ là về sai câu.
- **Part 7 có số câu khác nhau từng ô** (2, 2, 2, 3, 2, 3, 3, 4, 4, 4, 5, 5, 5,
  5, 5), nên `number` phải cộng dồn theo số câu của ô trước chứ không nhân với
  hằng số.
- **Hình Part 7 nằm trên passage, không phải trên ô**: `p7-11` đoạn 2, `p7-13`
  đoạn 3, `p7-14` đoạn 3, `p7-15` **cả đoạn 2 và 3**. Năm hình rải trong bốn ô.
- **Part 5 không có system prompt riêng** — nó dùng `SYSTEM`. Sáu part còn lại
  mỗi part một bản.

### Trường của ô, theo part

| part | trường mang thông tin |
|---|---|
| 1 | `question_type`, `context`, `voice`, `people` |
| 2 | `question_type`, `context`, `voices` (2 giọng: hỏi và đáp) |
| 3 | `context`, `question_types` (3), `topic`, `voices`, `graphic` |
| 4 | `context`, `question_types` (3), `topic` (kiểu bài nói), `voices` (1), `graphic` |
| 5 | `question_type`, `grammar`, `context` |
| 6 | `context`, `question_types` (4), `grammars` (4), `topic` |
| 7 | `context`, `question_types` (2–5), `topic`, `passages`, `structure` |

`topic` mang nghĩa khác nhau theo part: chủ đề hội thoại (3), kiểu bài nói (4),
dạng văn bản (6, 7). Nó là **nhãn** đi vào `question_set_label`, không phải chú
thích — bối cảnh lệch khỏi nó làm thống kê theo chủ đề đếm sai.

---

## 4. Hiện vật ghi ra đĩa

Sau mỗi lượt viết, khối trả về bị tách ba đường trước khi lưu:

| khối | đi đâu | part |
|---|---|---|
| `[PHOTO]` | `photos/{id}.txt` | 1 |
| `[GRAPHIC]` | `graphics/{id}.txt` | 3, 4, 7 |
| còn lại | `paste/{id}.txt` | tất cả |

Ô có **nhiều hơn một** hình thì tệp được đánh số: `graphics/p7-15-1.txt` và
`-2.txt`. Ô một hình thì không có hậu tố — và `check_graphic` của Part 3/4 đọc
đúng `graphics/{id}.txt`, nên quy ước này là hợp đồng chứ không phải tiện tay.

Tách ra chứ không để trong tệp dán vì hai lý do: parser từ chối dòng lạ sau các
đáp án, và bảng là **dữ liệu để vẽ**, không phải dòng để dán.

---

## 5. Hai tầng kiểm

Node `check` chạy **hai lượt, và thứ tự là chỗ tiết kiệm**.

**Lượt một — miễn phí** (`gateway=None`, luôn chạy): parser thật
(`content_import`), luật hình (`check_graphic`), luật hình dạng theo part
(`check_shape`), trùng lặp trên cả đề, và các luật riêng của Part 6/7.

**Lượt hai — tốn tiền** (`--verify`, mặc định **tắt**): chỉ chạy cho ô đã **sạch**
ở lượt một.

- `verify_answer` — tự làm lại câu rồi đối chiếu với `Answer:` của đề.
- `count_workable_options` — có mấy phương án thật sự dùng được. Đây là phép kiểm
  cho đúng lỗi nội dung trội nhất, và là thứ mọi phép kiểm khác đều mù.

Ô đã hỏng ở lượt một không cần hỏi model "đáp án có đúng không" — nó còn chưa đọc
được. Gộp một lượt thì mỗi ô hỏng vẫn tốn hai lượt gọi, nhân với ba vòng viết
lại.

Findings của lượt hai **chảy vào `fix_hint`** như mọi findings khác, nên một ô bị
phát hiện "hai phương án cùng dùng được" sẽ được viết lại theo đúng lý do đó.

Chi phí: khoảng **+200 lượt gọi** cho một đề đầy đủ, hơn nữa nếu nhiều ô phải
viết lại. Dùng chung gateway với chặng viết, nên `--verify` rút ngắn quãng đường
tới lúc cạn hạn mức ngày khoảng ba lần.

Lời nhắc của hai tầng này viết bằng **tiếng Anh**, khác phần còn lại của
`check.py` — xem §8.

---

## 6. Hai bước của cả đề

Không đặt được trong vòng per-slot, vì chúng là thuộc tính của **cả đề**: ô đang
viết không biết 102 ô kia đã dùng chữ cái nào.

**`balance`** — ghi lại tệp dán sao cho đáp án rải đều. Gán đích **trong từng
part**, không trên danh sách gộp: gán gộp thì thêm một part mới sẽ dịch đích của
mọi part đã cân trước đó, tệp dán bị viết lại và không còn khớp với những gì đã
nằm trong database. Đích tính theo **câu**, không theo ô — đếm theo ô thì ba câu
của một cụm Part 3 cùng đáp án, thứ đọc ra ngay là máy làm.

`balance` **ghi đè tệp dán**, nên phải chạy **trước `load`**.

**`spread`** — `check_answer_spread` trên cả đề. Lý do nó tồn tại, đo trên một
lượt chạy thật: **29 trên 30 câu có đáp án là (A)** — người chọn bừa A được 97%.
Mọi câu riêng lẻ đều hợp lệ, nên không phép kiểm từng câu nào thấy được.

Node này **bỏ qua khi đề còn thiếu ô** và nói ra điều đó. Trên đề mới viết 3/103
ô nó sẽ báo lệch, nhưng cái nó báo là *chỗ thiếu* chứ không phải nội dung sai —
và một cảnh báo luôn kêu là một cảnh báo người ta học cách bỏ qua.

---

## 7. Các hằng số và vì sao chúng có giá trị đó

| hằng | giá trị | lý do |
|---|---|---|
| `MAX_REVISIONS` | 3 | ba vòng hỏng cùng kiểu là lỗi ở prompt, không ở lượt viết |
| `RETRY_TRIES` / `RETRY_DELAY` | 7 / 6.0s | đo được ba lượt 503 liên tiếp rồi lượt thứ tư trả 200 |
| `DEFAULT_MAX_TOKENS` | 6000 | kéo hai hướng: model suy luận cần rộng, TPM của nhà cung cấp tính `max_tokens` vào ngân sách phút |
| `CRITIC_MAX_TOKENS` | 4000 | rộng hơn nhiều so với 40 từ nó xin — model buộc suy luận tiêu trần vào phần nghĩ |
| `CHECK_MAX_TOKENS` | 4000 | câu trả lời là một chữ cái, phần nghĩ mới là thứ tốn |
| `PLAN_MAX_TOKENS` | 16000 | đo thật: Part 5 nghĩ 14 912 ký tự, Part 7 nghĩ 15 572 — ở 4 000 cả hai không kịp in dòng nào |

**Không truyền `--max-tokens` nữa** — trần mặc định đi theo hình dạng từng ô
(§12). Truyền tay thì con số truyền tay thắng cho MỌI ô, kể cả ô không cần.

---

## 8. Ngôn ngữ của lời nhắc

Luật rút từ ba lần rò đo được: **ngôn ngữ lời nhắc an toàn khi nó *mô tả*, rò khi
nó *đọc chính tả***. Model phân biệt được "viết về chủ đề nhà ở" với "bốn nhãn là
X, Y, Z, T"; cái sau nó coi là chuỗi phải xuất ra.

| bề mặt | ngôn ngữ | model xuất ra |
|---|---|---|
| `SYSTEM_PART*`, `GRAPHIC_*` (`prompts.py`) | Anh | nội dung đề |
| `prompt_for_part*` (user prompt) | Việt | nội dung đề |
| prompt sinh bối cảnh / brief (`plan.py`) | Việt | context, brief |
| `AXIS_BRIEF` (`graphics.py`) | Việt, nhãn ví dụ tiếng Anh | brief |
| `VERIFY_SYSTEM_*`, `AMBIGUITY_SYSTEM_*` (`check.py`) | **Anh** | một chữ cái |

Nhóm cuối là nhóm duy nhất mà ngôn ngữ lời nhắc **không khớp** ngôn ngữ đầu ra,
và nó được đổi sang tiếng Anh vì đó là bề mặt duy nhất bắt model phán đoán tiếng
Anh mà không có mỏ neo tiếng Anh nào. **Chưa đo** — phép đo là chạy
`check --model` trên cùng một tập ô của `tp-form-06` bằng cả hai bản rồi so số
lỗi bắt được.

Mọi thứ **in lên hình** đều là tiếng Anh, dù brief viết bằng tiếng gì. Luật này
nằm ở `GRAPHIC_RULES_TEMPLATE` và là lớp chắn cuối; lớp đầu là các brief đã tự
viết nhãn bằng tiếng Anh.

---

## 9. Những gì luồng này KHÔNG làm

- **Không sinh audio, không vẽ hình, không vẽ ảnh.** `photo`, `graphic`, `media`
  là các lệnh riêng của `generate_exam`.
- **Không nạp vào database.** `load` là lệnh riêng, và phải chạy **sau**
  `balance`.
- **Không kiểm phân bố khi đề chưa đủ ô** (§6).
- **Không viết lại ô đã bị giao người.** Tệp dán của nó vẫn nằm đó và `pending()`
  coi như đã xong. Xoá tệp hoặc chạy `prune` nếu muốn viết lại.
- **Không dùng model ở tầng kiểm trừ khi bật `--verify`** (§5).

Trình tự đầy đủ tới lúc nạp được:

```
full (plan → write → balance → spread)  →  photo / graphic  →  media  →  load
```

---

## 10. Runbook: chạy trọn đề từ Part 1 tới Part 7

Đây là các bước đầy đủ, theo thứ tự, từ một `--slug` tới một đề nạp được. Mọi
lệnh chạy từ `apps/api`.

```bash
cd apps/api
SLUG=tp-form-08
MODEL=bai/glm-5.3-flash
```

**Không truyền `--max-tokens`.** Trần được chọn theo hình dạng từng ô (§12), và
một con số cho cả trăm ô là cách vừa cắt cụt ô khó vừa làm chậm ô dễ.

---

### Bước 0 — Blueprint

Một lần cho cả đề, bảy part:

```bash
for p in 1 2 3 4 5 6 7; do
  uv run python -m app.content.generate_exam plan \
    --slug "$SLUG" --part $p --model "$MODEL" --seed 20260822
done
```

Giữ nguyên một `--seed` cho cả bảy lượt: seed quyết định dàn chủ đề, dàn giọng
và bộ hình lấy từ pool.

**Kiểm ngay, trước khi trả tiền cho 103 ô.** Ba lượt hỏng đầu tiên của đề này
đều vì *đầu vào* sai, không vì chặng viết:

```bash
# nhãn có khớp bối cảnh không, và bối cảnh có lẫn mã nhãn không
python3 -c "
import json
d = json.load(open('content/generated/$SLUG/blueprint.json'))
for part in d['parts']:
    bad = sum(1 for s in part['slots'] if s.get('context','').startswith('PART_'))
    print(f\"part {part['part']}: {len(part['slots'])} ô\" + (f'  ← {bad} ô lẫn mã nhãn' if bad else ''))
    for s in part['slots'][:3]:
        print('   ', s['id'], (s.get('topic') or s.get('question_type') or '')[:34], '|', s.get('context','')[:52])
"

# brief hình: nhãn phải là TIẾNG ANH và đúng chủ đề của ô
python3 -c "
import json
d = json.load(open('content/generated/$SLUG/blueprint.json'))
for part in d['parts']:
    for s in part['slots']:
        if s.get('graphic'): print(f\"[{s['id']}] {s.get('topic','')}\n    {s['graphic']}\n\")
"
```

Lượt `plan` hỏng thì nó **rơi về bảng cấu hình** và nói ra — bối cảnh khi đó
đúng nhưng giống nhau giữa các đề cùng seed. Muốn bối cảnh riêng thì chạy lại
part đó.

---

### Bước 1 tới 7 — Viết từng part

Khác nhau đúng một chỗ: **`--verify` chỉ bật ở Part 3 và 4**, vì đó là hai part
duy nhất có findings *chặn* được và tự khiến ô hỏng được viết lại (§12).

```bash
# Part 1 — 6 ô, sinh kèm mô tả ảnh vào photos/
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 1

# Part 2 — 25 ô, ba lựa chọn chứ không bốn
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 2

# Part 3 — 13 ô; p3-11..13 có hình → BẬT verify
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 3 --verify

# Part 4 — 10 ô; p4-09..10 có hình → BẬT verify
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 4 --verify

# Part 5 — 30 ô, part nhiều ô nhất
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 5

# Part 6 — 4 ô, mỗi ô một văn bản bốn chỗ trống
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 6

# Part 7 — 15 ô, 5 hình nằm trên passage của p7-11, 13, 14, 15
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 7
```

Mỗi lệnh tự chạy `balance` cho part đó khi xong. `plan` bỏ qua từ lượt thứ hai
trở đi vì blueprint đã có.

**Đọc gì trên màn hình:**

```
── part 3 · 3 ô ──
  → [1/3] p3-11 …                       ô bắt đầu
      … p3-11 vẫn đang chạy (60s)        nhịp tim mỗi phút
      ↻ vòng 1: <lý do> …                sắp viết lại
      ⚠ <cờ>                             cần người nhìn, KHÔNG chặn nạp
  ✓ [1/3] p3-11 → accepted (242s)
  part 3: 3 nhận · 0 giao người · 12.1 phút · còn 50 ô, ước 67 phút
```

**Thử vài ô trước khi cam kết cả part** — nên làm với part chưa từng chạy:

```bash
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 5 --limit 3
```

---

### Sau mỗi part — kiểm

Part 3 và 4 đã kiểm trong vòng lặp. **Part 1, 2, 5, 6, 7 kiểm ở đây:**

```bash
uv run python -m app.content.generate_exam check --slug "$SLUG" --part 5 \
  --verify --model "$MODEL"
```

Đọc kết quả: `✗` là **chặn nạp**, `⚠` là cần người nhìn. Riêng dòng
`✗ CẢ ĐỀ: đáp án lệch` chỉ có nghĩa khi đề đã đủ ô.

Ô bị **giao người** (`escalated`) giữ lại tệp dán và `pending()` sẽ KHÔNG nhặt
lại. Muốn viết lại thì xoá tệp:

```bash
rm content/generated/$SLUG/paste/p5-17.txt
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL" --part 5
```

Ngoại lệ: ô hỏng vì **lượt gọi** (mạng, timeout) chưa kịp ghi tệp nào, nên nó
vẫn nằm trong hàng đợi — chạy lại là đủ, không phải xoá gì.

---

### Xem còn thiếu gì, bất cứ lúc nào

```bash
uv run python -c "
from app.content.exam import blueprint as bp
from app.content.exam.writer import pending
from app.content.exam_agents.graph import parts_of
from app.content.exam_cli.paths import blueprint_path, workdir_for
from collections import Counter
b = bp.load(blueprint_path('$SLUG')); w = workdir_for('$SLUG')
left = pending(b, w); c = Counter(parts_of(b, s.id) for s in left)
for p in range(1, 8):
    total = len([s for part in b.parts if part.part == p for s in part.slots])
    print(f'  part {p}: còn {c.get(p, 0)}/{total}')
print(f'  tổng còn {len(left)} ô')
"
```

Chạy lại đúng lệnh cũ là an toàn: hàng đợi là truy vấn trên thư mục, ô đã xong
không bị viết lại.

---

### Sau khi đủ 103 ô

```bash
# 1. cân đáp án trên CẢ đề, và kiểm phân bố (giờ mới có nghĩa)
uv run python -m app.content.exam_agents.full --slug "$SLUG" --model "$MODEL"

# 2. vẽ hình ngữ liệu Part 3/4/7 từ dữ liệu bảng
uv run python -m app.content.generate_exam graphic --slug "$SLUG"

# 3. vẽ ảnh Part 1 từ phần mô tả
uv run python -m app.content.generate_exam photo --slug "$SLUG"

# 4. kiểm đầy đủ cả đề
uv run python -m app.content.generate_exam check --slug "$SLUG" --verify --model "$MODEL"

# 5. media đã lên nhà cung cấp chưa
uv run python -m app.content.generate_exam media --slug "$SLUG" --push

# 6. nạp vào database — SAU `balance`
uv run python -m app.content.generate_exam load --slug "$SLUG" --token <admin-token>
```

Bước 1 không viết ô nào (đã đủ), nó chạy để `balance` cân **cả đề** và `spread`
kiểm phân bố — `spread` bỏ qua chừng nào còn thiếu ô.

**`balance` ghi đè tệp dán, nên phải chạy trước `load`.** Cân lại sau khi đã nạp
làm tệp và database lệch nhau.

---

### Khi có gì đó lạ

```bash
# prompt THẬT sẽ gửi đi cho một ô — không gọi model
uv run python -m app.content.generate_exam prompt --slug "$SLUG" --slot p4-09

# toàn văn mọi lượt gọi của một lượt chạy (§11)
LLM_TRANSCRIPT_LOG=/tmp/llm.jsonl uv run python -m app.content.exam_agents.full \
  --slug "$SLUG" --model "$MODEL" --part 4 --verify
```

---

### Nhịp đo được

| | |
|---|---|
| ô thường | ~52 giây (52 lượt viết) |
| ô có hình | 225–365 giây |
| một part 30 ô, không verify | ~30 phút |
| `--verify` | +2 lượt gọi mỗi câu, nhưng chỉ +13% thời gian |

Dòng `còn N ô, ước N phút` mà graph in ra tính từ nhịp thật của chính lượt đang
chạy, nên nó đúng hơn bảng này.


## 11. Xem model thật sự gửi đi cái gì

Sổ `ai_interaction` trả lời *"tốn bao nhiêu, hỏng bao nhiêu"* — feature, provider,
model, token, chi phí, độ trễ, trạng thái, số lần thử lại. Nó **không** giữ toàn
văn prompt lẫn câu trả lời, và đó là câu hỏi tốn thời gian nhất khi một lượt sinh
ra kết quả lạ: *nó gửi đi đúng cái gì?*

Bật `LLM_TRANSCRIPT_LOG` để ghi toàn văn ra một tệp JSONL, mỗi lượt gọi một dòng:

```bash
cd apps/api

LLM_TRANSCRIPT_LOG=/tmp/llm.jsonl uv run python -m app.content.exam_agents.full \
  --slug "$SLUG" --model "$MODEL" --part 4 --verify
```

Mỗi dòng có `at`, `feature`, `provider`, `model`, `status`, `latency_ms`, token,
`cost_usd`, `error`, `request` (`system`, `user`, `max_tokens`, `temperature`) và
`response`.

Đọc nhanh:

```bash
# một dòng tóm tắt mỗi lượt gọi
python3 -c "
import json,sys
for l in open('/tmp/llm.jsonl'):
    d=json.loads(l)
    print(f\"{d['feature']:16s} {d['status']:6s} {d['latency_ms']:>6}ms \"
          f\"{d['prompt_tokens']:>5}/{d['completion_tokens']:<5} {(d['error'] or '')[:60]}\")
"

# xem nguyên system prompt của lượt gọi thứ N
python3 -c "
import json
print(json.loads(open('/tmp/llm.jsonl').readlines()[0])['request']['system'])
"
```

Ba tính chất cố ý:

- **Ra tệp, không vào bảng.** Toàn văn là dữ liệu người dùng, không thuộc về một
  bảng dùng chung, và lớn gấp hàng trăm lần phần số liệu. Bảng giữ số, tệp giữ chữ.
- **Mặc định TẮT.** Bật cho lượt chạy pipeline, nơi câu hỏi luôn là "nó gửi gì".
- **Ghi hỏng không làm hỏng lượt gọi.** Đầy đĩa hay sai đường dẫn thì mất một dòng
  log, không mất một lượt chạy ba tiếng.

Lượt **hỏng** cũng được ghi kèm prompt — đó chính là lúc cần biết đã gửi gì nhất.
Đo thật: một lượt `429 Too many pending requests` rồi `with_backoff` thử lại và
thành công hiện ra thành hai dòng, cùng một prompt.

---

## 12. Trần đầu ra và cách verify, theo từng part

### Trần đầu ra: mặc định theo HÌNH DẠNG ô

`--max-tokens` là **một** con số cho cả trăm ô có độ khó rất khác nhau. Không
truyền thì `max_tokens_for(part, slot)` chọn theo ô:

| part | ô thường | ô có hình |
|---|---|---|
| 1, 2 | 10 000 | — |
| 3, 4 | 14 000 | **24 000** |
| 5 | 12 000 | — |
| 6 | 16 000 | — |
| 7 | 20 000 | **24 000** |

Cơ sở, đo với `glm-5.3-flash`: nội dung sinh ra chỉ 64–401 token, nên gần như
**toàn bộ** trần là phần suy luận và nó tỉ lệ với ĐỘ KHÓ, không với độ dài đầu
ra. Ô không hình dùng trung bình 2 096 token, nhiều nhất 7 739. Ô có hình dùng
8 506 ở trần 25 000; `p3-11` bị **cắt** ở trần 12 000.

**Trần rộng không miễn phí.** Model nở phần suy luận cho vừa ngân sách: cùng một
ô có hình, trần 40 000 mất 322 giây còn 25 000 chỉ mất 225 — nhanh hơn 30%. Cửa
sổ đọc cũng đi theo trần (§7), nên trần rộng làm một ô HỎNG hỏng chậm hơn.

Truyền `--max-tokens` thì con số truyền tay thắng, cho mọi ô.

### Verify: chỉ đáng bật trong vòng lặp ở Part 3 và 4

Trong đồ thị, chỉ findings trở thành **`problem`** mới đổi được kết cục — chúng
bật `blocked`, đẩy ô sang critic và khiến nó được viết lại. Findings thành **cờ**
thì không.

| findings | thành | đồ thị phản ứng |
|---|---|---|
| `graphic_rule_verdict` | problem | **có** — viết lại |
| `verify_answer` | cờ | không |
| `count_workable_options` | cờ | không |

Nên:

- **Part 3, 4 — bật `--verify`.** Ô có hình được phán quyết luật giao điểm, và ô
  hỏng được viết lại ngay trong vòng. Đây là part duy nhất `--verify` tự sửa được.
- **Part 1, 2, 5, 6 — KHÔNG bật trong vòng lặp.** Không ô nào có hình, nên không
  findings nào chặn được; `--verify` chỉ thêm 2 lượt gọi mỗi câu để lấy cờ.
- **Part 7 — tuỳ.** Có ô mang hình nhưng hình Part 7 là *ngữ liệu*, không có luật
  trục đáp án, nên cũng không có findings nào chặn.

Với các part đó, kiểm SAU khi viết:

```bash
uv run python -m app.content.generate_exam check --slug tp-form-08 --part 5 \
  --verify --model bai/glm-5.3-flash
```

Cùng số lượt gọi, nhưng tách rời thì kiểm lại được mà không phải viết lại, và
`cmd_check` in cờ ra kèm số câu.

Cờ trong vòng lặp giờ **cũng được in** (`⚠ …` dưới dòng ô). Trước đó chúng được
tính rồi vứt — `_check_node` ghi vào state và không nơi nào đọc, tức là trả tiền
cho một kết quả không ai thấy.
