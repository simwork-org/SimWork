const COOKIE_MAX_AGE = 600;
const IS_HTTPS = typeof window !== "undefined" && window.location.protocol === "https:";
export type AuthIntent = "company" | "candidate";

export type PendingAuthState = {
  role?: string;
  invite?: string;
  next?: string;
};

type SessionLike = {
  session_id: string;
  assessment_id?: string | null;
  invite_token?: string | null;
  company_name?: string | null;
};

function sanitizeNextPath(next?: string | null): string | null {
  if (!next) return null;
  try {
    const decoded = decodeURIComponent(next);
    if (!decoded.startsWith("/") || decoded.startsWith("//")) return null;
    const parsed = new URL(decoded, "http://simwork.local");
    if (parsed.pathname === "/") return null;
    if (parsed.pathname.startsWith("/api/auth")) return null;
    if (parsed.pathname.startsWith("/login")) return null;
    if (parsed.pathname.startsWith("/auth/redirect")) return null;
    parsed.searchParams.delete("auth");
    parsed.searchParams.delete("next");
    parsed.searchParams.delete("invite");
    const sanitized = `${parsed.pathname}${parsed.search}${parsed.hash}`;
    return sanitized === "/" ? null : sanitized;
  } catch {
    return null;
  }
}

function isCompanyRoute(path: string): boolean {
  return path === "/dashboard" || path.startsWith("/dashboard/") || path.startsWith("/review/");
}

function isCandidateRoute(path: string): boolean {
  return (
    path === "/candidate" ||
    path === "/scenarios" ||
    path.startsWith("/briefing/") ||
    path.startsWith("/workspace/") ||
    path.startsWith("/complete/")
  );
}

export function buildLoginUrl(options: PendingAuthState = {}): string {
  const params = new URLSearchParams();
  if (options.role) params.set("role", options.role);
  if (options.invite) params.set("invite", options.invite);
  const safeNext = sanitizeNextPath(options.next);
  if (safeNext) params.set("next", safeNext);
  const query = params.toString();
  return query ? `/login?${query}` : "/login";
}

export function buildLandingAuthUrl(options: {
  auth: AuthIntent;
  next?: string | null;
  invite?: string | null;
}): string {
  const params = new URLSearchParams();
  params.set("auth", options.auth);
  const safeNext = sanitizeNextPath(options.next);
  if (safeNext) params.set("next", safeNext);
  if (options.invite) params.set("invite", options.invite);
  const query = params.toString();
  return query ? `/?${query}` : "/";
}

export function inferCompanyIntent(nextPath?: string | null): boolean {
  const safeNext = sanitizeNextPath(nextPath);
  return !!safeNext && isCompanyRoute(safeNext);
}

export function setCookie(name: string, value: string) {
  let cookie = `${name}=${encodeURIComponent(value)};path=/;max-age=${COOKIE_MAX_AGE};SameSite=Lax`;
  if (IS_HTTPS) cookie += ";Secure";
  document.cookie = cookie;
}

export function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

export function clearCookie(name: string) {
  document.cookie = `${name}=;path=/;max-age=0`;
}

export function setPendingAuthState(state: PendingAuthState) {
  clearPendingAuthState();
  if (state.role) setCookie("simwork_role", state.role);
  if (state.invite) setCookie("simwork_invite", state.invite);
  const safeNext = sanitizeNextPath(state.next);
  if (safeNext) setCookie("simwork_next", safeNext);
}

export function readPendingAuthState(): Required<PendingAuthState> {
  return {
    role: getCookie("simwork_role"),
    invite: getCookie("simwork_invite"),
    next: getCookie("simwork_next"),
  };
}

export function clearPendingAuthState() {
  clearCookie("simwork_role");
  clearCookie("simwork_invite");
  clearCookie("simwork_next");
}

export function findAssignedSession<T extends SessionLike>(sessions: T[]): T | undefined {
  return sessions.find((item) => item.assessment_id || item.invite_token);
}

export function resolveAuthenticatedDestination(
  role: string,
  sessions: SessionLike[],
  next?: string | null
): string {
  const safeNext = sanitizeNextPath(next);

  if (role === "company") {
    if (safeNext && isCompanyRoute(safeNext)) return safeNext;
    return "/dashboard";
  }

  if (safeNext && isCandidateRoute(safeNext)) return safeNext;

  return "/candidate";
}
