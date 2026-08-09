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
export type VocabularySummary = components["schemas"]["VocabularySummary"];
export type VocabularyDetail = components["schemas"]["VocabularyDetail"];
export type ReviewCard = components["schemas"]["ReviewCard"];
export type ReviewSession = components["schemas"]["ReviewSession"];
export type ReviewResult = components["schemas"]["ReviewResult"];
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

  // Learning Hub
  topics: "/api/v1/topics",
  vocabulary: "/api/v1/vocabulary",
  vocabularyDetail: (id: string) => `/api/v1/vocabulary/${id}`,
  reviewSession: "/api/v1/vocabulary-review/session",
  submitReview: (id: string) => `/api/v1/vocabulary/${id}/review`,
  dictation: "/api/v1/dictation",
  dictationDetail: (id: string) => `/api/v1/dictation/${id}`,
  submitDictation: (id: string) => `/api/v1/dictation/${id}/attempts`,

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
} as const;
