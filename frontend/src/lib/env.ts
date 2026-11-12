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
  const apiBaseUrl = (rawApiBase || "http://localhost:8000").replace(/\/+$/, "");

  const rawNeonAuthUrl =
    (import.meta.env.VITE_NEON_AUTH_URL as string | undefined)?.trim() ?? "";
  const neonAuthUrl = rawNeonAuthUrl || null;

  return {
    apiBaseUrl,
    neonAuthUrl,
    isNeonAuthConfigured: neonAuthUrl !== null,
  };
}
