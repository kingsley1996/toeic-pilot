# SPEC-REAL-WORLD-LISTENING.md

## 1. Mục tiêu

Xây dựng tính năng **Real-world Listening / Listening Lab** cho Dictation của TOEIC Pilot.

Cho phép user luyện nghe từ nội dung thực tế như YouTube/TikTok thay vì chỉ luyện audio TOEIC có sẵn.

MVP phải ưu tiên:

- đơn giản để triển khai;
- tái sử dụng engine Dictation hiện tại;
- không download/re-host video YouTube/TikTok;
- transcript có timestamp là dữ liệu trung tâm;
- có thể mở rộng sang Shadowing, Vocabulary và AI Analysis sau này.

> **MVP không xây một hệ thống tải video YouTube/TikTok về server.**
> Video được phát từ nền tảng gốc bằng embed/player. AI chỉ xử lý transcript hoặc media mà ứng dụng có quyền xử lý.

---

# 2. Scope MVP

## In scope

### Source

Hỗ trợ:

1. YouTube URL
2. TikTok URL
3. Upload audio/video của user

### Playback

- YouTube: embedded player.
- TikTok: embedded player nếu URL hợp lệ và embed được.
- Upload: dùng HTML5 audio/video player.
- Play/pause.
- Seek.
- Replay current segment.
- Playback speed: `0.75x`, `1x`, `1.25x`.

### Transcript

MVP hỗ trợ 2 cách:

1. User nhập/paste transcript.
2. User upload media → backend dùng STT để tạo transcript.

Transcript phải có timestamp:

```json
{
  "segments": [
    {
      "id": "seg_001",
      "start": 12.42,
      "end": 15.18,
      "text": "Hello everyone."
    },
    {
      "id": "seg_002",
      "start": 15.18,
      "end": 20.91,
      "text": "Today we're going to discuss the new schedule."
    }
  ]
}
```

### Exercise

MVP chỉ cần một loại exercise:

**Dictation**

Flow:

```text
Listen
  ↓
Replay
  ↓
Type what you hear
  ↓
Check
  ↓
Show expected transcript
  ↓
Record result
```

### Progress

Lưu:

- số lần attempt;
- đúng/sai;
- user answer;
- expected answer;
- completion;
- time spent.

---

# 3. Explicitly out of scope

Không làm trong MVP:

- download YouTube video;
- download TikTok video;
- re-host YouTube/TikTok content;
- tự động crawl arbitrary TikTok/YouTube transcript nếu không có API/quyền phù hợp;
- pronunciation scoring;
- speech recording;
- shadowing;
- AI-generated comprehension questions;
- automatic TOEIC score conversion;
- recommendation engine;
- social sharing;
- public content library;
- playlist;
- offline video.

Các feature trên để phase sau.

---

# 4. User Flow

## 4.1. Create Listening Lesson

UI:

```text
Listening Lab

[ YouTube ] [ TikTok ] [ Upload ]

Paste video URL
┌───────────────────────────────────────┐
│ https://youtube.com/watch?v=...       │
└───────────────────────────────────────┘

[ Continue ]
```

Sau khi validate URL:

```text
Source
✓ YouTube

Title
[ fetched title if available ]

Transcript
┌───────────────────────────────────────┐
│ Paste transcript here...              │
└───────────────────────────────────────┘

[ Create Lesson ]
```

Nếu source là upload:

```text
Upload media
      ↓
STT processing
      ↓
Transcript + timestamps
      ↓
Review transcript
      ↓
Create Lesson
```

---

# 5. Core Data Model

Không gắn logic exercise trực tiếp vào YouTube/TikTok.

Tạo abstraction chung:

```ts
type ListeningSourceType =
  | "youtube"
  | "tiktok"
  | "upload";

interface ListeningSource {
  type: ListeningSourceType;
  externalId?: string;
  url?: string;
  title?: string;
}
```

## ListeningContent

```ts
interface ListeningContent {
  id: string;
  userId: string;

  source: ListeningSource;

  title: string;
  language: "en";

  transcriptStatus:
    | "pending"
    | "ready"
    | "failed";

  segments: ListeningSegment[];

  durationSeconds?: number;

  createdAt: Date;
  updatedAt: Date;
}
```

## ListeningSegment

