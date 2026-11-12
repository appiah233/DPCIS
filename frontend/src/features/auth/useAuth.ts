import { createContext, useContext } from "react";

import type { AuthMeResponse } from "@/lib/api";
import type { AuthUser } from "@/lib/auth";

export interface AuthContextValue {
  isConfigured: boolean;
  isLoading: boolean;
  sessionUser: AuthUser | null;
  identity: AuthMeResponse | null;
  errorMessage: string | null;
  refreshAuth: () => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useOptionalAuth(): AuthContextValue | null {
  return useContext(AuthContext);
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}
