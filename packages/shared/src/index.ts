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
export type AttemptSummary = components["schemas"]["AttemptSummary"];
/**
 * Một trang kết quả. Chỉ endpoint nào PHÌNH được mới bọc phong bì này — danh
 * sách có trần trong miền nghiệp vụ (giọng đọc, câu của một đề) vẫn trả mảng
 * trần. Xem `app/schemas/common.py` để biết quy tắc phân nhóm.
 */
export type AttemptPage = components["schemas"]["Page_AttemptSummary_"];
export type VocabularyPage = components["schemas"]["Page_VocabularySummary_"];
export type DictationPage = components["schemas"]["Page_DictationSummary_"];
export type VocabularyAdminPage = components["schemas"]["Page_VocabularyAdmin_"];
export type DictationAdminPage = components["schemas"]["Page_DictationAdmin_"];
export type DictationStoryAdminPage = components["schemas"]["Page_DictationStoryAdmin_"];
export type DictationSectionAdminPage = components["schemas"]["Page_DictationSectionAdmin_"];
export type TestAdminPage = components["schemas"]["Page_TestAdmin_"];
export type QuestionPublic = components["schemas"]["QuestionPublic"];
export type PassagePublic = components["schemas"]["PassagePublic"];
export type AttemptPartProgress = components["schemas"]["AttemptPartProgress"];
export type TestAdmin = components["schemas"]["TestAdmin"];
export type CollectionAdmin = components["schemas"]["CollectionAdmin"];
export type SetAdmin = components["schemas"]["SetAdmin"];
export type AudioAssetPublic = components["schemas"]["AudioAssetPublic"];
export type TurnDraft = components["schemas"]["TurnDraft"];
export type VoiceOption = components["schemas"]["VoiceOption"];
export type AudioRequestAck = components["schemas"]["AudioRequestAck"];
export type PassageAdmin = components["schemas"]["PassageAdmin"];
export type TestPartSummary = components["schemas"]["TestPartSummary"];
export type QuestionAdmin = components["schemas"]["QuestionAdmin"];
export type TestPartParseResponse = components["schemas"]["TestPartParseResponse"];
export type GroupDraft = components["schemas"]["GroupDraft"];
export type QuestionDraft = components["schemas"]["QuestionDraft"];
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
export type LlmStats = components["schemas"]["LlmStatsPublic"];
export type QuestionLabelRow = components["schemas"]["QuestionLabelRow"];
export type FacetCatalog = components["schemas"]["FacetCatalog"];
export type AiFeatureRow = components["schemas"]["AiFeatureRow"];
export type CoachExplanation = components["schemas"]["CoachExplanationPublic"];
export type KnownModel = components["schemas"]["KnownModel"];
export type LabelValue = components["schemas"]["LabelValue"];

// Escape hatch for callers that need a shape not aliased above.
export type { components, paths } from "./api-types";

