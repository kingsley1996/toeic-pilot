# Design System — TOEIC Pilot

**Trạng thái:** 🟡 **V2 — PRODUCTION FOUNDATION** · 2026-08-14  
**Phạm vi:** toàn bộ `apps/web`  
**Nguồn sự thật:** token, typography, interaction states, primitive components, domain components, AI components, accessibility và visual QA.

> Một quyết định về hình thức được ra một lần ở đây, không ra lại ở từng trang. Nếu đang chọn màu, spacing, radius, typography hoặc interaction state trong `page.tsx`, quyết định đó thuộc Design System.

---

## 0. Mục tiêu của V2

V2 giữ nguyên hướng **Calibration** của hệ cũ nhưng sửa các điểm khiến design system khó mở rộng:

1. Tách **visual size** khỏi **interactive hit area**.
2. Không dùng `opacity` làm quy tắc disabled chung.
3. Không coi `line-height >= 1.25` là luật tuyệt đối cho mọi loại nội dung.
4. Chuyển spacing từ scale thuần sang **semantic spacing**.
5. Cho phép radius `4 / 6 / 8px` theo hierarchy, nhưng `4px` vẫn là default.
6. Tách component thành **primitives → patterns → domain components → AI components**.
7. Chuẩn hóa **interaction states**.
8. Bổ sung **AI interaction language**.
9. Accessibility trở thành **contract có thể kiểm chứng**, không chỉ là checklist.
10. Responsive và text scaling trở thành acceptance criteria bắt buộc.
11. Giữ nguyên các quyết định product-specific mạnh: Calibration, 4 accent US/UK/AU/CA, dictation diff, score scale, icon mapping và semantic color.

---

# 1. Hướng thiết kế: Calibration

## 1.1 Product premise

**Đối tượng:** người Việt đi làm hoặc sắp đi làm, cần một con số TOEIC cụ thể cho một mục đích cụ thể.

**Việc chính của giao diện mỗi ngày:** đưa người học vào phiên luyện tập, rồi nói thật cho họ biết họ đang ở đâu.

Sản phẩm không phải một app flashcard có thêm audio. Điểm đặc trưng là **độ chính xác**:

- Không xuất bản audio nếu audio không còn khớp transcript.
- Dictation được chấm theo từng từ.
- Không đoán score khi thiếu bảng quy đổi.
- Dữ liệu học được lưu đủ để có thể đánh giá lại về sau.

Vì vậy giao diện là **mặt đọc của một thiết bị đo**.

### Nguyên tắc

- Số liệu phải thẳng hàng.
- Đơn vị phải rõ.
- Threshold thật phải được thể hiện bằng cấu trúc.
- Trạng thái phải có ngữ nghĩa.
- Khi hệ thống không biết, UI phải nói **không biết**.
- Không dùng visual decoration nếu nó không truyền tải hierarchy hoặc information.

---

## 1.2 Không biến anti-slop thành luật thẩm mỹ

Design system không cấm một kỹ thuật vì nó phổ biến.

Ví dụ:

- Shadow không phải luôn sai; overlay thật có thể cần shadow.
- Gradient không phải luôn sai; chỉ dùng khi nó truyền tải dữ liệu liên tục.
- Radius lớn không phải luôn sai; chỉ dùng khi hierarchy của component cần nó.
- Animation không phải luôn sai; chỉ dùng khi nó giúp hiểu trạng thái hoặc nội dung.

**Rule:**

> Không dùng visual technique chỉ để làm UI "đẹp hơn". Dùng nó khi nó truyền tải hierarchy, state, data hoặc interaction.

---

# 2. Design system architecture

Design system có 5 lớp:

```text
TOKENS
  ↓
PRIMITIVES
  ↓
PATTERNS
  ↓
DOMAIN COMPONENTS
  ↓
AI COMPONENTS
```

## 2.1 Tokens

Các giá trị nền tảng:

```text
color
typography
spacing
radius
motion
breakpoints
z-index
```

Tokens không chứa business logic.

## 2.2 Primitives

Các component không biết TOEIC:

```text
Button
Input
Textarea
Select
Panel
Badge
Icon
Tooltip
Dialog
Popover
Skeleton
Tabs
Table
```

