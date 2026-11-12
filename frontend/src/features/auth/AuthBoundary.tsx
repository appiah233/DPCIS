import {
  Eye,
  EyeOff,
  KeyRound,
  LogIn,
  LogOut,
  ShieldAlert,
  ShieldCheck,
  UserPlus,
} from "lucide-react";
import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
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
      .catch(() => {
        if (!cancelled) {
          setLocalError("Unable to restore the authentication session.");
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

  const isConfigured = sharedAuth ? sharedAuth.isConfigured : isNeonAuthConfigured;
  const user = sharedAuth ? sharedAuth.sessionUser : localUser;
  const identity = sharedAuth ? sharedAuth.identity : null;
  const isLoading = sharedAuth ? sharedAuth.isLoading : localLoading;
  const displayError = localError ?? sharedAuth?.errorMessage ?? null;

  const handleGoogleSignIn = async () => {
    if (!isConfigured) return;
    setLocalError(null);
    setIsSubmitting(true);
    try {
      const result = await signInWithGoogle();
      if (result.error) {
        setLocalError(result.error.message ?? "Google sign-in could not be started.");
      }
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Google sign-in could not be started.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignOut = async () => {
    if (!isConfigured) return;
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
    try {
      const result =
        mode === "sign-up"
          ? await signUpWithEmail(email.trim(), password, name.trim())
          : await signInWithEmail(email.trim(), password);
      if (result.error) {
        setLocalError(result.error.message ?? "Email authentication failed.");
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
      setLocalError(error instanceof Error ? error.message : "Email authentication failed.");
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

  return (
    <Card className="min-h-56">
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-1">
          <CardTitle as="h2">Neon Managed Auth</CardTitle>
          <p className="text-sm text-muted-foreground">
            Sign in with Google OAuth or email via Neon Managed Better Auth; application roles are
            enforced on the backend.
          </p>
        </div>
        {isConfigured ? (
          <Badge variant="success">
            <ShieldCheck className="size-3.5" aria-hidden="true" />
            <span>{user ? "Signed in" : "Configured"}</span>
          </Badge>
        ) : (
          <Badge variant="warning">
            <ShieldAlert className="size-3.5" aria-hidden="true" />
            <span>Awaiting Auth URL</span>
          </Badge>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {!isConfigured ? (
          <Alert variant="warning" role="status">
            <div className="flex items-start gap-2.5">
              <KeyRound className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div>
                <AlertTitle>Managed Auth URL not yet set</AlertTitle>
                <AlertDescription>
                  Set <code>VITE_NEON_AUTH_URL</code> in <code>frontend/.env.local</code> after
                  enabling Managed Auth on the Neon branch. Protected routes remain locked until
                  authentication is configured.
                </AlertDescription>
              </div>
            </div>
          </Alert>
        ) : isLoading ? (
          <Alert variant="default" role="status">
            <AlertTitle>Restoring session</AlertTitle>
            <AlertDescription>
              Checking your Neon Managed Better Auth session and server role...
            </AlertDescription>
          </Alert>
        ) : user ? (
          <div className="space-y-4">
            <Alert variant="success" role="status">
              <AlertTitle>
                Signed in as {identity?.email ?? user.email ?? identity?.display_name ?? user.name ?? "authenticated user"}
              </AlertTitle>
              <AlertDescription>
                {identity ? (
                  <span>
                    Application role: <strong>{identity.role}</strong>. Bearer tokens are issued
                    dynamically per API request.
                  </span>
                ) : (
                  <span>
                    Managed Better Auth keeps your session active and provides bearer tokens only
                    for authenticated API requests.
                  </span>
                )}
              </AlertDescription>
            </Alert>

            <div>
              <Button
                type="button"
                variant="outline"
                size="default"
                disabled={isSubmitting}
                onClick={handleSignOut}
              >
                <LogOut className="size-4" aria-hidden="true" />
                <span>Sign out</span>
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Alert variant="default" role="status">
              <AlertTitle>
                {mode === "sign-in" ? "Sign in to Examination Hub" : "Create an Examination Hub account"}
              </AlertTitle>
              <AlertDescription>
                Use your email and password or continue with Google via Neon Managed Auth.
              </AlertDescription>
            </Alert>

            <form className="space-y-4" onSubmit={handleSubmitEmailAuth}>
              {mode === "sign-up" ? (
                <div className="field-group space-y-1.5">
                  <Label htmlFor={nameInputId}>Full name</Label>
                  <Input
                    id={nameInputId}
                    name="name"
                    required
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    autoComplete="name"
                    enterKeyHint="next"
                  />
                </div>
              ) : null}

              <div className="field-group space-y-1.5">
                <Label htmlFor={emailInputId}>Email address</Label>
                <Input
                  id={emailInputId}
                  name="email"
                  required
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="username"
                  spellCheck={false}
                  autoCorrect="off"
                  autoCapitalize="none"
                  enterKeyHint="next"
                />
              </div>

              <div className="field-group space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor={passwordInputId}>Password</Label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="default"
                    className="min-h-11 px-2.5 text-xs"
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
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
                  enterKeyHint="done"
                  aria-describedby={mode === "sign-up" ? passwordHelpId : undefined}
                />
                {mode === "sign-up" ? (
                  <p id={passwordHelpId} className="text-xs text-muted-foreground">
                    Use at least 8 characters.
                  </p>
                ) : null}
              </div>

              <div className="flex flex-wrap items-center gap-2.5 pt-1">
                <Button type="submit" size="default" disabled={isSubmitting}>
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

                <Button
                  type="button"
                  variant="outline"
                  size="default"
                  disabled={isSubmitting}
                  onClick={handleGoogleSignIn}
                >
                  <LogIn className="size-4" aria-hidden="true" />
                  <span>Continue with Google</span>
                </Button>

                <Button
                  type="button"
                  variant="ghost"
                  size="default"
                  disabled={isSubmitting}
                  onClick={toggleMode}
                >
                  {mode === "sign-up" ? "Already have an account?" : "Create an account"}
                </Button>
              </div>
            </form>
          </div>
        )}

        {displayError ? (
          <Alert variant="destructive" role="alert">
            <AlertTitle>Authentication error</AlertTitle>
            <AlertDescription>{displayError}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>

      <CardFooter className="justify-between">
        <span className="text-xs text-muted-foreground">
          Identity key: Managed Auth user ID (never an email address)
        </span>
        <span className="text-xs font-medium text-foreground">
          Managed by Neon Auth (server-enforced RBAC)
        </span>
      </CardFooter>
    </Card>
  );
}
