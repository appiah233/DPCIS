import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import { AuthContext } from "@/features/auth/useAuth";
import type { AuthContextValue } from "@/features/auth/useAuth";
import { ApiClientError, fetchAuthMe } from "@/lib/api";
import type { AuthMeResponse } from "@/lib/api";
import {
  getCurrentAuthUser,
  isNeonAuthConfigured,
  signOutNeonAuth,
} from "@/lib/auth";
import type { AuthUser } from "@/lib/auth";

export type { AuthContextValue };

function resolveAuthErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.status === 401) {
      return "Your session has expired. Please sign in again.";
    }
    if (error.status === 503 || (error.status !== undefined && error.status >= 500)) {
      return "Examination Hub is temporarily unavailable. Please try again shortly.";
    }
  }
  return "We could not verify your account right now. Please try again.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(isNeonAuthConfigured);
  const [sessionUser, setSessionUser] = useState<AuthUser | null>(null);
  const [identity, setIdentity] = useState<AuthMeResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const requestSeqRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const refreshAuth = useCallback(async () => {
    if (!isNeonAuthConfigured) {
      setSessionUser(null);
      setIdentity(null);
      setErrorMessage(null);
      setIsLoading(false);
      return;
    }

    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const requestSeq = ++requestSeqRef.current;

    setIsLoading(true);
    setIdentity(null);
    setErrorMessage(null);

    try {
      const currentUser = await getCurrentAuthUser();
      if (requestSeq !== requestSeqRef.current || controller.signal.aborted) {
        return;
      }

      if (!currentUser) {
        setSessionUser(null);
        setIdentity(null);
        return;
      }

      setSessionUser(currentUser);
      const me = await fetchAuthMe({ signal: controller.signal });
      if (requestSeq !== requestSeqRef.current || controller.signal.aborted) {
        return;
      }

      setIdentity(me);
      setErrorMessage(null);
    } catch (error) {
      if (requestSeq !== requestSeqRef.current || controller.signal.aborted) {
        return;
      }
      if (import.meta.env.DEV) {
        console.warn("Authentication verification failed:", error);
      }
      setIdentity(null);
      if (error instanceof ApiClientError && error.status === 401) {
        void signOutNeonAuth().catch(() => undefined);
        setSessionUser(null);
      }
      setErrorMessage(resolveAuthErrorMessage(error));
    } finally {
      if (requestSeq === requestSeqRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!isNeonAuthConfigured) {
      return;
    }

    void refreshAuth();

    return () => {
      requestSeqRef.current += 1;
      abortControllerRef.current?.abort();
    };
  }, [refreshAuth]);

  const signOut = useCallback(async () => {
    requestSeqRef.current += 1;
    abortControllerRef.current?.abort();

    try {
      await signOutNeonAuth();
    } finally {
      setSessionUser(null);
      setIdentity(null);
      setErrorMessage(null);
      setIsLoading(false);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      isConfigured: isNeonAuthConfigured,
      isLoading,
      sessionUser,
      identity,
      errorMessage,
      refreshAuth,
      signOut,
    }),
    [isLoading, sessionUser, identity, errorMessage, refreshAuth, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
