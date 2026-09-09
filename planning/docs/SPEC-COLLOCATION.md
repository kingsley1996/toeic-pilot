# SPEC — TOEIC Collocation

**Status:** PROPOSED
**Scope:** Vocabulary / Collocation
**Priority:** Medium

---

# 1. Decision

**Không tạo module learning riêng cho Collocation.**

Collocation là một `vocabulary_entry` có:

```text
part_of_speech = phrase
```

và có thêm:

```text
collocation_detail
```

Quan hệ:

```text
vocabulary_entry 1 ─── 1 collocation_detail
```

`vocabulary_entry` tiếp tục là identity của learning item.

Không tạo:

```text
collocation_review_state
collocation_review_log
collocation_audio
collocation_xp
collocation_streak
```

Collocation phải reuse toàn bộ vocabulary infrastructure hiện tại:

* Review / SM-2
* Flashcard
* Recall
* Audio
* XP
* Ruby
* Daily Goal
* Streak
* Publish Gate

Mục tiêu là Collocation và Vocabulary dùng chung một review queue. Hình dung:

```text
Today's Review

invoice
submit a report
deadline
interested in
contract
meet a deadline
```

> **Core Rule — Collocation = Vocabulary Entry + Collocation Metadata + Optional Slot-Fill Quiz.**
> Không tạo learning system thứ hai cho Collocation.

---

# 2. Data Model

## 2.1. `collocation_detail`

```sql
collocation_detail (
    entry_id       UUID PRIMARY KEY
                   REFERENCES vocabulary_entry(id)
                   ON DELETE CASCADE,

    base_word      TEXT NOT NULL,

    gap_word       TEXT NULL,

    pattern        TEXT NOT NULL,

    distractors    JSONB NULL,

    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL
)
```

Không thêm `is_collocation` vào `vocabulary_entry`.

**Sự tồn tại của `collocation_detail` là source of truth để xác định một entry là Collocation.**

---

# 3. Vocabulary Entry Rules

Collocation phải là:

```text
vocabulary_entry.part_of_speech = phrase
```

Ví dụ:

```text
headword = "submit a report"
part_of_speech = "phrase"
```

`headword` luôn chứa **toàn bộ Collocation**:

```text
submit a report
interested in
meet a deadline
take responsibility
```

Không tạo một `collocation` entity riêng.

---

# 4. `base_word`

`base_word` là **lexical anchor dùng để nhóm các Collocation liên quan**.

```text
submit a report       → submit
submit a claim        → submit
submit an application → submit
submit a request      → submit
```

`base_word` không nhất thiết là từ đầu tiên trong `headword`:

```text
interested in  →  base_word = interest
```

### Rules

* Required
* `trim`
* lowercase khi lưu
* không được empty
* MVP lưu dưới dạng `TEXT`
* chưa cần FK tới vocabulary entry khác

---

# 5. `gap_word`

`gap_word` là **exact surface token trong `headword` sẽ bị ẩn khi tạo Slot-Fill Quiz**.

```text
headword: submit a report
gap_word: submit

quiz: _____ a report
```

```text
headword: interested in
gap_word: in

quiz: interested _____
```

### Rules

`gap_word`:

* có thể `NULL`
* nếu có giá trị thì phải là đúng một token
* không chứa whitespace
* phải xuất hiện trong `headword`
* không được bằng toàn bộ `headword`
* lưu lowercase; so khớp với `headword` **không phân biệt hoa/thường** (`headword` giữ nguyên văn)

---

# 6. `gap_word = NULL`

`NULL` nghĩa là:

> Entry vẫn là Collocation nhưng không tham gia Slot-Fill Quiz.

```text
in accordance with
gap_word = NULL
```

Entry vẫn được dùng cho Flashcard / SM-2 / Recall / Audio / XP / Streak —
nhưng không được đưa vào `COLLOCATION_SLOT_FILL`.

Đây là **quiz eligibility**, không phải invalid content.

---

# 7. `pattern`

