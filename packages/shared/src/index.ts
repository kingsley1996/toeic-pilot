// Request/response shapes are DERIVED, not hand-written: they come from FastAPI's
// own OpenAPI schema via scripts/generate-api-types.sh. Editing them here would
// reintroduce the silent contract drift documented in planning/REVIEW-OPUS.md P1-4.
import type { components } from "./api-types";

export type TokenResponse = components["schemas"]["TokenResponse"];
export type UserPublic = components["schemas"]["UserPublic"];
export type UserRegister = components["schemas"]["UserRegister"];
export type UserLogin = components["schemas"]["UserLogin"];
export type HTTPValidationError = components["schemas"]["HTTPValidationError"];

// Escape hatch for callers that need a shape not aliased above.
export type { components, paths } from "./api-types";

export const API_ROUTES = {
  health: "/health",
  ready: "/ready",
  register: "/api/v1/auth/register",
  login: "/api/v1/auth/login",
  me: "/api/v1/auth/me",
} as const;
