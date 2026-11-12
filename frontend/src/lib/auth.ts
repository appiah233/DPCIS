import { createInternalNeonAuth } from "@neondatabase/auth";

const authUrl = (import.meta.env.VITE_NEON_AUTH_URL as string | undefined)?.trim() ?? "";

const neonAuth = authUrl ? createInternalNeonAuth(authUrl) : null;
export const neonAuthClient = neonAuth?.adapter ?? null;
export const isNeonAuthConfigured = neonAuthClient !== null;

export interface AuthUser {
  id: string;
  name?: string | null;
  email?: string | null;
}

const AUTH_UNAVAILABLE_MESSAGE = "Authentication is currently unavailable.";

function resolveSafeCallbackUrl(callbackURL?: string): string {
  const fallbackUrl = `${window.location.origin}/`;
  if (!callbackURL) {
    return fallbackUrl;
  }
  try {
    const parsed = new URL(callbackURL, window.location.origin);
    return parsed.origin === window.location.origin ? parsed.toString() : fallbackUrl;
  } catch {
    return fallbackUrl;
  }
}

export async function signUpWithEmail(email: string, password: string, name: string) {
  if (!neonAuthClient) {
    throw new Error(AUTH_UNAVAILABLE_MESSAGE);
  }
  return neonAuthClient.signUp.email({ email, password, name });
}

export async function signInWithEmail(email: string, password: string) {
  if (!neonAuthClient) {
    throw new Error(AUTH_UNAVAILABLE_MESSAGE);
  }
  return neonAuthClient.signIn.email({ email, password });
}

export async function signInWithGoogle(callbackURL?: string) {
  if (!neonAuthClient) {
    throw new Error(AUTH_UNAVAILABLE_MESSAGE);
  }
  return neonAuthClient.signIn.social({
    provider: "google",
    callbackURL: resolveSafeCallbackUrl(callbackURL),
  });
}

export async function signOutNeonAuth(): Promise<void> {
  if (!neonAuthClient) {
    return;
  }
  await neonAuthClient.signOut();
}

function extractValidJwt(candidate: unknown): string | null {
  if (typeof candidate !== "string") {
    return null;
  }
  const trimmed = candidate.trim();
  if (!trimmed || /\s/.test(trimmed)) {
    return null;
  }
  const segments = trimmed.split(".");
  if (segments.length !== 3 || segments.some((segment) => segment.length === 0)) {
    return null;
  }
  return trimmed;
}

function extractTokenFromResultData(data: unknown): string | null {
  if (!data || typeof data !== "object") {
    return null;
  }
  const record = data as {
    token?: unknown;
    session?: { token?: unknown } | null;
  };
  return (
    extractValidJwt(record.token) ??
    extractValidJwt(record.session?.token)
  );
}

/**
 * Retrieve the signed Better Auth JWT for backend API Bearer authentication.
 *
 * `@neondatabase/auth@0.6.x` routes both `/get-session` and `/token` through
 * its `"getSession"` cache hook, so `neonAuthClient.token()` may return a cached
 * `{ session: { token }, user }` payload instead of `{ token }`. Prefer
 * `neonAuth.getJWTToken()`, fall back to `neonAuthClient.token()` checking both
 * runtime shapes, and require a 3-segment JWT so opaque session tokens are
 * never sent as Bearer JWTs.
 */
export async function getNeonAuthToken(): Promise<string | null> {
  if (!neonAuth || !neonAuthClient) {
    return null;
  }

  try {
    const jwtFromSession = extractValidJwt(await neonAuth.getJWTToken());
    if (jwtFromSession) {
      return jwtFromSession;
    }
  } catch {
    // Fall back to the adapter token endpoint if session lookup fails.
  }

  const result = await neonAuthClient.token();
  return extractTokenFromResultData(result.data);
}

export async function getCurrentAuthUser(): Promise<AuthUser | null> {
  if (!neonAuthClient) {
    return null;
  }

  const result = await neonAuthClient.getSession();
  const user = result.data?.user;
  return user ? { id: user.id, name: user.name, email: user.email } : null;
}
