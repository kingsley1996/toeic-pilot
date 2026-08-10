// Request/response shapes are DERIVED, not hand-written: they come from FastAPI's
// own OpenAPI schema via scripts/generate-api-types.sh. Editing them here would
// reintroduce the silent contract drift documented in planning/REVIEW-OPUS.md P1-4.
import type { components } from "./api-types";

export type TokenResponse = components["schemas"]["TokenResponse"];
export type UserPublic = components["schemas"]["UserPublic"];
export type UserRegister = components["schemas"]["UserRegister"];
export type UserLogin = components["schemas"]["UserLogin"];
export type HTTPValidationError = components["schemas"]["HTTPValidationError"];

// Learning Hub
export type TopicPublic = components["schemas"]["TopicPublic"];
export type AudioClip = components["schemas"]["AudioClip"];
export type DictationTopicPublic = components["schemas"]["DictationTopicPublic"];
export type DictationTopicDetail = components["schemas"]["DictationTopicDetail"];
export type DictationSectionDetail = components["schemas"]["DictationSectionDetail"];
export type DictationStoryDetail = components["schemas"]["DictationStoryDetail"];
export type DictationStorySummary = components["schemas"]["DictationStorySummary"];
export type StoryItem = components["schemas"]["StoryItem"];
export type StoryProgress = components["schemas"]["StoryProgress"];
export type DictationTopicAdmin = components["schemas"]["DictationTopicAdmin"];
export type DictationSectionAdmin = components["schemas"]["DictationSectionAdmin"];
export type DictationStoryAdmin = components["schemas"]["DictationStoryAdmin"];
export type VocabularySummary = components["schemas"]["VocabularySummary"];
export type VocabularyDetail = components["schemas"]["VocabularyDetail"];
export type VocabularyProgress = components["schemas"]["VocabularyProgress"];
export type VocabularyMastery = components["schemas"]["VocabularyMastery"];
export type ReviewCard = components["schemas"]["ReviewCard"];
export type ReviewSession = components["schemas"]["ReviewSession"];
export type ReviewResult = components["schemas"]["ReviewResult"];
export type RecallResult = components["schemas"]["RecallResult"];
export type UserProfilePublic = components["schemas"]["UserProfilePublic"];
export type UserProfileUpdate = components["schemas"]["UserProfileUpdate"];
export type PasswordChange = components["schemas"]["PasswordChange"];
export type LearningStats = components["schemas"]["LearningStats"];
export type StudyDay = components["schemas"]["StudyDay"];
export type UploadTicket = components["schemas"]["UploadTicket"];
export type ImageAssetPublic = components["schemas"]["ImageAssetPublic"];
export type ImageConfirm = components["schemas"]["ImageConfirm"];
export type CollectionSummary = components["schemas"]["CollectionSummary"];
export type CollectionDetail = components["schemas"]["CollectionDetail"];
export type TestSummary = components["schemas"]["TestSummary"];
export type TestDetail = components["schemas"]["TestDetail"];
export type PartBreakdown = components["schemas"]["PartBreakdown"];
export type AttemptState = components["schemas"]["AttemptState"];
export type AttemptResult = components["schemas"]["AttemptResult"];
export type QuestionPublic = components["schemas"]["QuestionPublic"];
export type AttemptPartProgress = components["schemas"]["AttemptPartProgress"];
export type DictationSummary = components["schemas"]["DictationSummary"];
export type DictationDetail = components["schemas"]["DictationDetail"];
export type DictationResult = components["schemas"]["DictationResult"];
export type WordDiff = components["schemas"]["WordDiff"];

// Content admin
export type TopicAdmin = components["schemas"]["TopicAdmin"];
export type VocabularyRow = components["schemas"]["VocabularyRow"];
export type DictationRow = components["schemas"]["DictationRow"];
export type VocabularyParseResponse = components["schemas"]["VocabularyParseResponse"];
export type DictationParseResponse = components["schemas"]["DictationParseResponse"];
export type CommitResult = components["schemas"]["CommitResult"];
export type VocabularyAdmin = components["schemas"]["VocabularyAdmin"];
export type DictationAdmin = components["schemas"]["DictationAdmin"];
export type AudioSlotState = components["schemas"]["AudioSlotState"];

// Escape hatch for callers that need a shape not aliased above.
export type { components, paths } from "./api-types";