## 2.3 Patterns

Các pattern dùng lại giữa nhiều feature:

```text
FormField
StatusLabel
EmptyState
DataTable
PageHeader
Section
ConfirmAction
Pagination
Navigation
```

## 2.4 Domain components

Các component hiểu TOEIC Pilot:

```text
AccentChip
AudioState
AudioButton
DictationDiff
DictationInput
ScoreScale
ReviewCard
QuestionOption
ExamTimer
```

## 2.5 AI components

Các component biểu diễn nội dung và trạng thái AI:

```text
AIMessage
AIExplanation
AISource
AIStreaming
AIConfidence
AIGeneratedContent
AIError
```

### Quy tắc ownership

```text
components/ui/
    primitive

components/patterns/
    reusable product-neutral patterns

components/audio/
    audio domain

components/dictation/
    dictation domain

components/scoring/
    score domain

components/ai/
    AI interaction
```

Không gom toàn bộ component vào một `ui.tsx`.

---

# 3. Color tokens

Tất cả màu phải đi qua semantic token. Không viết hex trực tiếp trong component.

## 3.1 Light

| Token | Hex | Vai trò |
|---|---|---|
| `ground` | `#E9EDF0` | Nền trang |
| `panel` | `#FFFFFF` | Bề mặt nổi |
| `recess` | `#DDE3E8` | Bề mặt chìm |
| `rule` | `#CBD4DB` | Kẻ chia trang trí |
| `rule-strong` | `#738999` | Ranh giới component |
| `ink` | `#0F171D` | Chữ chính |
| `ink-muted` | `#4A5964` | Chữ phụ |
| `ink-faint` | `#5E6C77` | Chú thích |
| `action` | `#C2340F` | Hành động chính |
| `action-hover` | `#A82B0B` | Hover |
| `action-ink` | `#9A2709` | Link / text action |
| `action-tint` | `#FCEDE8` | Nền action nhẹ |
| `on-action` | `#FFFFFF` | Chữ trên action |
| `ok` | `#17694A` | Đúng / hợp lệ |
| `ok-tint` | `#E4F1EA` | Nền ok |
| `warn` | `#8A5A06` | Chưa đúng / cảnh báo |
| `warn-tint` | `#FBF0DC` | Nền warn |
| `alert` | `#A31220` | Lỗi / từ chối |
| `alert-tint` | `#FBE9EA` | Nền alert |

## 3.2 Dark

| Token | Hex | Vai trò |
|---|---|---|
| `ground` | `#0D1317` | Nền trang |
| `panel` | `#151D22` | Bề mặt nổi |
| `recess` | `#080C0F` | Bề mặt chìm |
| `rule` | `#243037` | Kẻ chia |
| `rule-strong` | `#576E7E` | Ranh giới component |
| `ink` | `#E8EEF2` | Chữ chính |
| `ink-muted` | `#9AAAB5` | Chữ phụ |
| `ink-faint` | `#798792` | Chú thích |
| `action` | `#FF6B3D` | Hành động chính |
| `action-hover` | `#FF8355` | Hover |
| `action-ink` | `#FF8A5F` | Link / text action |
| `action-tint` | `#2A1109` | Nền action |
| `on-action` | `#160B05` | Chữ trên action |
| `ok` | `#4BD69B` | Đúng / hợp lệ |
| `ok-tint` | `#0B2A1E` | Nền ok |
| `warn` | `#E8A93C` | Cảnh báo |
| `warn-tint` | `#2E2007` | Nền warn |
| `alert` | `#F87A82` | Lỗi |
| `alert-tint` | `#2E0D10` | Nền alert |

### Semantic rule

```text
action = cần hành động
ok     = hợp lệ / hoàn thành
warn   = chưa đúng / cần chú ý
alert  = lỗi hệ thống / từ chối
```

**Không dùng `action` như màu trạng thái.**

**Không dùng `alert` cho lỗi học tập thông thường.**

Ví dụ dictation sai một từ dùng `warn`, không dùng `alert`.

---

# 4. Accent system — US / UK / AU / CA

Mỗi từ vựng có bốn audio:

```text
US
UK
AU
CA
```

## 4.1 Rules

1. Không dùng màu cờ.
2. Phải phân biệt được khi chuyển grayscale.
3. Màu không bao giờ là kênh thông tin duy nhất.
4. Nhãn `US`, `UK`, `AU`, `CA` luôn đi cùng màu.
5. Không dùng `action` cho accent.
6. Nếu có accent thứ năm, mở rộng semantic scale; không lấy màu action.

| Accent | Light | Dark |
|---|---|---|
| US | `#133965` | `#4187D6` |
| UK | `#5F398B` | `#A57BD5` |
| AU | `#0C6A5E` | `#31B9A6` |
| CA | `#976906` | `#E4B95C` |

### Accessibility rule

Mỗi accent phải được kiểm tra riêng cho:

```text
accent → panel
panel → accent
accent → ground
```

Không suy luận rằng "đạt contrast ở một context" nghĩa là được dùng trên mọi background.

Accent không bao giờ được dùng như sole indicator.

---

# 5. Typography

## 5.1 Font roles

| Role | Font | Dùng cho |
|---|---|---|
| Display | `Archivo` | Heading / score display |
| Body | `Be Vietnam Pro` | Nội dung tiếng Việt |
| Data | `IBM Plex Mono` | Score / duration / numeric data |

Tất cả font cần hỗ trợ Vietnamese subset.

## 5.2 Typography scale

| Token | Size / Leading | Font | Weight |
|---|---:|---|---:|
| `readout` | 64 / 72 | Archivo | 600 |
| `display` | 30 / 38 | Archivo | 600 |
| `title` | 22 / 30 | Archivo | 600 |
| `subtitle` | 17 / 26 | Archivo | 600 |
| `body` | 15 / 25 | Be Vietnam Pro | 400 |
| `body-strong` | 15 / 25 | Be Vietnam Pro | 600 |
| `small` | 13 / 21 | Be Vietnam Pro | 400 |
| `label` | 11 / 16 | Be Vietnam Pro | 600 |
| `data` | 13 / 20 | IBM Plex Mono | 500 |
| `data-lg` | 17 / 26 | IBM Plex Mono | 500 |

## 5.3 Vietnamese line-height rule

Không dùng một luật cứng rằng mọi text phải `>= 1.25`.

Thay vào đó:

```text
body / paragraph      >= 1.5
small / helper text   >= 1.5
heading               >= 1.25
single-line UI label  có thể tighter nếu không wrap
numeric display       kiểm clipping thực tế
```

Mọi typography token phải được kiểm tra với:

```text
ế ộ ữ ậ ổ
Ôn tập
Từ vựng
Câu nghe
Xuất bản
```

## 5.4 Numeric data

Các token data phải bật:

```css
font-variant-numeric: tabular-nums;
```

Áp dụng cho:

```text
score
duration
count
timer
table numeric cells
```

---

# 6. Spacing

Base scale:

```text
4 · 8 · 12 · 16 · 24 · 32 · 48 · 64
```

Không dùng giá trị ngẫu nhiên.

## 6.1 Semantic spacing

| Token | Value | Ý nghĩa |
|---|---:|---|
| `space-micro` | 4px | Khoảng trong icon/text |
| `space-control` | 8px | Nội dung trong control |
| `space-compact` | 12px | Nhóm nhỏ |
| `space-component` | 16px | Giữa các phần của component |
| `space-group` | 24px | Nhóm component |
| `space-section` | 32px | Giữa section |
| `space-page` | 48px | Khoảng page |
| `space-major` | 64px | Section lớn |

Semantic name ưu tiên hơn con số khi abstraction được chia sẻ.

---

# 7. Radius

Radius mặc định là `4px`, nhưng không còn là luật tuyệt đối.

```text
radius-sm     4px
radius-md     6px
radius-lg     8px
radius-pill   999px
radius-none   0
```

## Usage

```text
4px  → button, input, card, badge, default
6px  → component cần hierarchy nhẹ
8px  → modal / surface lớn nếu cần
999px → accent chip
0px  → score scale / measurement rules
```

Không dùng `rounded-xl` hoặc radius lớn chỉ để làm UI "mềm".

