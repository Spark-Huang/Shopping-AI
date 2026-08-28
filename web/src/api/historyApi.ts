/**
 * History service (D3): fetch the server-side conversation context for the
 * current user via the orchestrator read-only proxy (GET /context/{user_id})
 * so the chat can replay prior turns after a page refresh.
 */

import { config } from "../config/appConfig";
import { authFetch } from "../lib/auth";
import { HistoryResponse } from "../types/orders";

/**
 * Fetch the persisted conversation context for the given user id.
 * Throws on network / HTTP errors so callers can fall back silently.
 */
export const fetchHistory = async (
  userId: number
): Promise<HistoryResponse> => {
  const url = `${config.api.baseUrl}/context/${userId}`;
  const response = await authFetch(url);
  if (!response.ok) {
    throw new Error(`History fetch failed: HTTP ${response.status}`);
  }
  return (await response.json()) as HistoryResponse;
};

/** Persist a user preference without invoking the full agent chain. */
export const addContext = async (
  userId: number,
  newContext: string
): Promise<void> => {
  const response = await authFetch(`${config.api.baseUrl}/context/${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_context: newContext }),
  });
  if (!response.ok) {
    throw new Error(`Context update failed: HTTP ${response.status}`);
  }
};