MVP hỗ trợ:

```text
VERB_NOUN
ADJ_PREP
NOUN_NOUN
VERB_PREP
PREP_PHRASE
ADJ_NOUN
VERB_ADJ
```

| Pattern       | Example            |
| ------------- | ------------------ |
| `VERB_NOUN`   | submit a report    |
| `ADJ_PREP`    | interested in      |
| `NOUN_NOUN`   | customer service   |
| `VERB_PREP`   | depend on          |
| `PREP_PHRASE` | in accordance with |
| `ADJ_NOUN`    | a big mistake      |
| `VERB_ADJ`    | get married        |

`ADJ_NOUN` và `VERB_ADJ` thêm sau đợt nội dung đầu (2026-09-09): 53/182 cụm
của kho nhập nằm ở hai dạng này — bỏ là mất gần nửa kho. CHECK constraint
nhận 7 giá trị; migration 079 sửa trực tiếp vì chưa ship.

API/database sử dụng canonical value. Không dùng biến thể
`verb+noun`, `Verb+Noun`, …

---

# 8. `distractors`

Distractors được lưu sẵn khi import content.

```json
["make", "do", "take"]
```

Rules:

* tối đa 3
* không empty
* không duplicate
* không được bằng `gap_word`
* không generate runtime

Runtime quiz chỉ sử dụng distractors đã lưu.

---

# 9. Distractor Validation

## Machine validation — `ERROR`

```text
distractor == gap_word
duplicate distractor
empty distractor
> 3 distractors
```

## Semantic validation — `WARNING`

Không thể đảm bảo bằng DB/code rằng distractor thực sự sai:

```text
submit a report · gap: submit · distractors: make, do, write
```

`write a report` cũng đúng.

### Heuristic WARNING

Máy kiểm được một xấp xỉ rẻ: **điền thử distractor vào gap** — nếu cụm kết quả
(`headword` với gap thay bằng distractor) trùng `headword` của một collocation
khác trong DB hoặc trong lô đang nhập, sinh WARNING
"distractor có thể tạo thành một Collocation hợp lệ khác".

Heuristic chỉ thấy những cụm đã có trong kho — **không WARNING ≠ đúng**.
Cổng cuối là human review, không phải runtime LLM.

---

# 10. Content Import

Sử dụng pipeline Vocabulary hiện tại:

```text
Parse → Validate → Review → Commit
```

**Parse không được ghi DB.**

Format:

```text
headword | base_word | gap_word | pattern | meaning_VN | example_EN | example_VN | distractors
```

```text
submit a report | submit | submit | VERB_NOUN | nộp báo cáo | Please submit the report by Friday. | Vui lòng nộp báo cáo trước thứ Sáu. | make,do,take

interested in | interest | in | ADJ_PREP | quan tâm đến | She is interested in the position. | Cô ấy quan tâm đến vị trí này. | to,on,about
```

Không có gap (cột `gap_word` và `distractors` để trống):

```text
in accordance with | accordance | | PREP_PHRASE | theo đúng | The work was completed in accordance with the agreement. | Công việc được hoàn thành theo đúng thỏa thuận. |
```

---

# 11. Import Validation

`ERROR` nếu:

* `headword` empty
* `base_word` empty
* `part_of_speech != phrase`
* pattern không hợp lệ
* `gap_word` chứa whitespace
* `gap_word` không tồn tại trong `headword` (so khớp không phân biệt hoa/thường — §5)
* `gap_word` bằng toàn bộ `headword`
* distractor empty
* distractor duplicate
* distractor == `gap_word`
* quá 3 distractors

`WARNING` nếu:

* heuristic §9 bắt được distractor tạo thành cụm có thể hợp lệ
* content cần human review

Chỉ commit khi không còn `ERROR`.

---

# 12. Edit After Commit

Import không phải điểm cuối. `collocation_detail` phải sửa được sau commit qua
admin — tối thiểu một endpoint PATCH trên admin vocabulary:

```http
PATCH /admin/vocabulary/entries/{entry_id}/collocation
```

Nhận `base_word`, `gap_word`, `pattern`, `distractors` — validate đúng bộ luật
§11, field nào không gửi thì giữ nguyên. Form nằm trong màn edit entry có sẵn
của admin, không làm trang riêng.

Không có chỗ sửa này thì một distractor sai chỉ khắc phục được bằng SQL.

Audio không liên quan: sửa detail không đụng `headword`, content hash không đổi.

---

# 13. Learning Integration

Collocation phải reuse hệ thống hiện tại — đây là mục duy nhất nói về integration.

### Review

Dùng chung review state và SM-2. Không tạo review state riêng.

### Flashcard

Collocation xuất hiện trong vocabulary review queue — chung hàng đợi với từ
(§1). Learning engine không cần biết Collocation tồn tại.

### Recall

Recall toàn bộ `headword`:

```text
nộp báo cáo → submit a report
```

`gap_word` không được dùng làm expected answer của Recall.

### Audio

Audio đọc toàn bộ `headword`: `submit a report → "submit a report"`.

### Reward

Reuse `vocabulary_review` XP / ruby / daily goal / streak.
Không có reward logic riêng cho Collocation.

### Metadata cho UI

Nếu UI cần phân loại, dùng metadata:

```text
WORD | PHRASE | COLLOCATION
```

suy từ `part_of_speech` + sự tồn tại của `collocation_detail` — không thêm cột.

---

# 14. Audio / Publish Gate

Collocation sử dụng audio pipeline hiện tại.

Nếu `headword` thay đổi:

```text
submit a report → submit the report
```

content hash thay đổi, audio cũ là stale, publish gate hiện tại chặn publish
cho tới khi audio được regenerate. Không tạo audio gate riêng.

---

# 15. Collocation Detail UI

Trang detail hiển thị:

```text
submit a report

[Verb + Noun]

Base word: submit

Meaning: nộp báo cáo

Example: Please submit the report by Friday.
```

Nếu có `base_word`, hiển thị **Other collocations with "submit"**, link tới
`GET /vocabulary/collocations?base_word=submit` (§16).

---

# 16. Related Collocations API

```http
GET /vocabulary/collocations?base_word=submit&pattern=VERB_NOUN
```

Cả hai query param đều optional. Chỉ trả entry `published` join được detail.

```json
{
  "items": [
    {
      "id": "0b9f6a1e-…",
      "headword": "submit a report",
      "baseWord": "submit",
      "pattern": "VERB_NOUN"
    },
    {
      "id": "c4d2e8b7-…",
      "headword": "submit a claim",
      "baseWord": "submit",
      "pattern": "VERB_NOUN"
    }
  ]
}
```

Endpoint chỉ phục vụ discovery/navigation.

---

# 17. Slot-Fill Quiz

Collocation có question type:

```text
COLLOCATION_SLOT_FILL
```

```text
_____ a report

A. submit   B. make   C. do   D. take

correct: submit
```

---

# 18. Quiz Eligibility

Một Collocation chỉ được đưa vào Slot-Fill Quiz khi:

```text
collocation_detail exists
AND gap_word IS NOT NULL
AND vocabulary_entry is published
```

Query bắt buộc filter `gap_word IS NOT NULL`. Entry có `gap_word = NULL`
không được xuất hiện trong Slot-Fill Quiz (§6).

---

# 19. Quiz Payload

Backend trả:

```json
{
  "type": "COLLOCATION_SLOT_FILL",
  "entryId": "0b9f6a1e-…",
  "headword": "submit a report",
  "gapWord": "submit",
  "choices": ["submit", "make", "do", "take"]
}
```

Client chịu trách nhiệm render `_____ a report`, qua **một** utility dùng chung:

```text
renderGap(headword, gapWord)
```

Không để nhiều component tự implement logic `replace()`.

---

# 20. Quiz Answer