---

# 8. Elevation

Default:

> **Không dùng shadow cho hierarchy thông thường.**

Hierarchy chính:

```text
recess
ground
panel
panel + rule-strong
```

Card hover:

```text
rule → rule-strong
```

Không:

```text
hover:-translate-y-0.5
```

## Exception: true overlay

Chỉ dùng shadow cho:

```text
modal
popover
dropdown
menu
```

Token:

```text
shadow-overlay-light = 0 8px 24px rgb(0 0 0 / 0.18)
shadow-overlay-dark  = 0 8px 24px rgb(0 0 0 / 0.50)
```

---

# 9. Motion

```text
duration-state = 120ms
duration-enter = 200ms
easing = cubic-bezier(0.2, 0, 0, 1)
```

Motion phải trả lời một trong ba câu hỏi:

```text
What changed?
Where did it come from?
What should I look at next?
```

Không dùng animation để trang trí.

## Signature motion

Dictation diff có thể reveal từng từ:

```text
24ms stagger
max total = 600ms
>25 words → disable stagger
```

## Reduced motion

`prefers-reduced-motion: reduce` phải tắt:

```text
animation
stagger
decorative transitions
```

Giữ lại state change tức thời.

---

# 10. Icon system

**Lucide / lucide-react.**

## Rules

- Không emoji.
- `14px` cho small text.
- `16px` mặc định.
- `20px` standalone / empty state.
- `currentColor`.
- Icon đi cùng text → `aria-hidden="true"`.
- Icon đứng một mình → bắt buộc accessible name.
- Không icon trong vòng tròn màu chỉ để trang trí.

## Semantic mapping

| Concept | Icon |
|---|---|
| Dictation / nghe | `Headphones` |
| Play / pause | `Play` / `Pause` |
| Accent | `AudioLines` |
| Vocabulary | `Library` |
| Review | `RotateCcw` |
| Topic | `BookOpen` |
| Published | `CircleCheck` |
| Draft | `CircleDashed` |
| Audio missing | `CircleSlash` |
| Audio stale | `TriangleAlert` |
| Publish | `Send` |
| Error / rejected | `OctagonAlert` |
| Account | `UserRound` |
| Logout | `LogOut` |
| Mobile menu / close | `Menu` / `X` |
| Content editor | `SquarePen` |
| Content tree | `FolderTree` |
| Section / story | `Layers` / `FileText` |
| Check answer | `Check` |
| Flag | `Flag` |
| Copy | `Copy` → `Check` |
| Timer | `Clock` |
| Archive | `Archive` |
| Delete | `Trash2` |
| Back | `ArrowLeft` |
| Field error | `CircleAlert` |
| Help | `Info` |
| Not found | `Compass` |
| Theme | `Sun` / `Moon` / `Monitor` |

Một concept chỉ có một canonical icon.

---

# 11. Interaction state system

Mọi interactive primitive phải định nghĩa state trước khi implementation.

## 11.1 Common states

```text
default
hover
focus-visible
active / pressed
selected
disabled
loading
error
success
```

Không phải component nào cũng cần mọi state.

## 11.2 State priority

```text
disabled
  >
error
  >
selected
  >
active
  >
hover
  >
default
```

Focus là **accessibility layer**, không phải visual status.

## 11.3 State contract

Ví dụ Button:

```text
Button
├── default
├── hover
├── focus-visible
├── pressed
├── disabled
└── loading
```

AudioChip:

```text
AudioChip
├── idle
├── selected
├── playing
├── missing
└── disabled
```

Dictation:

```text
Dictation
├── idle
├── typing
├── checking
├── result
├── stale-result
└── error
```

---

# 12. Primitives

## 12.1 Button

### Variants

| Variant | Use |
|---|---|
| `primary` | Một hành động chính |
| `secondary` | Hành động phụ |
| `quiet` | Toolbar / hành động thứ ba |
| `destructive` | Xóa / huỷ |

Không có `success` button.

### Visual size

```text
sm = 28px
md = 36px
lg = 44px
```

### Interactive hit area

Visual size và hit area là hai khái niệm khác nhau.

```text
desktop:
  hit area >= visual size

mobile:
  hit area >= 44 × 44px
```

