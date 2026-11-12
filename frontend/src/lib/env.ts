export interface PublicEnvConfig {
  apiBaseUrl: string;
  neonAuthUrl: string | null;
  isNeonAuthConfigured: boolean;
}

/**
 * Read strictly public VITE_* frontend configuration without throwing at import time.
 * Server secrets (DATABASE_URL, NEON_AUTH_JWKS_URL) must never exist in Vite env vars.
 */
export function getPublicEnvConfig(): PublicEnvConfig {
  const rawApiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? "";
  const isLocalOrigin =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "[::1]";
  const apiBaseUrl = (
    rawApiBase || (isLocalOrigin ? "http://127.0.0.1:8000" : "/api")
  ).replace(/\/+$/, "");

  const rawNeonAuthUrl =
    (import.meta.env.VITE_NEON_AUTH_URL as string | undefined)?.trim() ?? "";
  const neonAuthUrl = rawNeonAuthUrl || null;

  return {
    apiBaseUrl,
    neonAuthUrl,
    isNeonAuthConfigured: neonAuthUrl !== null,
  };
}
