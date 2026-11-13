import { Eye, EyeOff, LogIn, LogOut, RotateCcw, UserPlus } from "lucide-react";
import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOptionalAuth } from "@/features/auth/useAuth";
import {
  getCurrentAuthUser,
  isNeonAuthConfigured,
  signInWithEmail,
  signInWithGoogle,
  signOutNeonAuth,
  signUpWithEmail,
} from "@/lib/auth";
import type { AuthUser } from "@/lib/auth";

export interface AuthBoundaryProps {
  onAuthSuccess?: () => void | Promise<void>;
}

function extractRawErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object" && "message" in error) {
    const maybeMessage = (error as { message?: unknown }).message;
    if (typeof maybeMessage === "string") {
      return maybeMessage;
    }
  }
  return "";
}

function sanitizeAuthError(error: unknown, fallback: string): string {
  if (import.meta.env.DEV) {
    console.warn("Authentication request failed:", error);
  }

  const raw = extractRawErrorMessage(error);
  if (/invalid.*(email|password|credential)|incorrect.*password|user not found/i.test(raw)) {
    return "Incorrect email address or password.";
  }
  if (/already exists|already registered|duplicate/i.test(raw)) {
    return "An account with this email address already exists.";
  }
  if (/password.*(short|length|least 8|weak)/i.test(raw)) {
    return "Please use a password with at least 8 characters.";
  }
  if (/invalid email/i.test(raw)) {
    return "Please enter a valid email address.";
  }
  if (/too many|rate limit/i.test(raw)) {
    return "Too many sign-in attempts. Please wait a moment and try again.";
  }
  return fallback;
}