Một button `28px` có thể có wrapper/hit area `44px`.

### Disabled

Không dùng `opacity: 0.45` như rule chung.

Disabled phải:

```text
remain visible
remain understandable
not appear clickable
```

Ví dụ:

```text
background → recess
text       → ink-faint
border     → rule
cursor     → not-allowed
```

Nếu disabled vì business condition, hiển thị reason bằng accessible description.

Không phụ thuộc vào HTML `title` làm explanation chính.

---

# 13. Surface components

## Panel

```text
background: panel
border: rule
radius: 4px
shadow: none
```

## PanelLink

Hover:

```text
rule → rule-strong
panel → recess
```

Không lift.

## Recess

Dùng cho:

```text
table header
read-only area
disabled input background
secondary information
```

---

# 14. Form components

## Input

```text
background: panel
border: rule-strong
radius: 4px
```

Error:

```text
border: alert
icon: CircleAlert / OctagonAlert
helper text: alert
```

Không chỉ đổi màu border.

## FormField

Cấu trúc:

```text
Label
Control
Description
Error
```

Accessibility:

```text
label → htmlFor
description → aria-describedby
error → aria-describedby
invalid → aria-invalid
```

---

# 15. Status components

Status luôn có ít nhất:

```text
icon + text
```

Không dùng màu làm sole indicator.

| State | Token | Icon |
|---|---|---|
| Published | `ok` | `CircleCheck` |
| Draft | `ink-muted` | `CircleDashed` |
| Audio stale | `warn` | `TriangleAlert` |
| Audio missing | `alert` | `CircleSlash` |

---

# 16. AccentChip

Đây là domain component, không phải generic Badge.

Rules:

- `US`, `UK`, `AU`, `CA` luôn hiện.
- Selected → accent background + accessible contrasting text.
- Unselected → transparent + rule-strong + accent dot.
- Missing → disabled + `CircleSlash`.
- Playing → selected + playback indicator.
- Duration dùng `IBM Plex Mono`.
- Màu không bao giờ là sole indicator.

---

# 17. EmptyState

Không căn giữa mặc định.

Cấu trúc:

```text
icon
title
description
primary next action
```

Empty state phải trả lời:

> "Bây giờ người dùng nên làm gì?"

Không dùng:

```text
Không có dữ liệu.
```

nếu có thể đưa ra next action.

---

# 18. Navigation

Có hai shell:

```text
AppShell
AdminShell
```

## Learner

Không sidebar.

## Admin

Có sidebar.

Phân biệt bằng structure, không cần thêm màu riêng.

### Rules

- Admin không nằm trong learner primary nav.
- Một cửa vào admin.
- Admin luôn có `← Về khu học`.
- Navigation labels không wrap.
- `shrink-0 whitespace-nowrap` cho nav item khi cần.

---

# 19. Dictation system

Dictation có 4 trạng thái hiển thị chính:

| State | Visual |
|---|---|
| Correct | `ok` + normal |
| Missing | `warn` + emphasized |
| Extra | `warn` + strikethrough |
| Unreached | `ink-faint` + masked |

Màu + typography là hai kênh thông tin độc lập.

## Rules

- Không dùng `alert` cho mistake của learner.
- Không hiển thị answer của phần chưa gõ.
- `unreached` được mask bằng `*`.
- Accuracy vẫn tính trên toàn câu.
- Không dùng phần trăm trên UI dictation.
- Result nằm ngay dưới input.
- Nếu text thay đổi sau khi chấm, result phải hiển thị là stale.
- Enter chỉ thực hiện một action.
- `event.repeat` phải được xử lý.
- Shift+Enter vẫn giữ hành vi xuống dòng.

---

# 20. Skeleton

Skeleton phải có đúng shape của content tương lai.

```text
background: recess
animation: subtle
duration: 1.4s
```

Không dùng:

```text
"Đang tải..."
```

trong skeleton.

Skeleton phải tôn trọng `prefers-reduced-motion`.

---

# 21. Signature component: ScoreScale

ScoreScale là component domain quan trọng nhất.

Không dùng:

```text
big number + gradient
```

Mà dùng:

