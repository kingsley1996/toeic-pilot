export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type UserPublic = {
  id: string;
  email: string;
  created_at: string;
};

export type UserRegister = {
  email: string;
  password: string;
};

export type UserLogin = {
  email: string;
  password: string;
};

export const API_ROUTES = {
  health: "/health",
  register: "/api/v1/auth/register",
  login: "/api/v1/auth/login",
  me: "/api/v1/auth/me",
} as const;
