# Kiểm kê prompt

Mọi lời nhắc gửi cho mô hình trong dự án này, phân theo **mục đích sử dụng**. Số
đo lấy ngày **2026-09-01** và sẽ mục đi; `rg 'LLMRequest\('` là cách đếm lại.

## 0. Hai họ prompt, và ranh giới giữa chúng là ranh giới kiến trúc

Đây là điều phải đọc trước, vì nó giải thích vì sao cùng là "prompt" mà hai nơi
lại được đối xử khác hẳn nhau.

**Hai sổ đăng ký, cùng một lớp `Prompt`, hai thư mục.**

|  | Sổ **runtime** | Sổ **sinh đề** |
|---|---|---|
| Ở đâu | `app/services/llm/prompts/` (4 tệp) | `app/content/exam/prompts/` (11 tệp) |
| Chạy lúc nào | trong một **request** của người học | trên máy soạn nội dung |
| Định dạng | `.md` | `.md` |
| Có phiên bản | ✅ `tên@hash12` | ✅ `tên@hash12` |
| Ghi vào `ai_interaction` | ✅ cột `prompt_version` | ❌ |

Hai sổ tách nhau **cố ý**. Gộp một chỗ thì ranh giới quyết định prompt nào đi
thẳng ra màn hình người học — và do đó cái nào cần `prompt_version` — trở thành
vô hình. `load(name, directory)` nhận thư mục chính vì thế; `_registry.py` bên
`exam/prompts/` là cửa vào của sổ thứ hai.

Họ runtime là **tệp có phiên bản** chứ không phải chuỗi trong mã, và
`app/services/llm/prompts/__init__.py` nói rõ ba thứ đến từ đó: đổi prompt thành
một diff riêng, `ai_interaction.prompt_version` truy được **bản nào tạo ra câu
trả lời nào**, và cổng hồi quy của bộ eval có mốc để so.

Phiên bản là **hash của chính nội dung**, không phải số người tự tăng — số tự
tăng thì có ngày ai đó sửa prompt mà quên tăng, và từ đó hai nội dung khác nhau
mang cùng một nhãn, hỏng đúng thứ cột này sinh ra để làm.

Sổ sinh đề không ghi `prompt_version` vào đâu cả, và điều đó **chấp nhận được vì
đầu ra của nó được người duyệt trước khi vào database**. Một prompt sinh đề tệ
tạo ra một tệp dán tệ, và tệ đó bị chặn ở cổng `check` hoặc ở mắt người soạn.
Một prompt runtime tệ đi thẳng ra màn hình người học.

`app/content/exam/prompts/graphic.py` **ở lại dạng Python**, một mình. Nó là
template **hai tầng** — f-string dựng ra một template mà `graphic_rules()` mới
`.format(ordinal=…)` lần thứ hai — nên nó là mã có hình dạng mã, không phải văn
bản có hình dạng dữ liệu. `check_prompts.py` cũng ở lại: prompt ngắn, và nó đã
là mô-đun riêng.

## 1. Runtime — trả lời người học trong request

Bốn tệp, `app/services/llm/prompts/`. Mỗi tệp gắn với một `FEATURE`, và feature
là khoá tra bảng giá và bảng cấu hình model (`ai_feature_config`).

| Prompt | Dòng | `FEATURE` | Gọi từ | Việc |
|---|---|---|---|---|
| `coach_explain.md` | 27 | `coach_explain` | `services/coach.py` | Giải thích một câu người học làm sai |
| `coach_chat.md` | 17 | `coach_chat` | `services/chat.py` | Hỏi tiếp về câu vừa được giải thích |
| `assistant_chat.md` | 25 | `assistant_chat` | `services/assistant.py` | Trợ lý toàn trang, có gọi công cụ |
| `label_facet.md` | 14 | `enrich_label` | `content/enrich_skills.py` | Gán một facet nhãn cho một câu |

`label_facet.md` là ngoại lệ đáng chú ý: nó **nằm trong họ runtime nhưng chỉ chạy
offline**. Nó ở đây vì nó cần đúng thứ họ runtime có — truy được bản nào gán
nhãn nào — chứ không vì nó chạy trong request.

`assistant.py` còn ghép thêm hai khối vào prompt lúc chạy: `SITE_GUIDE` (bản đồ
tĩnh các khu của trang, ~512 ký tự) và một đoạn tài liệu lấy từ `knowledge_chunk`
theo câu hỏi. Nó cũng khai `TOOL_SCHEMAS` — bốn công cụ đọc dữ liệu của chính
người học — nên "prompt" ở đây là prompt cộng bộ công cụ, không chỉ là chữ.

## 2. Sinh đề — viết nội dung mới

`app/content/exam/prompts/`, một tệp `.md` mỗi part; `partN.py` chỉ còn một dòng
`exam_prompt("partN_system").render(...)` và hàm dựng phần *user*.

| Tệp | ~ký tự | Chỗ trống | Việc |
|---|---|---|---|
| `part1_system.md` | 2 072 | `{PHOTO_MARKER}` | Sáu câu tả tranh |
| `part2_system.md` | 1 674 | — | Hỏi–đáp, **ba** lựa chọn |
| `part3_system.md` | 1 939 | — | Hội thoại 2–3 người |
| `part4_system.md` | 2 074 | — | Bài nói một người |
| `part5_system.md` | 1 988 | `{EXAMPLE_EXPLANATION}` | Câu đơn điền chỗ trống |
| `part6_system.md` | 2 901 | `{BLANK}` | Văn bản bốn chỗ trống |
| `part7_system.md` | 5 153 | — | Đọc hiểu, 1–3 ngữ liệu |

