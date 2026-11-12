export interface HealthResponse {
  status: string;
}

export interface RootInfoResponse {
  name: string;
  version: string;
  environment: string;
  status: string;
}

export type HealthCheckState =
  | { kind: "checking" }
  | { kind: "healthy"; checkedAt: string }
  | { kind: "unreachable"; errorMessage: string; checkedAt: string };
