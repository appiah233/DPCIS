import { ArrowRight, CheckCircle2, Database, Lock, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { HealthStatusCard } from "@/components/HealthStatusCard";
import { PageHeader } from "@/components/PageHeader";
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
import { AuthBoundary } from "@/features/auth/AuthBoundary";
import { useAuth } from "@/features/auth/useAuth";

export function OverviewPage() {
  const { identity } = useAuth();

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Assessment Portal"
        title="Examination Hub"
        description="Server-authoritative timed multiple-choice examinations with Neon Managed Auth, instant backend grading, and permanent attempt records."
      />

      <section aria-labelledby="runtime-readiness-heading" className="space-y-4">
        <h2
          id="runtime-readiness-heading"
          className="text-lg font-semibold tracking-tight text-foreground"
        >
          Account &amp; Service Status
        </h2>
        <div className="card-grid">
          <HealthStatusCard />
          <AuthBoundary />
        </div>
      </section>

      <section aria-labelledby="workspace-routes-heading" className="space-y-4">
        <h2
          id="workspace-routes-heading"
          className="text-lg font-semibold tracking-tight text-foreground"
        >
          Examination Workspaces
        </h2>
        <div className="card-grid">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle as="h3">Student Examination Portal</CardTitle>
                <Badge variant={identity?.role === "STUDENT" ? "accent" : "secondary"}>
                  {identity?.role === "STUDENT" ? "Your Portal" : "Student Role"}
                </Badge>
              </div>
              <CardDescription>
                View published examinations, take timed assessments with live autosave, recover
                seamlessly across refreshes, and review permitted scores.
              </CardDescription>
            </CardHeader>
            <CardFooter>
              <Button asChild variant="outline">
                <Link to="/student">
                  <span>Open Student Portal</span>
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </Button>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle as="h3">Administrator Console</CardTitle>
                <Badge variant={identity?.role === "ADMIN" ? "accent" : "secondary"}>
                  {identity?.role === "ADMIN" ? "Your Console" : "Admin Role"}
                </Badge>
              </div>
              <CardDescription>
                Create examinations, parse and edit bulk MCQ items, configure pass marks and timers,
                publish exams, and audit student outcomes.
              </CardDescription>
            </CardHeader>
            <CardFooter>
              <Button asChild variant="outline">
                <Link to="/admin">
                  <span>Open Admin Console</span>
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </Button>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle as="h3">Integrity &amp; Timer Guarantees</CardTitle>
                <Badge variant="outline">Server-Enforced</Badge>
              </div>
              <CardDescription>
                Core examination rules verified strictly on FastAPI and PostgreSQL, independent of
                browser state.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <Lock className="size-4 shrink-0 text-primary" aria-hidden="true" />
                <span>Answer keys stay server-side throughout active attempts</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="size-4 shrink-0 text-primary" aria-hidden="true" />
                <span>Countdown and expiry deadlines derive from server UTC timestamps</span>
              </div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-4 shrink-0 text-primary" aria-hidden="true" />
                <span>Role access enforced against application_users in PostgreSQL</span>
              </div>
              <div className="flex items-center gap-2">
                <Database className="size-4 shrink-0 text-primary" aria-hidden="true" />
                <span>Finalized attempt scores and question snapshots are immutable</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
