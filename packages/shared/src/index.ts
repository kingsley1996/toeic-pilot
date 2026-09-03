// Request/response shapes are DERIVED, not hand-written: they come from FastAPI's
// own OpenAPI schema via scripts/generate-api-types.sh. Editing them here would
// reintroduce the silent contract drift documented in planning/docs/REVIEW-OPUS.md P1-4.
import type { components } from "./api-types";

export type TokenResponse = components["schemas"]["TokenResponse"];
export type AuthProviderPublic = components["schemas"]["AuthProviderPublic"];
export type UserPublic = components["schemas"]["UserPublic"];
export type UserRegister = components["schemas"]["UserRegister"];
export type UserLogin = components["schemas"]["UserLogin"];
export type HTTPValidationError = components["schemas"]["HTTPValidationError"];

// Learning Hub
export type TopicSession = components["schemas"]["TopicSession"];
export type TopicSessionSubmit = components["schemas"]["TopicSessionSubmit"];
export type TopicSessionSummary = components["schemas"]["TopicSessionSummary"];
export type TopicPublic = components["schemas"]["TopicPublic"];
export type VocabularyCollectionPublic = components["schemas"]["VocabularyCollectionPublic"];
export type VocabularyCollectionItemPublic =
  components["schemas"]["VocabularyCollectionItemPublic"];
export type VocabularyCollectionDetail = components["schemas"]["VocabularyCollectionDetail"];
export type VocabularyItemDetail = components["schemas"]["VocabularyItemDetail"];
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
export type VocabularyTopicProgress = components["schemas"]["VocabularyTopicProgress"];
export type VocabularyMastery = components["schemas"]["VocabularyMastery"];
export type ReviewCard = components["schemas"]["ReviewCard"];
export type ReviewSession = components["schemas"]["ReviewSession"];
export type ReviewResult = components["schemas"]["ReviewResult"];
export type RecallResult = components["schemas"]["RecallResult"];
export type RecallCheck = components["schemas"]["RecallCheck"];
export type BackdropPublic = components["schemas"]["BackdropPublic"];
export type BackdropUpdate = components["schemas"]["BackdropUpdate"];
export type UserProfilePublic = components["schemas"]["UserProfilePublic"];
export type ProgressionPublic = components["schemas"]["ProgressionPublic"];
export type PetPublic = components["schemas"]["PetPublic"];
export type PetMove = components["schemas"]["PetMove"];
export type PetSpeciesPublic = components["schemas"]["PetSpeciesPublic"];
export type DailyTasksPublic = components["schemas"]["DailyTasksPublic"];
export type BadgesPublic = components["schemas"]["BadgesPublic"];
export type BadgePublic = components["schemas"]["BadgePublic"];
export type FramePublic = components["schemas"]["FramePublic"];
export type ProgressionConfigAdmin = components["schemas"]["ProgressionConfigAdmin"];
export type ProgressionSettingUpdate = components["schemas"]["ProgressionSettingUpdate"];
export type DailyTaskSlotAdmin = components["schemas"]["DailyTaskSlotAdmin"];
export type DailyTaskSlotCreate = components["schemas"]["DailyTaskSlotCreate"];
export type LevelTierAdmin = components["schemas"]["LevelTierAdmin"];
export type FrameTierAdmin = components["schemas"]["FrameTierAdmin"];
export type FrameTierCreate = components["schemas"]["FrameTierCreate"];
export type BadgeRuleAdmin = components["schemas"]["BadgeRuleAdmin"];
export type BadgeRuleCreate = components["schemas"]["BadgeRuleCreate"];
export type DailyTaskPublic = components["schemas"]["DailyTaskPublic"];
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
export type SkillScore = components["schemas"]["SkillScore"];
export type AttemptSummary = components["schemas"]["AttemptSummary"];
/**
 * Một trang kết quả. Chỉ endpoint nào PHÌNH được mới bọc phong bì này — danh
 * sách có trần trong miền nghiệp vụ (giọng đọc, câu của một đề) vẫn trả mảng
 * trần. Xem `app/schemas/common.py` để biết quy tắc phân nhóm.
 */
