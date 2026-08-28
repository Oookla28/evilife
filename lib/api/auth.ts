import { apiClient } from "./client";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  subject_id: string;
}

export interface AccountSummary {
  user: AuthUser;
  total_accounts: number;
  registered_at: string | null;
  last_login_at: string | null;
}

export interface RegisterInput {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export const getCurrentUser = () => apiClient<AuthUser>("/api/v1/auth/me");
export const getAccountSummary = () => apiClient<AccountSummary>("/api/v1/account/summary");

export const login = (input: LoginInput) =>
  apiClient<AuthUser>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

export const register = (input: RegisterInput) =>
  apiClient<AuthUser>("/api/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

export const logout = () =>
  apiClient<void>("/api/v1/auth/logout", { method: "POST" });
