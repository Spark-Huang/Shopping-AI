import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import Chatbox from "./ChatWindow";
import * as historyApi from "../../api/historyApi";
import "../../i18n";

vi.mock("react-toastify", () => ({
  toast: { info: vi.fn(), success: vi.fn(), error: vi.fn() },
}));

vi.mock("../../api/historyApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/historyApi")>();
  return {
    ...actual,
    createChatSession: vi.fn(),
    deleteChatSession: vi.fn(),
    fetchSessionMessages: vi.fn(),
    listChatSessions: vi.fn(),
  };
});

const currentUserId = "1";
const requestHistory = vi.fn();
const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);
Element.prototype.scrollIntoView = vi.fn();

afterEach(() => {
  cleanup();
});

const renderChatbox = () =>
  render(
    <Chatbox
      visible={true}
      safetyEnabled={true}
      onSafetyChange={vi.fn()}
    />
  );

describe("Chatbox header controls", () => {
  it("keeps the safety setting out of the chat header", () => {
    renderChatbox();

    expect(screen.queryByTestId("safety-switch")).toBeNull();
    expect(screen.queryByText("Safety")).toBeNull();
    expect(screen.queryByText(/Safety checks/i)).toBeNull();
  });
});

const finishWelcomeTypewriter = async () => {
  for (let elapsed = 0; elapsed < 4000; elapsed += 100) {
    await vi.advanceTimersByTimeAsync(100);
    if (
      screen.queryByText(
        "Welcome to Guikelai 👋 Tell me who it is for, your budget, and preferred tastes. I will help you choose Guizhou foods, teas, and heritage crafts."
      )
    )
      return;
  }
  throw new Error("Onboarding introduction did not finish typing");
};

describe("Chatbox user identity replay behavior", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    localStorage.clear();
    sessionStorage.clear();
    localStorage.setItem(
      "shopping_auth_user",
      JSON.stringify({ id: 1, username: "alice" })
    );
    localStorage.setItem("shopping_auth_token", "test-token");
    requestHistory.mockReset();
    fetchMock.mockReset();
    fetchMock.mockImplementation(requestHistory);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it.each([
    {
      name: "with history",
      context: "Previous recommendation\n\nPrevious cart update",
      shouldReplayHistory: true,
    },
    { name: "with empty history", context: "", shouldReplayHistory: false },
    {
      name: "with HTTP 500",
      context: undefined,
      shouldReplayHistory: false,
      rejectHistory: true,
    },
  ])(
    "preserves the user id on mount replay $name",
    async ({ context, shouldReplayHistory, rejectHistory }) => {
      if (rejectHistory) {
        requestHistory.mockRejectedValue(new Error("HTTP 500"));
      } else {
        requestHistory.mockResolvedValue({
          ok: true,
          json: async () => ({ context }),
        });
      }

      renderChatbox();
      await vi.advanceTimersByTimeAsync(2500);

      expect(
        requestHistory.mock.calls.some(
          (call) => String(call[0]) === `/api/context/${currentUserId}`
        )
      ).toBe(true);
      if (shouldReplayHistory) {
        expect(
          screen.getAllByText("Previous recommendation").length
        ).toBeGreaterThan(0);
      } else {
        await finishWelcomeTypewriter();
        expect(
          screen.getByText(
            "Welcome to Guikelai 👋 Tell me who it is for, your budget, and preferred tastes. I will help you choose Guizhou foods, teas, and heritage crafts."
          )
        ).toBeTruthy();
        expect(screen.getAllByTestId("example-chip")).toHaveLength(5);
        expect(screen.queryByText(/monthly spending limit|impulse buy/i)).toBeNull();
      }
      const storedUser = JSON.parse(
        localStorage.getItem("shopping_auth_user") ?? "null"
      );
      expect(storedUser?.id).toBe(Number(currentUserId));
      expect(sessionStorage.getItem("shopping_auth_user")).toBeNull();
    }
  );

  it("keeps the authenticated user on explicit reset", async () => {
    requestHistory.mockResolvedValue({
      ok: true,
      json: async () => ({
        context: "Previous recommendation\n\nPrevious cart update",
      }),
    });

    renderChatbox();
    await vi.advanceTimersByTimeAsync(500);
    fireEvent.click(screen.getAllByLabelText("Reset conversation")[0]);
    fireEvent.click(
      screen.getAllByLabelText("Confirm clearing the conversation?")[0]
    );
    await vi.advanceTimersByTimeAsync(2500);

    const storedUser = JSON.parse(
      localStorage.getItem("shopping_auth_user") ?? "null"
    );
    expect(storedUser?.id).toBe(Number(currentUserId));
  });

  it("filters internal records and truncates long history blocks", async () => {
    requestHistory.mockResolvedValue({
      ok: true,
      json: async () => ({
        context: [
          "These products are available in the catalog:",
          "Agent Response: internal debug text",
          "User asked: internal question",
          "CSV: item,price",
          "PRICE: 39.99",
          "Luminous Satin Dress | formal apparel | https://example.com/product",
          "",
          "A readable history block that is intentionally longer than eighty characters in total and must be summarized.",
        ].join("\n"),
      }),
    });

    renderChatbox();
    await vi.advanceTimersByTimeAsync(2500);

    expect(screen.queryByText(/PRICE:/i)).toBeNull();
    expect(screen.queryByText(/Agent Response:/i)).toBeNull();
    expect(screen.queryByText(/User asked:/i)).toBeNull();
    expect(screen.queryByText(/CSV:/i)).toBeNull();
    expect(
      screen.getByText(
        "A readable history block that is intentionally longer than eighty characters in…"
      )
    ).toBeTruthy();
  });

  it("does not show first-run budget setup controls", async () => {
    requestHistory.mockResolvedValue({
      ok: true,
      json: async () => ({
        context: "",
      }),
    });
    renderChatbox();
    await finishWelcomeTypewriter();

    expect(screen.queryByTestId("budget-form")).toBeNull();
    expect(screen.queryByRole("button", { name: /budget/i })).toBeNull();
  });
});

