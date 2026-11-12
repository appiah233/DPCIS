import { getNeonAuthToken } from "@/lib/auth";
import { getPublicEnvConfig } from "@/lib/env";
import type { HealthResponse, RootInfoResponse } from "@/types/foundation";

export type { HealthResponse, RootInfoResponse } from "@/types/foundation";

export type TokenProvider = () => Promise<string | null>;

export interface AuthMeResponse {
  user_id?: string;
  auth_subject: string;
  email: string | null;
  display_name: string | null;
  role: "STUDENT" | "ADMIN";
}

export class ApiClientError extends Error {
  readonly status?: number;
  readonly detail?: unknown;
  readonly code?: string;
  readonly payload?: Record<string, unknown>;

  constructor(
    message: string,
    status?: number,
    detail?: unknown,
    code?: string,
    payload?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.detail = detail;
    this.code = code;
    this.payload = payload;
  }
}

export interface ApiRequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  getToken?: TokenProvider;
  token?: string | null;
  auth?: boolean;
  body?: unknown;
  headers?: HeadersInit;
}

const DEFAULT_TIMEOUT_MS = 10000;
const HEALTH_TIMEOUT_MS = 5000;

function extractFastApiErrorMessage(detail: unknown): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") {
          return item.trim();
        }
        if (item && typeof item === "object") {
          const record = item as { loc?: unknown; msg?: unknown };
          const msg = typeof record.msg === "string" ? record.msg.trim() : "";
          const loc = Array.isArray(record.loc)
            ? record.loc
                .filter((part) => part !== "body")
                .map((part) => String(part))
                .join(".")
            : "";
          if (msg && loc) {
            return `${loc}: ${msg}`;
          }
          if (msg) {
            return msg;
          }
        }
        return "";
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  if (detail && typeof detail === "object") {
    const record = detail as { message?: unknown; detail?: unknown };
    if (typeof record.message === "string" && record.message.trim()) {
      return record.message.trim();
    }
    if (typeof record.detail === "string" && record.detail.trim()) {
      return record.detail.trim();
    }
  }

  return "We could not complete your request right now.";
}

function tryParseJson(rawText: string): unknown {
  if (!rawText.trim()) {
    return undefined;
  }
  try {
    return JSON.parse(rawText) as unknown;
  } catch {
    return undefined;
  }
}

async function requestJson<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { apiBaseUrl } = getPublicEnvConfig();
  const url = `${apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  const onExternalAbort = () => controller.abort();
  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort();
    } else {
      options.signal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }

  try {
    const headers = new Headers(options.headers);
    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }

    let resolvedToken: string | null = null;
    if (options.token !== undefined) {
      resolvedToken = options.token;
    } else if (options.getToken) {
      resolvedToken = await options.getToken();
    } else if (options.auth !== false) {
      resolvedToken = await getNeonAuthToken();
    }

    if (resolvedToken) {
      headers.set("Authorization", `Bearer ${resolvedToken}`);
    }

    let requestBody: BodyInit | undefined;
    if (options.body !== undefined) {
      if (
        options.body instanceof FormData ||
        options.body instanceof URLSearchParams ||
        options.body instanceof Blob ||
        typeof options.body === "string"
      ) {
        requestBody = options.body;
      } else {
        if (!headers.has("Content-Type")) {
          headers.set("Content-Type", "application/json");
        }
        requestBody = JSON.stringify(options.body);
      }
    }

    const response = await fetch(url, {
      method,
      headers,
      body: requestBody,
      signal: controller.signal,
    });

    if (!response.ok) {
      const rawErrorText = await response.text().catch(() => "");
      const parsedError = tryParseJson(rawErrorText);
      const payload =
        parsedError !== null &&
        typeof parsedError === "object" &&
        !Array.isArray(parsedError)
          ? (parsedError as Record<string, unknown>)
          : undefined;
      const code =
        payload && typeof payload.code === "string" ? payload.code : undefined;
      const detail =
        payload && "detail" in payload ? payload.detail : parsedError;
      const errorMessage = extractFastApiErrorMessage(detail);
      throw new ApiClientError(
        errorMessage,
        response.status,
        detail,
        code,
        payload,
      );
    }

    if (response.status === 204 || response.status === 205) {
      return undefined as T;
    }

    const rawText = await response.text();
    if (!rawText.trim()) {
      return undefined as T;
    }

    return JSON.parse(rawText) as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiClientError("Request timed out or was cancelled.");
    }
    throw new ApiClientError("Unable to connect to Examination Hub. Please check your connection and try again.");
  } finally {
    window.clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", onExternalAbort);
  }
}

export function apiGet<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  return requestJson<T>("GET", path, options);
}

export function apiPost<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  return requestJson<T>("POST", path, options);
}

export function apiPut<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  return requestJson<T>("PUT", path, options);
}

export function apiPatch<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  return requestJson<T>("PATCH", path, options);
}

export function apiDelete<T = void>(path: string, options?: ApiRequestOptions): Promise<T> {
  return requestJson<T>("DELETE", path, options);
}

export function fetchHealth(options?: ApiRequestOptions): Promise<HealthResponse> {
  return requestJson<HealthResponse>("GET", "/health", {
    auth: false,
    timeoutMs: HEALTH_TIMEOUT_MS,
    ...options,
  });
}

export function fetchRootInfo(options?: ApiRequestOptions): Promise<RootInfoResponse> {
  return requestJson<RootInfoResponse>("GET", "/", {
    auth: false,
    timeoutMs: HEALTH_TIMEOUT_MS,
    ...options,
  });
}

export function fetchAuthMe(options?: ApiRequestOptions): Promise<AuthMeResponse> {
  return requestJson<AuthMeResponse>("GET", "/auth/me", {
    getToken: getNeonAuthToken,
    ...options,
  });
}

export const fetchApplicationIdentity = fetchAuthMe;
