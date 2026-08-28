/**
 * User identity is now derived from the authenticated session instead of a
 * hard-coded demo id. The login gate in App guarantees `getOrCreateUserId`
 * is only called after authentication, so it reads the real account id.
 *
 * The `?? 1` fallback keeps existing component tests (which render panels
 * directly without seeding a session) from crashing; those tests stub
 * `fetch` anyway, so the fallback id never reaches a real backend.
 */

import { getAuthUser } from "./auth";

const FIXED_USER_ID = 1;

export const getOrCreateUserId = (): number => {
  return getAuthUser()?.id ?? FIXED_USER_ID;
};

/**
 * Legacy reset hook. Under the account model a "reset conversation" must not
 * mint a different user, so this is intentionally a no-op; identity stays
 * bound to the current login session.
 */
export const clearUserIdentity = (): void => {
  /* no-op */
};