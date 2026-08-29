/**
 * History service (D3): fetch the server-side conversation context for the
 * current user via the orchestrator read-only proxy (GET /context/{user_id})
 * so the chat can replay prior turns after a page refresh.
 */

import { config } from "../config/appConfig";
import { authFetch } from "../lib/auth";
import { HistoryResponse } from "../types/orders";
import { ProductPayload } from "../lib/images";

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

export interface ChatSession {
  id: number;
  user_id: number;
  title: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface SessionMessage {
  id: number;
  user_id: number;
  session_id: number | null;
  role: "user" | "assistant";
  content: string;
  products?: ProductPayload | null;
  created_at: string | null;
}

const requestSession = async (url: string, init?: RequestInit): Promise<Response> => {
  const response = await authFetch(url, init);
  if (!response.ok) {
    throw new Error(`Session request failed: HTTP ${response.status}`);
  }
  return response;
};

export const listChatSessions = async (userId: number): Promise<ChatSession[]> => {
  const response = await requestSession(`${config.api.baseUrl}/sessions/${userId}`);
  const body = (await response.json()) as { sessions: ChatSession[] };
  return body.sessions ?? [];
};

export const createChatSession = async (userId: number): Promise<ChatSession> => {
  const response = await requestSession(`${config.api.baseUrl}/sessions/${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: "" }),
  });
  return (await response.json()) as ChatSession;
};

export const fetchSessionMessages = async (
  userId: number,
  sessionId: number
): Promise<SessionMessage[]> => {
  const response = await requestSession(
    `${config.api.baseUrl}/sessions/${userId}/${sessionId}/messages`
  );
  const body = (await response.json()) as { messages: SessionMessage[] };
  return body.messages;
};

export const deleteChatSession = async (
  userId: number,
  sessionId: number
): Promise<void> => {
  await requestSession(`${config.api.baseUrl}/sessions/${userId}/${sessionId}`, {
    method: "DELETE",
  });
};