```text
score
real thresholds
current marker
target marker
section scores
```

Ví dụ:

```text
10      255      405      605      785      905      990
├────────┼────────┼────────┼────────┼────────┼────────┤
                  ▲
                645
```

## Rules

1. Threshold đến từ `score_conversion`.
2. Không hard-code threshold trong component.
3. Scale không giả định tuyến tính.
4. Target là marker riêng.
5. Nếu thiếu conversion table:
   - score = `—`
   - scale = neutral
   - explanation = "Đề này chưa có bảng quy đổi."
6. Không hiện `0`.
7. Không nội suy.
8. Không giấu component khi score không thể tính.

---

# 22. AI interaction system

AI Layer phải có ngôn ngữ UI riêng.

AI output không mặc định là authoritative.

## 22.1 AI states

```text
generated
retrieved
verified
uncertain
streaming
failed
regenerating
```

## 22.2 Source semantics

Phân biệt:

```text
AI-generated explanation
Retrieved source
User data
System data
```

Không dùng cùng visual treatment cho tất cả.

## 22.3 AIMessage

Cấu trúc:

```text
AI identity
content
source / provenance nếu có
state
actions
```

## 22.4 Streaming

Streaming phải có state rõ:

```text
thinking
streaming
complete
failed
```

Không hiển thị spinner vô thời hạn.

## 22.5 Uncertainty

Khi model không chắc:

```text
uncertain
```

không dùng `alert` nếu đây không phải system error.

Ví dụ:

```text
Có thể đáp án là B, nhưng cần xem ngữ cảnh đầy đủ.
```

## 22.6 Generated content

Nội dung AI sinh ra phải phân biệt với nội dung curriculum đã publish.

```text
generated ≠ published
```

---

# 23. Responsive system

Breakpoints không chỉ là CSS breakpoint. Mỗi component phải có responsive behavior.

## Minimum viewport

```text
360px
```

Không được horizontal overflow.

## Text scaling

UI phải hoạt động ở:

```text
100%
125%
150%
200%
```

Không dùng fixed height cho text content nếu nó có thể wrap.

## Mobile

Mọi interactive target:

```text
>= 44 × 44px
```

Visual control có thể nhỏ hơn nếu hit area được mở rộng.

## Responsive acceptance

Kiểm tối thiểu:

```text
360px
390px
768px
1024px
1280px
```

---

# 24. Accessibility contract

Đây là **definition of done**, không phải nice-to-have.

## Keyboard

Mọi interactive flow phải dùng được bằng:

```text
Tab
Shift+Tab
Enter
Space
Escape
Arrow keys
```

nếu component yêu cầu.

## Focus

```css
:focus-visible {
  outline: 2px solid action;
  outline-offset: 2px;
}
```

Không remove focus mà không có replacement.

## Contrast

Kiểm tra:

```text
text contrast >= 4.5:1
large text >= 3:1
component boundary >= 3:1
focus indicator >= 3:1
```

## Color independence

Không có information chỉ nằm ở:

```text
red / green / orange / blue
```

Luôn có thêm:

```text
icon
text
shape
typography
position
```

tùy context.

## Touch target

```text
>= 44 × 44px
```

## Zoom

Không bị:

```text
clipped
overlapped
hidden
horizontal overflow
```

ở 200% text size.

## Vietnamese stress test

Bắt buộc kiểm:

```text
Ôn tập
Từ vựng
Câu nghe
Xuất bản
Điểm ước tính
Đã hoàn thành
Chưa có audio
```

---

# 25. Theme system

Có ba mode:

```text
system
light
dark
```

Priority:

```text
explicit user choice
    >
system preference
```

Theme preference phải được set trước first paint để tránh flash.

Tokens không được định nghĩa chỉ trong dark media query.

---

# 26. Implementation contract

## globals.css

Chứa:

```text
CSS variables
base typography
focus
motion preference
```

## tailwind.config.ts

Chứa:

```text
semantic colors
radius
font families
motion tokens
```

Không chứa business-specific component styles.

## Components

Không hard-code:

```text
hex
random spacing
random radius
shadow
```

trong component.

## Domain components

Được phép biết:

```text
AudioState
ScoreConversion
DictationDiff
AIState
```

Primitive không được biết những thứ này.

---

# 27. Recommended folder structure

```text
src/
├── app/
│   └── ...
│
├── components/
│   ├── ui/
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── textarea.tsx
│   │   ├── panel.tsx
│   │   ├── badge.tsx
│   │   ├── dialog.tsx
│   │   ├── popover.tsx
│   │   ├── skeleton.tsx
│   │   └── index.ts
│   │
│   ├── patterns/
│   │   ├── form-field.tsx
│   │   ├── empty-state.tsx
│   │   ├── status-label.tsx
│   │   ├── page-header.tsx
│   │   └── index.ts
│   │
│   ├── audio/
│   │   ├── accent-chip.tsx
│   │   ├── audio-button.tsx
│   │   └── audio-state.tsx
│   │
│   ├── dictation/
│   │   ├── dictation-input.tsx
│   │   ├── dictation-diff.tsx
│   │   └── dictation-legend.tsx
│   │
│   ├── scoring/
│   │   └── score-scale.tsx
│   │
│   ├── ai/
│   │   ├── ai-message.tsx
│   │   ├── ai-source.tsx
│   │   ├── ai-streaming.tsx
│   │   ├── ai-confidence.tsx
│   │   └── ai-state.tsx
│   │
│   └── navigation/
│       ├── app-shell.tsx
│       ├── admin-shell.tsx
│       └── nav.tsx
│
├── lib/
│   └── ...
│
└── styles/
    └── globals.css
```

---

# 28. Design tokens — canonical list

```text
COLOR
  ground
  panel
  recess
  rule
  rule-strong

  ink
  ink-muted
  ink-faint

  action
  action-hover
  action-ink
  action-tint
  on-action

  ok
  ok-tint
  warn
  warn-tint
  alert
  alert-tint

  accent-us
  accent-uk
  accent-au
  accent-ca

TYPOGRAPHY
  readout
  display
  title
  subtitle
  body
  body-strong
  small
  label
  data
  data-lg

SPACING
  space-micro
  space-control
  space-compact
  space-component
  space-group
  space-section
  space-page
  space-major

RADIUS
  radius-sm
  radius-md
  radius-lg
  radius-pill
  radius-none

MOTION
  duration-state
  duration-enter
  easing-standard

ELEVATION
  shadow-overlay
```

---

# 29. Migration from V1

| V1 | V2 |
|---|---|
| `surface` | `ground` |
| `surface-raised` | `panel` |
| `surface-sunken` | `recess` |
| `border` | `rule` |
| `border-strong` | `rule-strong` |
| `text` | `ink` |
| `text-muted` | `ink-muted` |
| `text-subtle` | `ink-faint` |
| `brand` | `action` |
| `brand-hover` | `action-hover` |
| `brand-soft` | `action-tint` |
| `brand-text` | `action-ink` |
| `success` | `ok` |
| `warning` | `warn` |
| `danger` | `alert` |

Migration phải được thực hiện một lượt. Không để token cũ và mới cùng tồn tại.

---

# 30. Definition of Done

Một màn hình chỉ được coi là hoàn thành khi:

## Visual

- [ ] Không hard-code color.
- [ ] Không random spacing.
- [ ] Không random radius.
- [ ] Không shadow ngoài approved overlay.
- [ ] Không hover lift.
- [ ] Icon đúng canonical mapping.

## Interaction

- [ ] Default state.
- [ ] Hover nếu applicable.
- [ ] Focus-visible.
- [ ] Active/pressed nếu applicable.
- [ ] Disabled nếu applicable.
- [ ] Loading nếu applicable.
- [ ] Error/success nếu applicable.

## Accessibility

- [ ] Keyboard usable.
- [ ] Focus visible.
- [ ] Touch target >= 44×44.
- [ ] Contrast verified.
- [ ] Color không phải sole indicator.
- [ ] Labels / descriptions / errors có semantic relationship.
- [ ] 200% text scaling không vỡ.
- [ ] 360px không horizontal overflow.

## Responsive

- [ ] 360px.
- [ ] 390px.
- [ ] 768px.
- [ ] 1024px.
- [ ] 1280px.