export function AuthBoundary({ onAuthSuccess }: AuthBoundaryProps = {}) {
  const sharedAuth = useOptionalAuth();
  const baseId = useId();

  const [localUser, setLocalUser] = useState<AuthUser | null>(null);
  const [localLoading, setLocalLoading] = useState(
    () => sharedAuth === null && isNeonAuthConfigured,
  );
  const [localError, setLocalError] = useState<string | null>(null);

  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isConfigured = sharedAuth ? sharedAuth.isConfigured : isNeonAuthConfigured;

  useEffect(() => {
    if (!isConfigured && import.meta.env.DEV) {
      console.warn("Authentication service is not configured for this environment.");
    }
  }, [isConfigured]);

  useEffect(() => {
    if (sharedAuth !== null || !isNeonAuthConfigured) {
      return;
    }

    let cancelled = false;
    getCurrentAuthUser()
      .then((nextUser) => {
        if (!cancelled) {
          setLocalUser(nextUser);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLocalError(
            sanitizeAuthError(error, "We could not verify your session. Please try again."),
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLocalLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sharedAuth]);

  const user = sharedAuth ? sharedAuth.sessionUser : localUser;
  const isLoading = sharedAuth ? sharedAuth.isLoading : localLoading;
  const displayError = localError ?? sharedAuth?.errorMessage ?? null;

  const handleRetry = () => {
    setLocalError(null);
    if (sharedAuth) {
      void sharedAuth.refreshAuth();
      return;
    }
    window.location.reload();
  };

  const handleGoogleSignIn = async () => {
    if (!isConfigured) {
      return;
    }
    setLocalError(null);
    setIsSubmitting(true);
    try {
      const result = await signInWithGoogle();
      if (result.error) {
        setLocalError(
          sanitizeAuthError(
            result.error,
            "Google sign-in could not be started right now. Please try again.",
          ),
        );
      }
    } catch (error) {
      setLocalError(
        sanitizeAuthError(
          error,
          "Google sign-in could not be started right now. Please try again.",
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignOut = async () => {
    if (!isConfigured) {
      return;
    }
    setLocalError(null);
    setIsSubmitting(true);
    try {
      if (sharedAuth) {
        await sharedAuth.signOut();
      } else {
        await signOutNeonAuth();
        setLocalUser(null);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitEmailAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLocalError(null);
    setIsSubmitting(true);
    const fallbackError =
      mode === "sign-up"
        ? "We could not create your account right now. Please try again."
        : "We could not sign you in right now. Please check your details and try again.";

    try {
      const result =
        mode === "sign-up"
          ? await signUpWithEmail(email.trim(), password, name.trim())
          : await signInWithEmail(email.trim(), password);
      if (result.error) {
        setLocalError(sanitizeAuthError(result.error, fallbackError));
        return;
      }

      setPassword("");
      setShowPassword(false);

      if (sharedAuth) {
        await sharedAuth.refreshAuth();
      } else {
        setLocalUser(await getCurrentAuthUser());
      }

      if (onAuthSuccess && onAuthSuccess !== sharedAuth?.refreshAuth) {
        await onAuthSuccess();
      }
    } catch (error) {
      setLocalError(sanitizeAuthError(error, fallbackError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleMode = () => {
    setLocalError(null);
    setMode((prev) => (prev === "sign-in" ? "sign-up" : "sign-in"));
  };

  const nameInputId = `${baseId}-name`;
  const emailInputId = `${baseId}-email`;
  const passwordInputId = `${baseId}-password`;
  const passwordHelpId = `${baseId}-password-help`;
  const errorAlertId = `${baseId}-error`;

  if (!isConfigured) {
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader className="space-y-1.5">
          <CardTitle as="h2">Examination Hub is temporarily unavailable</CardTitle>
          <CardDescription>
            The authentication service has not been configured for this environment. Please contact
            the system administrator.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button type="button" variant="outline" className="min-h-[44px] w-full" onClick={handleRetry}>
            <RotateCcw className="size-4" aria-hidden="true" />
            <span>Try Again</span>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader className="space-y-1.5">
          <CardTitle as="h2">Sign in to your account</CardTitle>
          <CardDescription>Checking your session...</CardDescription>
        </CardHeader>
        <CardContent>
          <Alert variant="default" role="status" aria-live="polite">
            <AlertTitle>Checking your session</AlertTitle>
            <AlertDescription>Please wait while we verify your account.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (user) {
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader className="space-y-1.5">
          <CardTitle as="h2">Signed in</CardTitle>
          <CardDescription>
            Signed in as {user.email ?? user.name ?? "your account"}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {displayError ? (
            <Alert id={errorAlertId} variant="destructive" role="alert">
              <AlertTitle>Unable to continue</AlertTitle>
              <AlertDescription>{displayError}</AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-col gap-2.5 sm:flex-row">
            {displayError ? (
              <Button
                type="button"
                variant="outline"
                className="min-h-[44px] flex-1"
                disabled={isSubmitting}
                onClick={handleRetry}
              >
                <RotateCcw className="size-4" aria-hidden="true" />
                <span>Try Again</span>
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              className="min-h-[44px] flex-1"
              disabled={isSubmitting}
              onClick={handleSignOut}
            >
              <LogOut className="size-4" aria-hidden="true" />
              <span>Sign out</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const emailDescribedBy = displayError ? errorAlertId : undefined;
  const passwordDescribedBy =
    [mode === "sign-up" ? passwordHelpId : null, displayError ? errorAlertId : null]
      .filter(Boolean)
      .join(" ") || undefined;

  return (
    <Card className="auth-card mx-auto w-full max-w-md">
      <CardHeader className="space-y-3 pb-5">
        <span className="auth-eyebrow inline-flex w-fit items-center gap-2 rounded-full px-3 py-1.5 text-[0.68rem] font-bold tracking-[0.16em] uppercase">
          <span className="auth-eyebrow-dot size-1.5 rounded-full" aria-hidden="true" />
          Secure account access
        </span>
        <CardTitle as="h2" className="text-3xl leading-tight font-semibold tracking-[-0.04em] sm:text-[2.15rem]">
          {mode === "sign-in" ? "Welcome back" : "Join Examination Hub"}
        </CardTitle>
        <CardDescription className="max-w-sm">
          {mode === "sign-in"
            ? "Sign in to continue your examinations."
            : "Create an account to discover your examinations."}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {displayError ? (
          <Alert id={errorAlertId} variant="destructive" role="alert">
            <AlertTitle>Unable to sign in</AlertTitle>
            <AlertDescription>{displayError}</AlertDescription>
          </Alert>
        ) : null}

        <form className="space-y-4" onSubmit={handleSubmitEmailAuth}>
          {mode === "sign-up" ? (
            <div className="field-group space-y-1.5">
              <Label htmlFor={nameInputId}>Full name</Label>
              <Input
                id={nameInputId}
                name="name"
                required
                className="auth-input min-h-[48px]"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                enterKeyHint="next"
                aria-invalid={Boolean(displayError)}
                aria-describedby={emailDescribedBy}
              />
            </div>
          ) : null}

          <div className="field-group space-y-1.5">
            <Label htmlFor={emailInputId}>Email</Label>
            <Input
              id={emailInputId}
              name="email"
              required
              type="email"
              className="auth-input min-h-[48px]"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="none"
              enterKeyHint="next"
              aria-invalid={Boolean(displayError)}
              aria-describedby={emailDescribedBy}
            />
          </div>

          <div className="field-group space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor={passwordInputId}>Password</Label>
              <Button
                type="button"
                variant="ghost"
                size="default"
                className="min-h-[44px] min-w-[44px] px-2.5 text-xs"
                aria-pressed={showPassword}
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword((prev) => !prev)}
              >
                {showPassword ? (
                  <EyeOff className="size-4" aria-hidden="true" />
                ) : (
                  <Eye className="size-4" aria-hidden="true" />
                )}
                <span>{showPassword ? "Hide" : "Show"}</span>
              </Button>
            </div>
            <Input
              id={passwordInputId}
              name="password"
              required
              minLength={8}
              type={showPassword ? "text" : "password"}
              className="auth-input min-h-[48px]"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
              enterKeyHint="done"
              aria-invalid={Boolean(displayError)}
              aria-describedby={passwordDescribedBy}
            />
            {mode === "sign-up" ? (
              <p id={passwordHelpId} className="text-xs text-muted-foreground">
                Use at least 8 characters.
              </p>
            ) : null}
          </div>

          <Button type="submit" size="default" className="auth-submit min-h-[48px] w-full" disabled={isSubmitting}>
            {mode === "sign-up" ? (
              <UserPlus className="size-4" aria-hidden="true" />
            ) : (
              <LogIn className="size-4" aria-hidden="true" />
            )}
            <span>
              {isSubmitting
                ? "Working..."
                : mode === "sign-up"
                  ? "Create account"
                  : "Sign in"}
            </span>
          </Button>
        </form>

        <div className="relative flex items-center py-1" aria-hidden="true">
          <div className="w-full border-t border-border" />
          <span className="shrink-0 bg-card px-3 text-xs uppercase tracking-wide text-muted-foreground">
            or
          </span>
          <div className="w-full border-t border-border" />
        </div>

        <Button
          type="button"
          variant="outline"
          size="default"
          className="auth-google min-h-[48px] w-full"
          disabled={isSubmitting}
          onClick={handleGoogleSignIn}
        >
          <LogIn className="size-4" aria-hidden="true" />
          <span>Continue with Google</span>
        </Button>
      </CardContent>

      <CardFooter className="justify-center border-0 pt-0">
        <Button
          type="button"
          variant="ghost"
          size="default"
          className="min-h-[44px] w-full text-sm text-muted-foreground hover:text-foreground"
          disabled={isSubmitting}
          onClick={toggleMode}
        >
          {mode === "sign-up"
            ? "Already have an account? Sign in"
            : "Don't have an account? Create one"}
        </Button>
      </CardFooter>
    </Card>
  );
}
