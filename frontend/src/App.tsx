import { Route, Routes, BrowserRouter } from "react-router-dom";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider } from "@/features/auth/AuthContext";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { AppShell } from "@/layouts/AppShell";
import { AdminDashboardPage } from "@/pages/AdminDashboardPage";
import { AdminOverviewPage } from "@/pages/AdminOverviewPage";
import { AdminResultsPage } from "@/pages/AdminResultsPage";
import { AdminExamEditorPage } from "@/pages/AdminExamEditorPage";
import { AdminExamNewPage } from "@/pages/AdminExamNewPage";
import { AdminExamResultsPage } from "@/pages/AdminExamResultsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { StudentAttemptPage } from "@/pages/StudentAttemptPage";
import { StudentDashboardPage } from "@/pages/StudentDashboardPage";
import { StudentExamInstructionsPage } from "@/pages/StudentExamInstructionsPage";
import { StudentResultPage } from "@/pages/StudentResultPage";

export function App() {
  return (
    <ErrorBoundary fallbackTitle="Examination Hub could not initialize">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<OverviewPage />} />
              <Route element={<ProtectedRoute requiredRole="STUDENT" />}>
                <Route path="/student" element={<StudentDashboardPage />} />
                <Route path="/student/exams/:examId" element={<StudentExamInstructionsPage />} />
                <Route path="/student/attempts/:attemptId" element={<StudentAttemptPage />} />
                <Route path="/student/results/:attemptId" element={<StudentResultPage />} />
              </Route>
              <Route element={<ProtectedRoute requiredRole="ADMIN" />}>
                <Route path="/admin" element={<AdminOverviewPage />} />
                <Route path="/admin/exams" element={<AdminDashboardPage />} />
                <Route path="/admin/results" element={<AdminResultsPage />} />
                <Route path="/admin/exams/new" element={<AdminExamNewPage />} />
                <Route path="/admin/exams/:examId" element={<AdminExamEditorPage />} />
                <Route path="/admin/exams/:examId/results" element={<AdminExamResultsPage />} />
              </Route>
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
