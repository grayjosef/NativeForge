import { apiFetchBase, readHttpError } from "./m0ApiClient";

/**
 * The sign-in side of the API.
 *
 * Deliberately separate from `m0ApiClient`: every call in that module carries
 * an organization, and none of these can. Asking who you are is the question
 * you ask *before* you have an organization, and mixing the two is how a
 * sign-in page ends up sending an organization header it does not have.
 */

export interface AuthProvider {
  key: string;
  label: string;
  configured: boolean;
  /** Where the browser goes to begin a sign-in with this provider. */
  start_path: string;
  /** The URI an operator must register with this provider. */
  redirect_uri: string;
  scopes: string;
}

export interface ProvidersResponse {
  providers: AuthProvider[];
  any_configured: boolean;
  login_live: boolean;
  customer_auth_live: boolean;
}

export interface SessionResponse {
  authenticated: boolean;
  organization_id: string | null;
  roles: string[];
}

export async function getAuthProviders(
  baseUrl: string = apiFetchBase(),
): Promise<ProvidersResponse> {
  const res = await fetch(`${baseUrl}/api/auth/providers`);
  if (!res.ok) throw new Error(await readHttpError(res));
  const raw = (await res.json()) as Record<string, unknown>;
  return {
    providers: Array.isArray(raw.providers) ? (raw.providers as AuthProvider[]) : [],
    any_configured: Boolean(raw.any_configured),
    login_live: Boolean(raw.login_live),
    customer_auth_live: Boolean(raw.customer_auth_live),
  };
}

/**
 * Whether this browser currently holds a session, and for which organization.
 *
 * The endpoint reports a great deal more than this - every blocked reason,
 * every gate, every verification boolean - and none of that is the
 * application's business. It is read here down to the three facts the UI
 * routes on, so a future field cannot accidentally become something a page
 * renders.
 */
export async function getAuthSession(
  baseUrl: string = apiFetchBase(),
): Promise<SessionResponse> {
  const res = await fetch(`${baseUrl}/api/auth/session`, {
    // The session cookie is the entire point of the request.
    credentials: "include",
  });
  if (!res.ok) throw new Error(await readHttpError(res));
  const raw = (await res.json()) as Record<string, unknown>;
  const verification = (raw.session_verification ?? {}) as Record<string, unknown>;
  return {
    authenticated: raw.status === "authenticated",
    organization_id:
      typeof verification.organization_id === "string" ? verification.organization_id : null,
    roles: Array.isArray(verification.roles) ? (verification.roles as string[]) : [],
  };
}

export async function signOut(baseUrl: string = apiFetchBase()): Promise<void> {
  await fetch(`${baseUrl}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}
