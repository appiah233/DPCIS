import { AlertTriangle, RotateCcw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface ErrorBoundaryProps {
  children: ReactNode;
  resetKeys?: readonly unknown[];
  fallbackTitle?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

function keysChanged(
  prevKeys: readonly unknown[] | undefined,
  nextKeys: readonly unknown[] | undefined,
): boolean {
  if (!prevKeys || !nextKeys) {
    return prevKeys !== nextKeys;
  }
  if (prevKeys.length !== nextKeys.length) {
    return true;
  }
  return prevKeys.some((item, index) => !Object.is(item, nextKeys[index]));
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ErrorBoundary caught rendering error:", error, info.componentStack);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps): void {
    if (this.state.hasError && keysChanged(prevProps.resetKeys, this.props.resetKeys)) {
      this.setState({ hasError: false });
    }
  }

  private handleReset = () => {
    this.setState({ hasError: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Alert variant="destructive" role="alert" className="my-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div className="space-y-3">
              <div>
                <AlertTitle>
                  {this.props.fallbackTitle ?? "Something unexpected interrupted this view"}
                </AlertTitle>
                <AlertDescription>
                  No local data was lost. You can reload this section or return to another route.
                </AlertDescription>
              </div>
              <Button variant="outline" size="sm" onClick={this.handleReset}>
                <RotateCcw className="size-4" aria-hidden="true" />
                Retry view
              </Button>
            </div>
          </div>
        </Alert>
      );
    }

    return this.props.children;
  }
}