**Chỗ trống là mốc hợp đồng, không phải chữ chép cứng**, và đó là điều dễ làm
hỏng nhất khi chuyển sang `.md`. Nếu `{BLANK}` thành `-------` viết thẳng trong
tệp thì đổi `contract.BLANK` sẽ làm prompt lệch khỏi trình phân tích **im lặng**.
`Prompt.render` dùng `str.format` và **nổ khi thiếu khoá**, nên liên kết ấy còn
nguyên và hỏng thì hỏng to.

Dùng chung cho Part 3/4/7, **ở lại dạng Python** (§0 nói vì sao):

| Prompt | ~ký tự | Việc |
|---|---|---|
| `GRAPHIC_FORMAT` | 1 300 | Định dạng khối hình |
| `GRAPHIC_RULES_TEMPLATE` | 3 400 | Luật **giao điểm**: hình phải trả lời được câu hỏi |

Xem prompt thật của một ô: `generate_exam prompt --slug <slug> --slot <id>`.

## 3. Dựng blueprint — quyết định đề sẽ là gì

| Tệp | Chỗ trống | Gọi từ |
|---|---|---|
| `plan_part1_scenes.md` | — | `generate_part1_scenes()` |
| `plan_scenes.md` | `{count}` `{part}` `{part_hint}` `{hosts}` | `generate_part_scenes()` |
| `plan_graphics.md` | `{count}` `{part}` `{kinds}` `{axis_brief}` `{hosts}` | `generate_part_graphics()` |

Chúng chạy **trước** chặng viết, và đầu ra là *dữ liệu blueprint* chứ không phải
câu hỏi.

`{hosts}` đã tự kết thúc bằng xuống dòng (`_numbered`), nên trong
`plan_graphics.md` nó **dính liền** với đoạn sau chứ không xuống dòng thêm —
để thừa một dòng trống là prompt khác đi, dù mắt gần như không thấy.

## 4. Kiểm đề — chấm nội dung vừa sinh

`app/content/exam/check_prompts.py`, mười một prompt chia hai họ và một cái lẻ:

| Nhóm | Prompt | Việc |
|---|---|---|
| Đối chiếu đáp án | `VERIFY_SYSTEM` + bản riêng cho Part 1, 2, 3, 6 | Đáp án đã đánh có đúng không |
| Nhập nhằng | `AMBIGUITY_SYSTEM` + bản riêng cho Part 1, 2, 3, 6 | Có lựa chọn thứ hai cũng đúng không |
| Hình | `GRAPHIC_VERDICT_SYSTEM` (~2 400) | Hình có thật sự trả lời được câu hỏi không |

Có bản riêng cho bốn part vì cùng một câu hỏi đặt cho Part 2 (ba lựa chọn, không
in gì) và cho Part 6 (điền vào văn bản) là hai việc khác nhau; part nào không có
bản riêng thì rơi về bản chung.

Thêm một prompt nữa: `critic.md`, dùng ở `exam_agents/graph.py::_critic_node` —
tối đa 40 từ, **chấm chứ không viết lại**. Nó dùng `feature="exam_verify"` vì
cùng loại việc với đối chiếu đáp án.

## 5. Sinh ảnh — không gửi cho LLM

`app/content/exam/photos.py` dựng prompt cho **bộ vẽ ảnh**, không cho mô hình
ngôn ngữ, nên nó không đi qua `Gateway` và không có hàng `ai_interaction` nào.

| Thành phần | ~ký tự | Việc |
|---|---|---|
| `STYLE` | 230 | Phong cách ảnh Part 1 |
| `ALWAYS_AVOID` | 210 | Thứ không bao giờ được xuất hiện |
| `photo_prompt()` | — | Tách mô tả thành (vẽ gì, `Avoid` gì) |

`photo_prompt` làm một việc dễ bị "gọn lại" sai: câu phủ định trong mô tả được
chuyển sang vế `Avoid` **và bỏ chữ phủ định đi**, vì để nguyên "No telephone is
visible" ở mục liệt kê thứ-không-được-có là phủ định hai lần.

`app/content/exam/graphics.py::AXIS_BRIEF` (~1 200 ký tự) không phải prompt gửi
đi mà là **văn bản in cho người soạn** khi một hình bị chặn.

## 6. Tổng

| Mục đích | Số prompt | Dạng | Có phiên bản |
|---|---|---|---|
| Runtime, trả lời người học | 4 | `.md` | ✅ |
| Sinh đề | 7 | `.md` | ✅ |
| Dựng blueprint | 3 | `.md` | ✅ |
| Kiểm đề, phần critic | 1 | `.md` | ✅ |
| Sinh đề, luật hình | 2 | Python | ❌ (template hai tầng) |
| Kiểm đề, verify/ambiguity | 11 | Python | ❌ |
| Sinh ảnh | 2 khối + 1 bộ dựng | Python | ❌ (không gửi LLM) |

**15 trên 30 prompt có phiên bản**, và phần còn lại ở lại dạng Python vì lý do
riêng chứ không vì bỏ sót: luật hình là template hai tầng, `check_prompts` đã là
mô-đun riêng với prompt ngắn, và prompt vẽ ảnh không đi qua LLM.

Không còn prompt nào viết thẳng trong lời gọi `LLMRequest`. Trước đợt này có bốn
cái như vậy — ba ở `plan.py`, một ở `_critic_node` — và chúng **không xuất hiện
trong bất kỳ lần kiểm kê nào làm bằng `grep`**, kể cả lần đầu của chính tài liệu
này; chỉ lần theo `LLMRequest(` mới thấy. Đó là lý do chúng được đưa ra tệp.