```ts
interface ListeningSegment {
  id: string;

  start: number;
  end: number;

  text: string;

  normalizedText?: string;
}
```

`start` và `end` tính bằng seconds.

Ví dụ:

```json
{
  "id": "seg_002",
  "start": 15.18,
  "end": 20.91,
  "text": "Today we're going to discuss the new schedule."
}
```

---

# 6. Exercise Model

Dictation exercise phải tham chiếu segment thay vì copy toàn bộ source.

```ts
interface DictationExercise {
  id: string;

  contentId: string;
  segmentId: string;

  promptType: "full";

  expectedText: string;

  start: number;
  end: number;
}
```

MVP dùng `promptType = "full"`.

User phải nghe segment và nhập toàn bộ câu.

Ví dụ:

```text
Audio:
"Today we're going to discuss the new schedule."

Input:
[ Today we're going to __________ ]

```

Không cần AI tạo blank trong MVP.

---

# 7. Answer Checking

Không dùng exact string comparison duy nhất.

Pipeline:

```text
userAnswer
    ↓
normalize
    ↓
compare
    ↓
calculate similarity
    ↓
result
```

Normalization:

- lowercase;
- trim;
- collapse multiple spaces;
- normalize apostrophes;
- bỏ punctuation không quan trọng;
- normalize common whitespace.

Ví dụ:

```text
"I think we're ready."
"I think we're ready"
```

được coi là tương đương.

Không tự động coi:

```text
"has"
"have"
```

là đúng.

MVP có thể dùng:

```ts
exactMatch: boolean
similarity: number
```

Ngưỡng similarity chỉ dùng để hỗ trợ feedback, không tự động thay thế expected answer.

---

# 8. Transcript Validation

Transcript là dữ liệu quan trọng nhất.

Backend phải validate:

### Required

- text không rỗng;
- `start >= 0`;
- `end > start`;
- segments được sort theo `start`;
- không có segment overlap nghiêm trọng;
- timestamp nằm trong duration nếu duration tồn tại.

### Example

```ts
validateTranscript(segments)
```

Trả về:

```ts
{
  valid: true,
  warnings: []
}
```

hoặc:

```ts
{
  valid: false,
  errors: [
    "Segment 3 has end <= start"
  ]
}
```

Không tạo exercise nếu transcript invalid.

---

# 9. Source Resolver

Tạo một service riêng:

```ts
SourceResolver
```

Responsibilities:

- nhận URL;
- detect source;
- extract external ID;
- validate URL;
- trả về normalized source.

Ví dụ:

```ts
resolveSource(url)
```

Input:

```text
https://www.youtube.com/watch?v=abc123
```

Output:

```json
{
  "type": "youtube",
  "externalId": "abc123",
  "url": "https://www.youtube.com/watch?v=abc123"
}
```

TikTok tương tự:

```json
{
  "type": "tiktok",
  "externalId": "...",
  "url": "..."
}
```

Không để frontend tự parse URL theo nhiều nơi.

---

# 10. Player Adapter

Tách player khỏi business logic.

```ts
interface ListeningPlayer {
  play(): void;
  pause(): void;
  seek(seconds: number): void;
  getCurrentTime(): number;
  setPlaybackRate(rate: number): void;
}
```

Implement:

```text
YouTubePlayerAdapter
TikTokPlayerAdapter
Html5MediaPlayerAdapter
```

UI chỉ làm việc với interface.

Ví dụ:

```ts
player.seek(segment.start);
player.play();
```

Không để Dictation component biết source là YouTube hay TikTok.

---

# 11. Segment Playback

Đây là behavior quan trọng của MVP.

Khi user chọn segment:

```text
segment.start
      ↓
player.seek(start)
      ↓
player.play()
      ↓
stop when currentTime >= segment.end
```

UI:

```text
[▶ Replay]

00:15 ─────────────── 00:21
Today we're going to discuss...
```

MVP chỉ cần replay segment hiện tại.

---

# 12. Backend API

API đề xuất:

## Create content

```http
POST /api/listening/contents
```

Request:

```json
{
  "source": {
    "type": "youtube",
    "url": "https://www.youtube.com/watch?v=abc123"
  },
  "title": "Business Meeting",
  "transcript": {
    "segments": []
  }
}
```