**`questionId` là stateless — chính là `entryId`.** Không tạo bảng question
instance: gap_word và distractors là bất biến của entry (không có gì cần chốt
snapshot), và quiz này không cho XP. Nếu sau này quiz cho XP hoặc cần ghi
attempt, đó là lúc dựng bảng instance — không phải bây giờ.

Client submit:

```json
{
  "questionId": "0b9f6a1e-…",
  "answer": "submit"
}
```

Backend resolve:

```text
questionId (= entry_id, phải published)
    → collocation_detail
    → gap_word
```

Correct khi:

```text
answer.trim().toLowerCase() === gap_word
```

Không validate answer bằng toàn bộ `headword`. `questionId` không khớp entry
published nào → 404, không đoán.

---

# 21. Board Quiz Integration

Board Quiz hiện tại được mở rộng để hỗ trợ:

```text
VOCABULARY
COLLOCATION_SLOT_FILL
```

Không tạo Board Quiz riêng cho Collocation. Collocation questions lấy cùng
payload với các question type khác. Không query distractors riêng khi client
render question.

---

# 22. Database

Migration chỉ tạo `collocation_detail`. Không migration bảng review/audio/XP/streak.

### Required constraints

```sql
PRIMARY KEY (entry_id)

FOREIGN KEY (entry_id)
REFERENCES vocabulary_entry(id)
ON DELETE CASCADE

CHECK (trim(base_word) <> '')

CHECK (
    gap_word IS NULL
    OR (
        trim(gap_word) <> ''
        AND gap_word !~ '\s'
    )
)

CHECK (
    pattern IN (
        'VERB_NOUN',
        'ADJ_PREP',
        'NOUN_NOUN',
        'VERB_PREP',
        'PREP_PHRASE'
    )
)
```

Các domain invariant còn lại (gap nằm trong headword, distractor ≠ gap, …) là
luật của tầng import/validate (§11) và PATCH (§12) — không cố ép bằng CHECK.

---

# 23. Indexes

Một index composite duy nhất:

```sql
CREATE INDEX ix_collocation_detail_base_word_pattern
    ON collocation_detail (base_word, pattern);
```

Prefix `base_word` phục vụ query chỉ theo `base_word`. Query chỉ theo `pattern`
hiếm — không tạo index riêng.

---

# 24. Implementation Slices

## C1 — Content Foundation

Implement:

* migration
* ORM model
* relation
* import parser
* validation
* admin review
* commit
* PATCH endpoint + fields trong màn admin edit entry (§12)

Acceptance:

```text
Valid Collocation → vocabulary_entry + collocation_detail
Import sai rule   → ERROR, không commit
gap trống         → commit OK, không eligible cho quiz
Sửa sau commit    → PATCH đổi pattern/distractors thành công
```

---

## C2 — Discovery

Implement:

* Collocation detail UI
* pattern chip
* base word
* related Collocations
* `/vocabulary/collocations`

Acceptance:

```text
submit a report → related → submit a claim → submit a request
```

---

## C3 — Slot-Fill Quiz

Implement:

* question type
* eligibility query (`gap_word IS NOT NULL` + published)
* board integration
* choices
* answer validation (§20, stateless `questionId`)
* `renderGap` utility

Acceptance:

```text
gap_word != NULL → eligible
gap_word = NULL  → not eligible
answer đúng/sai  → chấm bằng gap_word, không bằng headword
```

---

# 25. Out of Scope

Không làm trong MVP:

* Collocation review engine riêng
* Collocation SM-2 riêng
* AI generate runtime
* Runtime distractor generation
* Automatic semantic distractor validation (chỉ heuristic §9)
* Morphology engine
* Separate Collocation XP
* Separate Collocation streak
* Advanced Collocation analytics
* `base_entry_id` FK
* Question instance table cho quiz (§20)

Nếu cần AI generate content trong tương lai:

```text
LLM → offline generation → human review → import → validation → commit → publish
```

LLM không ghi production DB trực tiếp.
