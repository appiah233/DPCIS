import { Eye, EyeOff, Loader2, LogIn, LogOut, RotateCcw, UserPlus } from "lucide-react";
import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";

import { GoogleLogo } from "@/components/GoogleLogo";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOptionalAuth } from "@/features/auth/useAuth";
import { confirmGoogleEmailProof } from "@/lib/api";
import {
  getCurrentAuthUser,
  isNeonAuthConfigured,
  requestPasswordCode,
  resetPasswordWithCode,
  sendEmailVerificationCode,
  signInWithEmail,
  signInWithGoogle,
  signOutNeonAuth,
  signUpWithEmail,
  verifyEmailCode,
} from "@/lib/auth";
import type { AuthUser } from "@/lib/auth";

export interface AuthBoundaryProps {
  onAuthSuccess?: () => void | Promise<void>;
  embedded?: boolean;
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
  const code = error && typeof error === "object" && "code" in error
    ? String((error as { code?: unknown }).code ?? "") : "";
  if (/verification code.*expired/i.test(raw)) {
    return "Your verification code has expired. Request a new code.";
  }
  if (/verification code.*incorrect/i.test(raw)) {
    return "The verification code is incorrect. Use the most recent code sent to you.";
  }
  if (/password.*(too long|no more than 128)/i.test(raw)) {
    return "Please use a password with no more than 128 characters.";
  }
  if (/authentication (configuration|provider)/i.test(raw)) {
    return "The sign-in service is temporarily unavailable. Please try again shortly.";
  }
  if (/EMAIL_NOT_VERIFIED|email.*(not verified|unverified)|verify.*email/i.test(`${code} ${raw}`)) {
    return "Your email address needs verification. Request a code below to finish signing in.";
  }
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

export function AuthBoundary({ onAuthSuccess, embedded = false }: AuthBoundaryProps = {}) {
  const sharedAuth = useOptionalAuth();
  const baseId = useId();

  const [localUser, setLocalUser] = useState<AuthUser | null>(null);
  const [localLoading, setLocalLoading] = useState(
    () => sharedAuth === null && isNeonAuthConfigured,
  );
  const [localError, setLocalError] = useState<string | null>(null);
  const [signupNotice, setSignupNotice] = useState<string | null>(null);
  const [verificationEmail, setVerificationEmail] = useState<string | null>(null);
  const [verificationCode, setVerificationCode] = useState("");
  const [verificationBusy, setVerificationBusy] = useState(false);
  const [passwordResetEmail, setPasswordResetEmail] = useState<string | null>(null);
  const [passwordResetCode, setPasswordResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [touched, setTouched] = useState({ name: false, email: false, password: false });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGoogleSubmitting, setIsGoogleSubmitting] = useState(false);

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
    setIsGoogleSubmitting(true);
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
      setIsGoogleSubmitting(false);
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

  const getNameError = (val: string) =>
    mode === "sign-up" && val.trim().length === 0 ? "Enter your full name." : null;
  const getEmailError = (val: string) => {
    const trimmed = val.trim();
    if (!trimmed) return "Enter your email address.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) return "Enter a valid email address.";
    return null;
  };
  const getPasswordError = (val: string) => {
    if (!val) return "Enter your password.";
    if (val.length < 8) return "Password must be at least 8 characters.";
    return null;
  };

  const nameError = hasSubmitted || touched.name ? getNameError(name) : null;
  const emailError = hasSubmitted || touched.email ? getEmailError(email) : null;
  const passwordError = hasSubmitted || touched.password ? getPasswordError(password) : null;

  const handleSubmitEmailAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setHasSubmitted(true);
    setLocalError(null);
    setSignupNotice(null);
    if (getNameError(name) || getEmailError(email) || getPasswordError(password)) {
      return;
    }
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
        if (mode === "sign-in" && /EMAIL_NOT_VERIFIED|email.*(not verified|unverified)|verify.*email/i.test(
          `${"code" in result.error ? result.error.code : ""} ${result.error.message}`,
        )) setVerificationEmail(email.trim());
        return;
      }