Response:

```json
{
  "id": "content_123",
  "status": "ready"
}
```

---

## Get content

```http
GET /api/listening/contents/:id
```

---

## Create exercise

```http
POST /api/listening/contents/:id/exercises
```

MVP backend tạo một dictation exercise cho mỗi valid segment.

---

## Submit answer

```http
POST /api/listening/exercises/:id/attempts
```

Request:

```json
{
  "answer": "Today we're going to discuss the new schedule.",
  "timeSpentSeconds": 21
}
```

Response:

```json
{
  "isCorrect": true,
  "similarity": 1,
  "expectedText": "Today we're going to discuss the new schedule."
}
```

---

# 13. Database

Tối thiểu cần:

```text
listening_contents
listening_segments
dictation_exercises
dictation_attempts
```

## listening_contents

```text
id
user_id
source_type
source_url
external_id
title
duration_seconds
transcript_status
created_at
updated_at
```

## listening_segments

```text
id
content_id
segment_index
start_seconds
end_seconds
text
normalized_text
```

## dictation_exercises

```text
id
content_id
segment_id
created_at
```

Không cần lưu `expected_text` nếu có thể lấy từ segment, trừ khi sau này exercise có biến thể.

## dictation_attempts

```text
id
exercise_id
user_id
answer
is_correct
similarity
time_spent_seconds
created_at
```

---

# 14. Upload + STT

Đây là source duy nhất trong MVP có thể tự động tạo transcript từ media.

Pipeline:

```text
Upload
  ↓
Validate MIME / size
  ↓
Store temporary media
  ↓
Extract audio if necessary
  ↓
Speech-to-text
  ↓
Timestamped transcript
  ↓
Transcript normalization
  ↓
Validation
  ↓
Save segments
  ↓
Generate exercises
```

STT abstraction:

```ts
interface SpeechToTextProvider {
  transcribe(input: MediaInput): Promise<Transcript>;
}
```

Không hard-code provider vào business layer.

---

# 15. AI Usage

MVP **không cần LLM để tạo exercise**.

Lý do:

- transcript đã có;
- dictation answer chính là transcript;
- deterministic dễ test;
- rẻ;
- tránh hallucination;
- dễ debug.

LLM chỉ nên được thêm khi có requirement thực sự cần:

```text
Transcript
   ↓
LLM
   ↓
Vocabulary extraction
   ↓
Difficulty
   ↓
Natural sentence segmentation
   ↓
Advanced exercises
```

Đây là Phase 2.

---

# 16. Frontend Architecture

Đề xuất:

```text
features/listening/
├── components/
│   ├── ListeningSourceForm.tsx
│   ├── ListeningPlayer.tsx
│   ├── TranscriptViewer.tsx
│   ├── SegmentPlayer.tsx
│   ├── DictationExercise.tsx
│   └── ListeningProgress.tsx
│
├── hooks/
│   ├── useListeningPlayer.ts
│   ├── useTranscript.ts
│   └── useDictation.ts
│
├── services/
│   ├── listeningApi.ts
│   └── sourceResolver.ts
│
├── types/
│   └── listening.ts
│
└── utils/
    ├── normalizeTranscript.ts
    └── compareAnswer.ts
```

Không đặt YouTube/TikTok-specific logic trong `DictationExercise`.

---

# 17. UX MVP

## Step 1

```text
Listening Lab

Choose source:

[ YouTube ]
[ TikTok ]
[ Upload ]
```

## Step 2

```text
Paste URL
       ↓
Validate
       ↓
Preview player
```

## Step 3

```text
Transcript

[ Paste transcript ]

[ Create Lesson ]
```

## Step 4

```text
┌────────────────────────────────┐
│          Video Player          │
└────────────────────────────────┘

Segment 1
[▶] Hello everyone.

Segment 2
[▶] Today we're going to discuss
    the new schedule.

---------------------------------

Dictation

Listen to the sentence and type
what you hear.

[______________________________]

[ Check ]
```

## Step 5

Result:

```text
✓ Correct

Expected:
Today we're going to discuss the new schedule.

Your answer:
Today we're going to discuss the new schedule.

[ Next ]
```

---

# 18. Error Handling

Source errors:

```text
INVALID_URL
UNSUPPORTED_SOURCE
VIDEO_NOT_EMBEDDABLE
VIDEO_UNAVAILABLE
```

Transcript errors:

```text
EMPTY_TRANSCRIPT
INVALID_TIMESTAMP
INVALID_SEGMENT_ORDER
TRANSCRIPT_PROCESSING_FAILED
```

Upload errors:

```text
FILE_TOO_LARGE
UNSUPPORTED_MEDIA_TYPE
STT_FAILED
```

UI phải hiển thị message thân thiện, không expose raw exception.

---

# 19. Security

Backend phải:

- validate URL;
- whitelist supported domains;
- validate upload MIME;
- giới hạn upload size;
- không execute arbitrary downloaded files;
- không cho URL tùy ý đi vào internal HTTP fetcher;
- sanitize transcript text;
- enforce ownership bằng `userId`;
- rate-limit STT endpoints.

Đặc biệt:

> Không implement arbitrary URL downloader chỉ để lấy media từ YouTube/TikTok.

---

# 20. Testing

## Unit tests

### Source resolver

```text
YouTube valid URL → youtube
TikTok valid URL → tiktok
invalid URL → error
unsupported domain → error
```

### Transcript validation

```text
valid segments → success
end <= start → error
overlapping segments → warning/error
unsorted segments → error
empty text → error
```

### Answer normalization

```text
"Hello World"
"hello world"
→ equivalent
```

### Answer comparison

Test:

- exact answer;
- punctuation difference;
- capitalization difference;
- missing word;
- extra word;
- contraction;
- whitespace.

---

# 21. Integration tests

Test complete flow:

```text
Create source
   ↓
Create transcript
   ↓
Create segments
   ↓
Create exercises
   ↓
Submit answer
   ↓
Save attempt
   ↓
Return result
```

Upload flow:

```text
Upload
 ↓
STT mock
 ↓
Transcript
 ↓
Segments
 ↓
Exercises
```

Mock STT provider trong test.

---

# 22. Implementation Order

AI coding agent phải thực hiện theo thứ tự này.

## Phase 1 — Domain

1. Define TypeScript/Pydantic types.
2. Create DB models/migrations.
3. Implement transcript validation.
4. Implement answer normalization/comparison.

**Checkpoint:** domain tests pass.

---

## Phase 2 — Backend

1. Implement source resolver.
2. Implement Listening Content API.
3. Implement Segment API.
4. Implement Dictation Exercise API.
5. Implement Attempt API.

**Checkpoint:** API integration tests pass.

---

## Phase 3 — Player

1. Create player interface.
2. Implement HTML5 adapter.
3. Implement YouTube adapter.
4. Implement TikTok adapter.
5. Implement segment replay.

**Checkpoint:** user can replay an individual segment.

---

## Phase 4 — Upload + STT

1. Upload endpoint.
2. Media validation.
3. STT provider abstraction.
4. Timestamped transcript.
5. Persist segments.
6. Error handling.

**Checkpoint:** uploaded audio can become a playable dictation lesson.

---

## Phase 5 — Frontend

1. Source selection.
2. URL form.
3. Player.
4. Transcript viewer.
5. Dictation exercise.
6. Answer feedback.
7. Progress.

**Checkpoint:** complete end-to-end user flow works.

---

## Phase 6 — QA

Test:

- YouTube;
- TikTok;
- upload;
- invalid URLs;
- unavailable videos;
- missing transcript;
- malformed timestamps;
- long transcript;
- mobile layout;
- player seek/replay;
- answer checking;
- persistence.

---

# 23. Definition of Done

MVP được coi là hoàn thành khi user có thể:

```text
1. Open Listening Lab
2. Paste a supported YouTube/TikTok URL
3. See the embedded video
4. Provide a timestamped transcript
5. Create a lesson
6. Select a transcript segment
7. Replay that segment
8. Type what they hear
9. Submit answer
10. See correct/incorrect result
11. Continue to next segment
12. See saved practice history
```

Ngoài ra:

- Upload audio/video phải tạo được transcript bằng STT.
- Không download/re-host YouTube/TikTok media.
- Không cần LLM cho core dictation flow.
- Unit/integration tests phải pass.
- Existing TOEIC Dictation flow không bị break.

---

# 24. Phase 2 — Sau MVP