describe("Chatbox session history", () => {
  beforeEach(() => {
    vi.useRealTimers();
    localStorage.clear();
    localStorage.setItem(
      "shopping_auth_user",
      JSON.stringify({ id: 1, username: "alice" })
    );
    localStorage.setItem("shopping_auth_token", "token");
    fetchMock.mockReset();
    vi.mocked(historyApi.listChatSessions).mockResolvedValue([
      { id: 2, user_id: 1, title: "买玩具", created_at: null, updated_at: null },
      { id: 1, user_id: 1, title: "买化妆台和衣服", created_at: null, updated_at: null },
    ]);
    vi.mocked(historyApi.fetchSessionMessages).mockResolvedValue([
      { id: 1, user_id: 1, session_id: 2, role: "user", content: "买玩具", created_at: null },
      { id: 2, user_id: 1, session_id: 2, role: "assistant", content: "找到积木", created_at: null },
    ]);
    vi.mocked(historyApi.deleteChatSession).mockResolvedValue();
    vi.mocked(historyApi.createChatSession).mockResolvedValue({
      id: 3, user_id: 1, title: "", created_at: null, updated_at: null,
    });
    fetchMock.mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/sessions/1/2/messages")) {
        return {
          ok: true,
          json: async () => ({
            messages: [
              { role: "user", content: "买玩具" },
              { role: "assistant", content: "找到积木" },
            ],
          }),
        };
      }
      if (url === "/api/sessions/1" && (!init || init.method === "GET")) {
        return {
          ok: true,
          json: async () => ({
            sessions: [
              { id: 2, title: "买玩具" },
              { id: 1, title: "买化妆台和衣服" },
            ],
          }),
        };
      }
      if (url.startsWith("/api/context/")) {
        return { ok: true, json: async () => ({ context: "" }) };
      }
      if (url.endsWith("/query/stream")) {
        return {
          ok: true,
          body: {
            getReader: () => ({
              read: async () => ({ value: new TextEncoder().encode("data: [DONE]\n"), done: false }),
            }),
          },
          json: async () => ({}),
        };
      }
      return { ok: true, json: async () => ({ sessions: [] }) };
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("loads and continues a selected session", async () => {
    renderChatbox();
    fireEvent.click(screen.getAllByLabelText("History")[0]);
    fireEvent.click(await screen.findByText("买玩具"));
    expect(await screen.findByText("找到积木")).toBeTruthy();

    const input = await screen.findByPlaceholderText("Recipient, budget, taste, or Guizhou product…");
    fireEvent.change(input, { target: { value: "another toy" } });
    fireEvent.keyUp(input, { key: "Enter" });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).endsWith("/query/stream") &&
            JSON.parse(String(call[1]?.body)).session_id === 2
        )
      ).toBe(true)
    );
  });

  it("deletes a session from history", async () => {
    renderChatbox();
    fireEvent.click(screen.getAllByLabelText("History")[0]);
    fireEvent.click(await screen.findByLabelText("Delete 买玩具"));
    await waitFor(() => expect(screen.queryByText("买玩具")).toBeNull());
    expect(historyApi.deleteChatSession).toHaveBeenCalledWith(1, 2);
  });
});