export type ChatMessagePublic = components["schemas"]["ChatMessagePublic"];
export type ChatTurn = components["schemas"]["ChatTurn"];
export type ChatHistoryPage = components["schemas"]["Page_ChatMessagePublic_"];
export type AttemptPage = components["schemas"]["Page_AttemptSummary_"];
export type VocabularyPage = components["schemas"]["Page_VocabularySummary_"];
export type ReviewDueCount = components["schemas"]["ReviewDueCount"];
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
export type BulkPublishResult = components["schemas"]["BulkPublishResult"];
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
export type VocabularyCollectionAdmin = components["schemas"]["VocabularyCollectionAdmin"];
export type VocabularyCollectionItemAdmin = components["schemas"]["VocabularyCollectionItemAdmin"];
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
export type ProviderDetail = components["schemas"]["ProviderDetail"];
export type ProviderModelDetail = components["schemas"]["ProviderModelDetail"];
export type ModelTaskRow = components["schemas"]["ModelTaskRow"];
export type TestConnectionResult = components["schemas"]["TestConnectionResult"];
export type LabelValue = components["schemas"]["LabelValue"];
export type RubyWallet = components["schemas"]["RubyWallet"];
export type RubyEntry = components["schemas"]["RubyEntryPublic"];
export type RubyGift = components["schemas"]["RubyGiftPublic"];
export type RubyClaimResult = components["schemas"]["RubyClaimResult"];
export type RubyRulePublic = components["schemas"]["RubyRulePublic"];
export type SystemStatus = components["schemas"]["SystemStatus"];
export type UptimeReport = components["schemas"]["UptimeReport"];
export type ServiceUptime = components["schemas"]["ServiceUptime"];
export type UptimeBucket = components["schemas"]["UptimeBucket"];
export type PetlandMapPublic = components["schemas"]["PetlandMapPublic"];
export type PetlandMapBody = components["schemas"]["PetlandMapBody"];
export type DependencyStatus = components["schemas"]["DependencyStatus"];
export type MediaChannel = components["schemas"]["MediaChannel"];
export type EggPublic = components["schemas"]["EggPublic"];
export type EggResult = components["schemas"]["EggResult"];
export type EggBatchResult = components["schemas"]["EggBatchResult"];
export type EggChance = components["schemas"]["EggChance"];
export type EggSettingPublic = components["schemas"]["EggSettingPublic"];
export type PetOwnedPublic = components["schemas"]["PetOwnedPublic"];
export type EncounterPublic = components["schemas"]["EncounterPublic"];
export type EncounterHint = components["schemas"]["EncounterHint"];
export type EncounterResult = components["schemas"]["EncounterResult"];
export type EncounterTask = components["schemas"]["EncounterTask"];
export type EncounterSettingPublic = components["schemas"]["EncounterSettingPublic"];

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
  // Đăng nhập bằng nhà cung cấp bên ngoài. `authStart` KHÔNG gọi bằng `fetch`:
  // nó là một lần chuyển hướng cả trang, vì luồng phải đi qua màn hình của
  // Google/Apple rồi quay lại. Gọi bằng fetch sẽ nhận về HTML của Google và
  // không có gì hiển thị được.
  authProviders: "/api/v1/auth/providers",
  authStart: (provider: string, next: string) =>
    `/api/v1/auth/${provider}/start?next=${encodeURIComponent(next)}`,

  profile: "/api/v1/profile",
  profileStats: "/api/v1/profile/stats",
  progression: "/api/v1/profile/progression",
  dailyTasks: "/api/v1/daily-tasks",
  badges: "/api/v1/progression/badges",
  pet: "/api/v1/pet",
  petPosition: "/api/v1/pet/position",
  petActions: "/api/v1/pet/actions",
  // Gacha. Quay ở MÁY CHỦ: `open` không nhận tham số nào, vì một endpoint nhận
  // `tier` từ client là một endpoint nhận giá từ client (ADR-010 §6.1).
  petEggs: "/api/v1/pet/eggs",
  petEggOpen: "/api/v1/pet/eggs/open",
  // Đường riêng chứ không phải `?count=10` trên đường trên: hai lượt mở trả về
  // hai hình dạng khác nhau (một quả và một danh sách), và một endpoint đổi hình
  // dạng theo tham số là thứ frontend phải đoán.
  petEggOpenTen: "/api/v1/pet/eggs/open-ten",
  petCollection: "/api/v1/pet/collection",
  // Lần đọc này CÓ GHI: nó là chỗ một cuộc chạm mặt được sinh ra, và sinh lúc
  // đọc là thứ bảo đảm không ai bỏ lỡ được cuộc nào sinh ra trong lúc họ ngủ
  // (ADR-012 §1). Cùng hình dạng với `GET /daily-tasks`.
  petEncounters: "/api/v1/pet/encounters",
  petEncounterAnswer: (id: string) => `/api/v1/pet/encounters/${id}/answer`,
  petEncounterHint: (id: string) => `/api/v1/pet/encounters/${id}/hint`,
  // Đổi con đang nuôi. `PATCH /pet` chứ không phải một đường riêng: nó sửa một
  // trường của chính con thú, và nó trả về nguyên trạng thái mới như mọi đường
  // ghi khác ở góc này.
  petSwitch: "/api/v1/pet",
  adminPetEggs: "/api/v1/admin/pet/eggs",
  adminPetEncounters: "/api/v1/admin/pet/encounters",
  adminPetEncounterSpawn: "/api/v1/admin/pet/encounters/spawn",

  // Ví ruby. Không nằm dưới `/pet`: ruby kiếm ở chỗ HỌC và tiêu ở chỗ CHƠI, nên
  // đặt nó dưới góc thú cưng sẽ dựng đúng cái liên tưởng ADR-011 §3 cấm — rằng
  // con thú cần ruby để sống.
  ruby: "/api/v1/ruby",
  rubyGift: "/api/v1/ruby/gift",
  petlandMap: "/api/v1/petland/map",
  adminPetlandMap: "/api/v1/admin/petland/map",
  adminSystemStatus: "/api/v1/admin/system/status",
  adminSystemUptime: "/api/v1/admin/system/uptime",
  adminRubyRules: "/api/v1/admin/ruby/rules",
  adminRubyRule: (sourceType: string) => `/api/v1/admin/ruby/rules/${sourceType}`,
  adminPetSpecies: "/api/v1/admin/pet/species",
  adminPetSpeciesItem: (code: string) => `/api/v1/admin/pet/species/${code}`,
  badgesSeen: "/api/v1/progression/badges/seen",

  // Cấu hình hệ level. Mọi đường ghi ở đây trả về TOÀN BỘ cấu hình, nên màn hình
  // quản trị không bao giờ phải tự đoán trạng thái sau khi sửa — nó thay cả khối
  // bằng thứ máy chủ vừa trả về. Bốn phần chỉ có nghĩa khi đứng cạnh nhau (một
  // bậc khung ở level 30 là vô nghĩa nếu bảng level dừng ở 25).
  adminProgression: "/api/v1/admin/progression",
  adminProgressionSetting: "/api/v1/admin/progression/setting",
  adminProgressionLevels: "/api/v1/admin/progression/levels",
  adminProgressionLevelsGenerate: "/api/v1/admin/progression/levels/generate",
  adminProgressionSlots: "/api/v1/admin/progression/slots",
  adminProgressionSlot: (id: string) => `/api/v1/admin/progression/slots/${id}`,
  // Vé tải tranh khung/huy hiệu. Không có bước `confirm` riêng: bước đó chính là
  // lệnh PATCH gắn khoá vào hàng, và nó kiểm tiền tố + hỏi lại nhà cung cấp.
  adminProgressionAssetTicket: "/api/v1/admin/progression/assets/ticket",
  adminProgressionFrames: "/api/v1/admin/progression/frames",
  adminProgressionFrame: (code: string) => `/api/v1/admin/progression/frames/${code}`,
  adminProgressionBadges: "/api/v1/admin/progression/badges",
  adminProgressionBadge: (code: string) => `/api/v1/admin/progression/badges/${code}`,
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
  reviewDueCount: "/api/v1/vocabulary-review/due-count",
  // Gạch nối, không phải `/vocabulary/progress`: route `/vocabulary/{entry_id}`
  // sẽ bắt "progress" trước rồi 422 khi parse nó thành UUID.
  vocabularyProgress: "/api/v1/vocabulary-progress",
  vocabularyTopicProgress: "/api/v1/vocabulary-topic-progress",
  submitReview: (id: string) => `/api/v1/vocabulary/${id}/review`,
  submitRecall: (id: string) => `/api/v1/vocabulary/${id}/recall`,
  // Chỉ chấm chính tả, không ghi điểm: luồng học tự chấm năm nút dùng.
  recallCheck: (id: string) => `/api/v1/vocabulary/${id}/recall-check`,
  // Bàn cờ học tới đâu của một chủ đề, lưu TRÊN SERVER theo (user, topic).
  vocabularyTopicSession: (topicId: string) => `/api/v1/vocabulary-topic-sessions/${topicId}`,
  // Danh sách ván học của chính học viên, mới động vào trước. Mảng trần: số ván
  // không vượt quá số chủ đề đã xuất bản (nhóm A của `schemas/common.py`).
  vocabularyTopicSessions: "/api/v1/vocabulary-topic-sessions",

  // Nền lưới động: đường ĐỌC công khai (khách xem trang giới thiệu cũng thấy
  // nền này), đường GHI nằm dưới /admin.
  backdrop: "/api/v1/backdrop",
  adminBackdrop: "/api/v1/admin/backdrop",

  // Cây từ vựng: collection -> collection_item -> topic. Gạch nối, không lồng vào
  // `/vocabulary/...` (cùng luật với `dictation-topics` bên dưới).
  vocabularyCollections: "/api/v1/vocabulary-collections",
  vocabularyCollection: (id: string) => `/api/v1/vocabulary-collections/${id}`,
  vocabularyCollectionItem: (id: string) => `/api/v1/vocabulary-collection-items/${id}`,
  dictation: "/api/v1/dictation",
  dictationDetail: (id: string) => `/api/v1/dictation/${id}`,
  // Gạch nối, không phải `/dictation/random`: route động `/dictation/{item_id}`
  // khai kiểu UUID nên nó bắt mất "random" và trả 422. Cùng luật với
  // `dictation-topics` bên dưới.
  dictationRandom: "/api/v1/dictation-random",
  submitDictation: (id: string) => `/api/v1/dictation/${id}/attempts`,

  // Cây dictation. Gạch nối chứ không lồng vào `/dictation/...`: đường dẫn động
  // `/dictation/{item_id}` khai kiểu UUID và sẽ bắt mất `/dictation/topics`.
  dictationTopics: "/api/v1/dictation-topics",
  dictationTopic: (id: string) => `/api/v1/dictation-topics/${id}`,
  dictationSection: (id: string) => `/api/v1/dictation-sections/${id}`,
  dictationStory: (id: string) => `/api/v1/dictation-stories/${id}`,

  // Content admin
  adminTopics: "/api/v1/admin/topics",
  adminTopic: (id: string) => `/api/v1/admin/topics/${id}`,
  adminVocabularyCollections: "/api/v1/admin/vocabulary-collections",
  adminVocabularyCollection: (id: string) => `/api/v1/admin/vocabulary-collections/${id}`,
  adminVocabularyCollectionPublish: (id: string) =>
    `/api/v1/admin/vocabulary-collections/${id}/publish`,
  adminVocabularyCollectionItems: "/api/v1/admin/vocabulary-collection-items",
  adminVocabularyCollectionItem: (id: string) => `/api/v1/admin/vocabulary-collection-items/${id}`,
  adminVocabularyCollectionItemPublish: (id: string) =>
    `/api/v1/admin/vocabulary-collection-items/${id}/publish`,
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
  adminTestPublishAllQuestions: (slug: string) => `/api/v1/admin/tests/${slug}/questions/publish`,
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
  // Trợ lý trang web — một cuộc hội thoại cuốn theo mỗi người, không neo vào
  // lượt làm bài; ngữ cảnh là hướng dẫn trang cộng số liệu thật của người hỏi.
  assistantChat: "/api/v1/assistant/chat",
  adminAiFeatures: "/api/v1/admin/ai/features",
  adminAiFeature: (key: string) => `/api/v1/admin/ai/features/${key}`,
  adminAiModels: "/api/v1/admin/ai/models",
  adminAiProviders: "/api/v1/admin/ai/providers",
  adminAiStatsModels: "/api/v1/admin/ai/stats/models",
  adminAiTestConnection: "/api/v1/admin/ai/test-connection",
  adminAiLabels: "/api/v1/admin/ai/labels",
  adminAiLabelCatalog: "/api/v1/admin/ai/labels/catalog",
  adminAiSkillTagRequests: "/api/v1/admin/ai/skill-tags/requests",
  adminAiLabelReview: (id: string) => `/api/v1/admin/ai/labels/${id}`,
  adminAiSetLabelReview: (id: string) => `/api/v1/admin/ai/set-labels/${id}`,
  adminDictationStoryReorder: (id: string) => `/api/v1/admin/dictation/stories/${id}/reorder`,
} as const;