Sau khi MVP ổn định, mở rộng:

```text
Listening Lab
│
├── Dictation
│
├── Shadowing
│
├── Vocabulary
│
├── Comprehension
│
├── Pronunciation
│
└── AI Coach
```

AI pipeline:

```text
Transcript
    ↓
Sentence Analysis
    ↓
Vocabulary Extraction
    ↓
Difficulty Estimation
    ↓
Exercise Generation
    ↓
Exercise Validator
```

Analytics:

```text
attempts
   ↓
error patterns
   ↓
listening weakness
   ↓
taxonomy
   ↓
AI Analysis
   ↓
Study Planner
```

Ví dụ:

```text
User repeatedly misses:

"going to"
"have to"
"would have"
"did you"

        ↓

AI detects:
Connected Speech / Reduced Forms

        ↓

Add weakness:
listening.connected_speech

        ↓

Study Planner:
Listening → Connected Speech
```

---

# 25. AI Agent Execution Rules

AI coding agent phải tuân thủ các nguyên tắc sau.

### Rule 1 — Inspect first

Trước khi code:

- inspect existing Dictation module;
- tìm data model hiện tại;
- tìm audio player hiện tại;
- tìm API pattern;
- tìm authentication pattern;
- tìm storage pattern;
- tìm test pattern.

Không tạo architecture song song nếu existing code đã có abstraction phù hợp.

### Rule 2 — Reuse existing infrastructure

Ưu tiên reuse:

```text
existing Dictation
existing audio player
existing auth
existing storage
existing database
existing API conventions
existing UI components
existing review/progress system
```

Không duplicate logic.

### Rule 3 — MVP first

Không implement:

- LLM exercise generation;
- shadowing;
- pronunciation;
- recommendation;
- advanced analytics

trước khi core flow hoạt động.

### Rule 4 — Provider abstraction

Các external provider phải nằm sau interface:

```text
SpeechToTextProvider
ListeningPlayer
SourceResolver
```

Không để provider-specific code lan ra toàn application.

### Rule 5 — No arbitrary media downloading

Không thêm dependency hoặc endpoint có mục đích download arbitrary YouTube/TikTok media.

### Rule 6 — Deterministic first

Core dictation phải deterministic:

```text
segment
→ expected text
→ normalize
→ compare
→ result
```

LLM chỉ được thêm khi requirement yêu cầu.

### Rule 7 — Small increments

Sau mỗi phase:

```text
implement
→ test
→ verify
→ commit/checkpoint
→ continue
```

Không thực hiện toàn bộ feature trong một lần thay đổi lớn.

---

# 26. Recommended MVP Architecture

```text
                       ┌─────────────────┐
                       │ Listening Lab UI│
                       └────────┬────────┘
                                │
                    ┌───────────┴───────────┐
                    ↓                       ↓
             Source Resolver           Player Adapter
                    │                       │
          ┌─────────┼─────────┐       ┌─────┼─────┐
          ↓         ↓         ↓       ↓     ↓     ↓
       YouTube   TikTok    Upload    YT   TikTok HTML5
          │         │         │
          │         │         ↓
          │         │        STT
          │         │         │
          └─────────┴─────────┤
                              ↓
                       Transcript
                              ↓
                     Segment Validator
                              ↓
                       ListeningContent
                              ↓
                       Dictation Engine
                              ↓
                         Attempts
                              ↓
                    Learning Analytics
```

**Core principle:**

> `Source → Transcript → Segment → Exercise → Attempt`

Player chỉ là lớp playback.

Source chỉ là nơi nội dung đến từ đâu.

Transcript/Segment mới là domain model trung tâm.

---

# 27. Final MVP Principle

Không xây:

```text
YouTube Feature
TikTok Feature
Upload Feature
```

mà xây:

```text
Listening Content
        ↑
 ┌──────┼──────┐
YouTube TikTok Upload
```

Sau đó:

```text
Listening Content
        ↓
Transcript
        ↓
Segments
        ↓
Dictation
```

Điều này giúp TOEIC Pilot có thể thêm source mới sau này mà không phải viết lại Dictation engine.

MVP thành công khi **một listening segment bất kỳ có timestamp có thể trở thành một Dictation exercise có thể replay, submit và track progress**.