## Vietnamese

- [ ] Không clipping dấu.
- [ ] Không collision giữa các dòng.
- [ ] Heading và label đọc tự nhiên.
- [ ] Text dài có thể wrap.

## AI

Nếu có AI content:

- [ ] Generated state rõ.
- [ ] Streaming state rõ.
- [ ] Error state rõ.
- [ ] Uncertainty không bị biểu diễn như fact.
- [ ] Provenance/source được thể hiện khi cần.

---

# 31. Verification

## Static checks

```bash
grep -rnP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' apps/web/src
grep -rn 'shadow-sm\|shadow-md\|shadow-lg\|rounded-xl' apps/web/src
grep -rn 'brand\|surface\|text-subtle' apps/web/src
```

Expected:

```text
emoji → empty
legacy tokens → empty
unapproved shadows/radius → empty
```

## Build checks

```bash
pnpm lint
pnpm build
pnpm tsc --noEmit
pnpm format:check
```

## Manual QA

Mỗi release phải kiểm:

```text
light
dark
system theme

keyboard
mouse
touch

360px
390px
768px
1024px
1280px

100% text
125%
150%
200%

Vietnamese diacritics
```

---

# 32. Visual regression

Design system nên có visual regression cho các canonical states:

```text
Button:
  default
  hover
  focus
  disabled
  loading

Input:
  default
  focus
  error
  disabled

AccentChip:
  US
  UK
  AU
  CA
  selected
  missing

AudioState:
  ready
  stale
  missing
  error

Dictation:
  correct
  missing
  extra
  unreached
  stale result

ScoreScale:
  valid score
  target
  missing conversion

AI:
  generated
  streaming
  uncertain
  failed
```

Mục tiêu không phải snapshot toàn bộ app. Mục tiêu là bảo vệ **canonical design primitives và domain states**.

---

# 33. Khi nào xem lại design system

### Thêm accent thứ năm

Mở rộng accent scale. Không lấy `action`.

### Sprint TOEIC Practice

Bổ sung:

```text
QuestionOption
ExamTimer
AnswerGrid
ScoreScale
Part1 attribution
```

### Sprint AI Layer

Bổ sung:

```text
AIMessage
AIExplanation
AIStreaming
AIConfidence
AISource
AIError
```

### Có user thật

Đo trước:

```text
dictation completion
score comprehension
accent recognition
AI explanation comprehension
```

Không thay đổi design chỉ vì preference cá nhân nếu chưa có evidence.

---

# 34. Design principles — bản ngắn

Nếu phải nhớ đúng 10 điều:

```text
1. Measure, don't decorate.
2. Unknown data stays unknown.
3. Semantic tokens over raw values.
4. Structure over decoration.
5. Color is never the only signal.
6. Visual size is not hit area.
7. Every interactive component has explicit states.
8. Domain components encode real product concepts.
9. AI output is not automatically authoritative.
10. Accessibility is part of "done".
```

---

# 35. Final architecture

```text
                         TOEIC PILOT
                              │
                         CALIBRATION
                              │
             ┌────────────────┼────────────────┐
             ↓                ↓                ↓
           TOKENS          STATES           RULES
             │                │                │
      color/spacing      interaction       accessibility
      typography         loading           responsive
      radius             error             content
      motion             selected          semantics
             │                │                │
             └────────────────┼────────────────┘
                              ↓
                         PRIMITIVES
                              │
                    Button / Input / Panel
                              │
                              ↓
                          PATTERNS
                              │
                  Form / Empty / Status / Nav
                              │
             ┌────────────────┼────────────────┐
             ↓                ↓                ↓
           AUDIO          DICTATION         SCORING
             │                │                │
        AccentChip       DictationDiff      ScoreScale
             │                │                │
             └────────────────┼────────────────┘
                              ↓
                             AI
                              │
              generated / retrieved / uncertain
                  streaming / verified / failed
                              │
                              ↓
                       PRODUCT UI
```

**Nguồn sự thật duy nhất:** file này.  
Component không tự tạo token. Page không tự tạo component pattern. AI không tự tạo visual language. Domain state phải có representation rõ ràng trong UI.