      if (mode === "sign-up") {
        const currentUser = await getCurrentAuthUser();
        if (!currentUser) {
          setPassword("");
          setMode("sign-in");
          setVerificationEmail(email.trim());
          const sent = await sendEmailVerificationCode(email.trim());
          setSignupNotice(sent.error
            ? "Your account was created, but we could not send a verification code. Use Resend code below."
            : "Your account was created. Enter the verification code sent to your email.");
          return;
        }
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
    setSignupNotice(null);
    setVerificationEmail(null);
    setPasswordResetEmail(null);
    setHasSubmitted(false);
    setTouched({ name: false, email: false, password: false });
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
    const googleProofRequired = sharedAuth?.googleEmailProofRequired ?? false;
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader className="space-y-1.5">
          <CardTitle as="h2">Signed in</CardTitle>
          <CardDescription>
            Signed in as {user.email ?? user.name ?? "your account"}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {googleProofRequired ? <div className="space-y-3 rounded-md border p-4">
            <p className="text-sm">We need a code sent to {user.email ?? "your email"} before opening your workspace. The code will also let you create a password for future email sign-in.</p>
            <Button type="button" variant="outline" disabled={verificationBusy || !user.email}
              onClick={() => void (async () => {
                setVerificationBusy(true);
                setLocalError(null);
                try {
                  const sent = await requestPasswordCode(user.email!);
                  if (sent.error) throw sent.error;
                  setPasswordResetCode("");
                  setSignupNotice("A verification code was sent to your email.");
                } catch (error) {
                  setLocalError(sanitizeAuthError(error, "We could not send a code. Try again."));
                } finally { setVerificationBusy(false); }
              })()}>Send verification code</Button>
            {signupNotice ? <p role="status" className="text-sm">{signupNotice}</p> : null}
            <Label htmlFor={`${baseId}-google-code`}>Verification code</Label>
            <Input id={`${baseId}-google-code`} inputMode="numeric" autoComplete="one-time-code"
              value={passwordResetCode} onChange={(event) => setPasswordResetCode(event.target.value.trim())} />
            <Label htmlFor={`${baseId}-google-password`}>Create a password</Label>
            <Input id={`${baseId}-google-password`} type="password" autoComplete="new-password" minLength={8} maxLength={128}
              value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            <p className="text-xs text-muted-foreground">Use 8–128 characters. Enter the most recent verification code sent to your email.</p>
            <Button type="button" disabled={verificationBusy || !passwordResetCode || newPassword.length < 8 || newPassword.length > 128}
              onClick={() => void (async () => {
                setVerificationBusy(true);
                setLocalError(null);
                try {
                  await confirmGoogleEmailProof(passwordResetCode, newPassword);
                  setPasswordResetCode("");
                  setNewPassword("");
                  setSignupNotice(null);
                  if (sharedAuth) await sharedAuth.refreshAuth();
                  if (onAuthSuccess && onAuthSuccess !== sharedAuth?.refreshAuth) await onAuthSuccess();
                } catch (error) {
                  setLocalError(sanitizeAuthError(error, "The code or password could not be accepted."));
                } finally { setVerificationBusy(false); }
              })()}>Verify and create password</Button>
          </div> : null}
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

  const formBody = (
    <div className="space-y-4">
      {displayError ? (
        <Alert id={errorAlertId} variant="destructive" role="alert">
          <AlertTitle>{mode === "sign-up" ? "Unable to create account" : "Unable to sign in"}</AlertTitle>
          <AlertDescription>{displayError}</AlertDescription>
        </Alert>
      ) : null}
      {signupNotice ? <Alert role="status"><AlertTitle>Account created</AlertTitle>
        <AlertDescription>{signupNotice}</AlertDescription></Alert> : null}
      {verificationEmail ? <div className="space-y-3 rounded-md border p-4">
        <Label htmlFor={`${baseId}-verification-code`}>Email verification code</Label>
        <Input id={`${baseId}-verification-code`} inputMode="numeric" autoComplete="one-time-code"
          value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.trim())}
          aria-label="Email verification code" />
        <div className="flex flex-wrap gap-2">
          <Button type="button" disabled={verificationBusy || !verificationCode} onClick={() => void (async () => {
            setVerificationBusy(true);
            setLocalError(null);
            try {
              const result = await verifyEmailCode(verificationEmail, verificationCode);
              if (result.error) throw result.error;
              setVerificationEmail(null);
              setVerificationCode("");
              setSignupNotice("Email verified. You can sign in now.");
              if (sharedAuth) await sharedAuth.refreshAuth();
              else setLocalUser(await getCurrentAuthUser());
              if (onAuthSuccess && onAuthSuccess !== sharedAuth?.refreshAuth) await onAuthSuccess();
            } catch (error) {
              setLocalError(sanitizeAuthError(error, "That code could not be verified. Check it and try again."));
            } finally { setVerificationBusy(false); }
          })()}>Verify email</Button>
          <Button type="button" variant="outline" disabled={verificationBusy} onClick={() => void (async () => {
            setVerificationBusy(true);
            try {
              const result = await sendEmailVerificationCode(verificationEmail);
              if (result.error) throw result.error;
              setSignupNotice("A new verification code was sent to your email.");
              setLocalError(null);
            } catch (error) {
              setLocalError(sanitizeAuthError(error, "We could not send a code. Please try again."));
            } finally { setVerificationBusy(false); }
          })()}>Resend code</Button>
        </div>
      </div> : null}
      {mode === "sign-in" ? <div className="space-y-3">
        <Button type="button" variant="ghost" className="min-h-11 px-0 underline"
          disabled={verificationBusy} onClick={() => void (async () => {
            if (getEmailError(email)) {
              setLocalError("Enter your email address above to set or reset a password.");
              return;
            }
            setVerificationBusy(true);
            setLocalError(null);
            try {
              const result = await requestPasswordCode(email.trim());
              if (result.error) throw result.error;
              setPasswordResetEmail(email.trim());
              setSignupNotice("If this email has an account, a password code will arrive shortly.");
            } catch (error) {
              setLocalError(sanitizeAuthError(error, "We could not request a password code. Try again."));
            } finally { setVerificationBusy(false); }
          })()}>Set or reset your password</Button>
        {passwordResetEmail ? <div className="space-y-3 rounded-md border p-4">
          <Label htmlFor={`${baseId}-password-code`}>Password code</Label>
          <Input id={`${baseId}-password-code`} inputMode="numeric" autoComplete="one-time-code"
            value={passwordResetCode} onChange={(event) => setPasswordResetCode(event.target.value.trim())} />
          <Label htmlFor={`${baseId}-new-password`}>New password</Label>
          <Input id={`${baseId}-new-password`} type="password" autoComplete="new-password"
            value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
          <Button type="button" disabled={verificationBusy || !passwordResetCode || newPassword.length < 8}
            onClick={() => void (async () => {
              setVerificationBusy(true);
              setLocalError(null);
              try {
                const result = await resetPasswordWithCode(passwordResetEmail, passwordResetCode, newPassword);
                if (result.error) throw result.error;
                setPasswordResetEmail(null);
                setPasswordResetCode("");
                setNewPassword("");
                setSignupNotice("Password saved. Sign in with your email and new password.");
              } catch (error) {
                setLocalError(sanitizeAuthError(error, "The code or password could not be accepted. Try again."));
              } finally { setVerificationBusy(false); }
            })()}>Save new password</Button>
        </div> : null}
      </div> : null}

