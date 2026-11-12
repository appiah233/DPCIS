import { useCallback, useEffect, useRef, useState } from "react";

import { ApiClientError, fetchHealth } from "@/lib/api";
import type { HealthCheckState } from "@/types/foundation";

export function useHealthCheck(): {
  state: HealthCheckState;
  refresh: () => void;
} {
  const [state, setState] = useState<HealthCheckState>({ kind: "checking" });
  const abortRef = useRef<AbortController | null>(null);

  const runCheck = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ kind: "checking" });

    try {
      const result = await fetchHealth({ signal: controller.signal });
      if (controller.signal.aborted) {
        return;
      }
      const checkedAt = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      if (result.status === "healthy") {
        setState({ kind: "healthy", checkedAt });
      } else {
        setState({
          kind: "unreachable",
          errorMessage: `Unexpected service status: ${result.status}`,
          checkedAt,
        });
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      const checkedAt = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      const errorMessage =
        error instanceof ApiClientError
          ? error.message
          : "Unable to verify backend connectivity.";
      setState({ kind: "unreachable", errorMessage, checkedAt });
    }
  }, []);

  useEffect(() => {
    void runCheck();
    return () => {
      abortRef.current?.abort();
    };
  }, [runCheck]);

  return { state, refresh: runCheck };
}
