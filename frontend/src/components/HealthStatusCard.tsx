import { AlertTriangle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHealthCheck } from "@/hooks/useHealthCheck";

export function HealthStatusCard() {
  const { state, refresh } = useHealthCheck();
  const isChecking = state.kind === "checking";

  const handleRefresh = () => {
    if (isChecking) {
      return;
    }
    refresh();
  };

  return (
    <Card className="min-h-56">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <CardTitle as="h2">Backend API Health</CardTitle>
          <CardDescription>
            Live status probe against FastAPI <code>GET /health</code>.
          </CardDescription>
        </div>

        {state.kind === "checking" ? (
          <Badge variant="secondary">
            <Loader2
              className="size-3.5 animate-spin motion-reduce:animate-none"
              aria-hidden="true"
            />
            <span>Checking</span>
          </Badge>
        ) : state.kind === "healthy" ? (
          <Badge variant="success">
            <CheckCircle2 className="size-3.5" aria-hidden="true" />
            <span>Healthy</span>
          </Badge>
        ) : (
          <Badge variant="destructive">
            <AlertTriangle className="size-3.5" aria-hidden="true" />
            <span>Unreachable</span>
          </Badge>
        )}
      </CardHeader>

      <CardContent className="space-y-3">
        <p className="visually-hidden" aria-live="polite" aria-atomic="true">
          {state.kind === "checking"
            ? "Checking backend API status."
            : state.kind === "healthy"
              ? "Backend API service is healthy."
              : "Backend API service is currently unreachable."}
        </p>

        {state.kind === "checking" ? (
          <div className="space-y-2.5 pt-1">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : null}

        {state.kind === "healthy" ? (
          <Alert variant="success" role="status">
            <AlertTitle>Service connected</AlertTitle>
            <AlertDescription>
              The FastAPI backend responded with HTTP 200 and an explicit minimal health status.
              Last checked at <span className="tabular-nums">{state.checkedAt}</span>.
            </AlertDescription>
          </Alert>
        ) : null}

        {state.kind === "unreachable" ? (
          <Alert variant="warning" role="status">
            <AlertTitle>Backend service not reachable</AlertTitle>
            <AlertDescription className="space-y-2">
              <p>
                The frontend renders independently. Start the FastAPI server to verify live
                connectivity.
              </p>
              <details className="text-xs text-foreground">
                <summary className="inline-flex min-h-11 cursor-pointer items-center py-2 font-medium">
                  Connection details
                </summary>
                <p className="mt-1 break-words">
                  {state.errorMessage} (checked at{" "}
                  <span className="tabular-nums">{state.checkedAt}</span>)
                </p>
              </details>
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>

      <CardFooter className="justify-between">
        <span className="text-xs text-muted-foreground">Shallow liveness probe only</span>
        <Button
          variant="outline"
          size="default"
          aria-disabled={isChecking}
          onClick={handleRefresh}
        >
          <RefreshCw
            className={
              isChecking
                ? "size-4 animate-spin motion-reduce:animate-none"
                : "size-4"
            }
            aria-hidden="true"
          />
          <span>{isChecking ? "Checking..." : "Check again"}</span>
        </Button>
      </CardFooter>
    </Card>
  );
}
