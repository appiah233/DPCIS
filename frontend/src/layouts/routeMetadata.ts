export interface RouteMetadata {
  title: string;
  announcement: string;
  examFocusMode?: boolean;
}

export function resolveRouteMetadata(pathname: string): RouteMetadata {
  if (pathname === "/") {
    return {
      title: "Sign In | Examination Hub",
      announcement: "Sign in page",
    };
  }
  if (pathname === "/student") {
    return {
      title: "Examinations | Examination Hub",
      announcement: "Examinations page",
    };
  }
  if (pathname.startsWith("/student/attempts/")) {
    return {
      title: "Active Examination | Examination Hub",
      announcement: "Active timed examination page",
      examFocusMode: true,
    };
  }
  if (pathname.startsWith("/student/results/")) {
    return {
      title: "Examination Result | Examination Hub",
      announcement: "Examination result page",
    };
  }
  if (pathname.startsWith("/student/exams/")) {
    return {
      title: "Exam Instructions | Examination Hub",
      announcement: "Examination instructions page",
    };
  }
  if (pathname === "/admin") {
    return {
      title: "Overview | Examination Hub",
      announcement: "Administration overview page",
    };
  }
  if (pathname === "/admin/exams") {
    return {
      title: "Examinations | Examination Hub",
      announcement: "Examinations management page",
    };
  }
  if (pathname === "/admin/results") {
    return {
      title: "Results | Examination Hub",
      announcement: "Administration results page",
    };
  }
  if (pathname === "/admin/exams/new") {
    return {
      title: "Create Examination | Examination Hub",
      announcement: "Create examination page",
    };
  }
  if (/^\/admin\/exams\/[^/]+\/results\/?$/.test(pathname)) {
    return {
      title: "Examination Results | Examination Hub",
      announcement: "Examination results page",
    };
  }
  if (pathname.startsWith("/admin/exams/")) {
    return {
      title: "Manage Examination | Examination Hub",
      announcement: "Manage examination page",
    };
  }
  return {
    title: "Page Not Found | Examination Hub",
    announcement: "Page not found",
  };
}