export const API_ROUTES = {
  health: "/health",
  ready: "/ready",
  register: "/api/v1/auth/register",
  login: "/api/v1/auth/login",
  me: "/api/v1/auth/me",
  changePassword: "/api/v1/auth/password",
  logout: "/api/v1/auth/logout",

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
  attemptResult: (id: string) => `/api/v1/attempts/${id}/result`,
  attempt: (id: string) => `/api/v1/attempts/${id}`,
  attemptAnswer: (id: string, questionId: string) =>
    `/api/v1/attempts/${id}/questions/${questionId}`,
  attemptSubmit: (id: string) => `/api/v1/attempts/${id}/submit`,

  adminImageTicket: "/api/v1/admin/media/images/ticket",
  adminImageConfirm: "/api/v1/admin/media/images/confirm",
  adminAudioTicket: "/api/v1/admin/media/audio/ticket",
  adminAudioConfirm: "/api/v1/admin/media/audio/confirm",

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
  // Soạn đề thi (ADR-007). `parse` không ghi gì; `parts` mới là đường ghi.
  adminTestCollections: "/api/v1/admin/test-collections",
  adminTestCollectionPublish: (slug: string) => `/api/v1/admin/test-collections/${slug}/publish`,
  adminTests: "/api/v1/admin/tests",
  adminTest: (slug: string) => `/api/v1/admin/tests/${slug}`,
  adminTestQuestions: (slug: string) => `/api/v1/admin/tests/${slug}/questions`,
  adminTestPartParse: (slug: string, part: number) =>
    `/api/v1/admin/tests/${slug}/parts/${part}/parse`,
  adminTestParts: (slug: string) => `/api/v1/admin/tests/${slug}/parts`,
  adminTestPublish: (slug: string) => `/api/v1/admin/tests/${slug}/publish`,
  adminQuestionPublish: (id: string) => `/api/v1/admin/questions/${id}/publish`,
  adminQuestion: (id: string) => `/api/v1/admin/questions/${id}`,
  adminQuestionArchive: (id: string) => `/api/v1/admin/questions/${id}/archive`,
  adminTestArchive: (slug: string) => `/api/v1/admin/tests/${slug}/archive`,
  adminCollectionArchive: (slug: string) => `/api/v1/admin/test-collections/${slug}/archive`,
  adminCollection: (slug: string) => `/api/v1/admin/test-collections/${slug}`,
  adminTestSets: (slug: string) => `/api/v1/admin/tests/${slug}/sets`,
  adminQuestionSet: (setId: string) => `/api/v1/admin/question-sets/${setId}`,
  adminVoices: "/api/v1/admin/voices",
  adminAudioRequests: "/api/v1/admin/media/audio/requests",
  adminPassageImage: (setId: string) => `/api/v1/admin/question-sets/${setId}/passage-image`,
  adminQuestionAudio: (id: string) => `/api/v1/admin/questions/${id}/audio`,
  adminQuestionImage: (id: string) => `/api/v1/admin/questions/${id}/image`,
  adminSetAudio: (setId: string) => `/api/v1/admin/question-sets/${setId}/audio`,
  adminDictationTopic: (id: string) => `/api/v1/admin/dictation/topics/${id}`,
  adminDictationSection: (id: string) => `/api/v1/admin/dictation/sections/${id}`,
  adminDictationStory: (id: string) => `/api/v1/admin/dictation/stories/${id}`,
  // Tầng AI. `skillTagRequests` là một tiếng CHUÔNG — nó trả 202 và không hứa
  // nhãn đã có; API không gắn nhãn được (không import nổi `app.content`).
  adminAiStats: "/api/v1/admin/ai/stats",
  // Coach — chỉ dùng được sau khi lượt làm bài đã nộp; máy chủ trả 409 nếu chưa.
  coachExplain: (attemptId: string, questionId: string) =>
    `/api/v1/attempts/${attemptId}/items/${questionId}/coach`,
  coachChat: (attemptId: string) => `/api/v1/attempts/${attemptId}/chat`,
  coachFeedback: (attemptId: string, questionId: string) =>
    `/api/v1/attempts/${attemptId}/items/${questionId}/coach/feedback`,
  adminAiFeatures: "/api/v1/admin/ai/features",
  adminAiFeature: (key: string) => `/api/v1/admin/ai/features/${key}`,
  adminAiModels: "/api/v1/admin/ai/models",
  adminAiLabels: "/api/v1/admin/ai/labels",
  adminAiLabelCatalog: "/api/v1/admin/ai/labels/catalog",
  adminAiSkillTagRequests: "/api/v1/admin/ai/skill-tags/requests",
  adminAiLabelReview: (id: string) => `/api/v1/admin/ai/labels/${id}`,
  adminAiSetLabelReview: (id: string) => `/api/v1/admin/ai/set-labels/${id}`,
  adminDictationStoryReorder: (id: string) => `/api/v1/admin/dictation/stories/${id}/reorder`,
} as const;