      <form className="space-y-4" noValidate onSubmit={handleSubmitEmailAuth}>
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
              onBlur={() => setTouched((prev) => ({ ...prev, name: true }))}
              autoComplete="name"
              enterKeyHint="next"
              aria-invalid={Boolean(nameError)}
              aria-describedby={nameError ? `${nameInputId}-error` : undefined}
            />
            {nameError ? (
              <p id={`${nameInputId}-error`} className="text-xs font-medium text-destructive">
                {nameError}
              </p>
            ) : null}
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
            onBlur={() => setTouched((prev) => ({ ...prev, email: true }))}
            autoComplete="email"
            spellCheck={false}
            autoCorrect="off"
            autoCapitalize="none"
            enterKeyHint="next"
            aria-invalid={Boolean(emailError)}
            aria-describedby={
              [emailError ? `${emailInputId}-error` : null, emailDescribedBy]
                .filter(Boolean)
                .join(" ") || undefined
            }
          />
          {emailError ? (
            <p id={`${emailInputId}-error`} className="text-xs font-medium text-destructive">
              {emailError}
            </p>
          ) : null}
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
            onBlur={() => setTouched((prev) => ({ ...prev, password: true }))}
            autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
            enterKeyHint="done"
            aria-invalid={Boolean(passwordError)}
            aria-describedby={
              [passwordError ? `${passwordInputId}-error` : null, passwordDescribedBy]
                .filter(Boolean)
                .join(" ") || undefined
            }
          />
          {passwordError ? (
            <p id={`${passwordInputId}-error`} className="text-xs font-medium text-destructive">
              {passwordError}
            </p>
          ) : null}
          {mode === "sign-up" ? (
            <p id={passwordHelpId} className="text-xs text-muted-foreground">
              Use at least 8 characters.
            </p>
          ) : null}
        </div>

        <Button
          type="submit"
          size="default"
          className="auth-submit min-h-[48px] w-full"
          disabled={isSubmitting}
        >
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

      <button
        type="button"
        className="auth-google"
        disabled={isSubmitting || !isConfigured}
        aria-busy={isGoogleSubmitting ? "true" : undefined}
        onClick={handleGoogleSignIn}
      >
        <GoogleLogo size={18} />
        {isGoogleSubmitting ? (
          <>
            <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden="true" />
            <span>Redirecting to Google...</span>
          </>
        ) : (
          <span>{mode === "sign-up" ? "Sign up with Google" : "Sign in with Google"}</span>
        )}
      </button>

      <div className="pt-1 text-center">
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
      </div>
    </div>
  );

  if (embedded) {
    return <div className="w-full space-y-5">{formBody}</div>;
  }

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

      <CardContent>{formBody}</CardContent>
    </Card>
  );
}