export const API_ROUTES = {
  health: "/health",
  ready: "/ready",
  register: "/api/v1/auth/register",
  login: "/api/v1/auth/login",
  me: "/api/v1/auth/me",
  changePassword: "/api/v1/auth/password",

  // Hồ sơ người dùng. Không có biến thể nhận id: đây là dữ liệu riêng của
  // chính người đang đăng nhập, không phải trang cá nhân công khai.
  profile: "/api/v1/profile",
  profileStats: "/api/v1/profile/stats",
  avatarTicket: "/api/v1/profile/avatar/ticket",
  avatar: "/api/v1/profile/avatar",

  // Thư viện ảnh. Upload đi THẲNG tới nhà cung cấp; API chỉ ký vé và ghi
  // nhận (ADR-006 §2.3), nên không có đường nào ở đây nhận byte của file.
  // Luyện thi TOEIC. Công khai: danh sách đề là thứ người ta xem TRƯỚC khi
  // quyết định đăng ký, nên bắt đăng nhập để nhìn sẽ chặn đúng nhóm người mà
  // trang này tồn tại để thuyết phục.
  testCollections: "/api/v1/test-collections",
  testCollection: (slug: string) => `/api/v1/test-collections/${slug}`,
  practiceTest: (slug: string) => `/api/v1/practice-tests/${slug}`,
  attempts: "/api/v1/attempts",
  attempt: (id: string) => `/api/v1/attempts/${id}`,
  attemptAnswer: (id: string, questionId: string) =>
    `/api/v1/attempts/${id}/questions/${questionId}`,
  attemptSubmit: (id: string) => `/api/v1/attempts/${id}/submit`,

  adminImages: "/api/v1/admin/media/images",
  adminImageTicket: "/api/v1/admin/media/images/ticket",
  adminImageConfirm: "/api/v1/admin/media/images/confirm",

  // Learning Hub
  topics: "/api/v1/topics",
  vocabulary: "/api/v1/vocabulary",
  vocabularyDetail: (id: string) => `/api/v1/vocabulary/${id}`,
  reviewSession: "/api/v1/vocabulary-review/session",
  // Gạch nối, không phải `/vocabulary/progress`: route `/vocabulary/{entry_id}`
  // sẽ bắt "progress" trước rồi 422 khi parse nó thành UUID.
  vocabularyProgress: "/api/v1/vocabulary-progress",
  submitReview: (id: string) => `/api/v1/vocabulary/${id}/review`,
  submitRecall: (id: string) => `/api/v1/vocabulary/${id}/recall`,
  dictation: "/api/v1/dictation",
  dictationDetail: (id: string) => `/api/v1/dictation/${id}`,
  submitDictation: (id: string) => `/api/v1/dictation/${id}/attempts`,

  // Cây dictation. Gạch nối chứ không lồng vào `/dictation/...`: đường dẫn động
  // `/dictation/{item_id}` khai kiểu UUID và sẽ bắt mất `/dictation/topics`.
  dictationTopics: "/api/v1/dictation-topics",
  dictationTopic: (id: string) => `/api/v1/dictation-topics/${id}`,
  dictationSection: (id: string) => `/api/v1/dictation-sections/${id}`,
  dictationStory: (id: string) => `/api/v1/dictation-stories/${id}`,

  // Content admin
  adminTopics: "/api/v1/admin/topics",
  adminVocabulary: "/api/v1/admin/vocabulary",
  adminVocabularyParse: "/api/v1/admin/vocabulary/parse",
  adminVocabularyItem: (id: string) => `/api/v1/admin/vocabulary/${id}`,
  adminVocabularyPublish: (id: string) => `/api/v1/admin/vocabulary/${id}/publish`,
  adminDictation: "/api/v1/admin/dictation",
  adminDictationParse: "/api/v1/admin/dictation/parse",
  adminDictationItem: (id: string) => `/api/v1/admin/dictation/${id}`,
  adminDictationPublish: (id: string) => `/api/v1/admin/dictation/${id}/publish`,
  adminDictationTopics: "/api/v1/admin/dictation/topics",
  adminDictationTopicPublish: (id: string) => `/api/v1/admin/dictation/topics/${id}/publish`,
  adminDictationSections: "/api/v1/admin/dictation/sections",
  adminDictationSectionPublish: (id: string) => `/api/v1/admin/dictation/sections/${id}/publish`,
  adminDictationStories: "/api/v1/admin/dictation/stories",
  adminDictationStoryPublish: (id: string) => `/api/v1/admin/dictation/stories/${id}/publish`,
  adminDictationTopic: (id: string) => `/api/v1/admin/dictation/topics/${id}`,
  adminDictationSection: (id: string) => `/api/v1/admin/dictation/sections/${id}`,
  adminDictationStory: (id: string) => `/api/v1/admin/dictation/stories/${id}`,
  adminDictationStoryReorder: (id: string) => `/api/v1/admin/dictation/stories/${id}/reorder`,
} as const;
