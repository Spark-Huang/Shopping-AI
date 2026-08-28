import React from "react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import Chatbox from "./ChatWindow";

vi.mock("react-toastify", () => ({
  toast: { info: vi.fn(), success: vi.fn(), error: vi.fn() },
}));

const currentUserId = "1";
const requestHistory = vi.fn();
const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);
Element.prototype.scrollIntoView = vi.fn();

const renderChatbox = () =>
  render(
    <Chatbox
      visible={true}
      safetyEnabled={true}
      onSafetyChange={vi.fn()}
    />
  );

const finishWelcomeTypewriter = async () => {
  for (let elapsed = 0; elapsed < 4000; elapsed += 100) {
    await vi.advanceTimersByTimeAsync(100);
    if (
      screen.queryAllByTestId("budget-form").length > 0 &&
      screen.queryAllByTestId("example-chip").length === 5
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
    localStorage.setItem("shopping_user_id", "123456789");
    requestHistory.mockReset();
    fetchMock.mockReset();
    fetchMock.mockImplementation(requestHistory);
  });

  afterEach(() => {
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

      expect(requestHistory).toHaveBeenCalledTimes(1);
      expect(String(requestHistory.mock.calls[0][0])).toBe(
        `/api/context/${currentUserId}`
      );
      if (shouldReplayHistory) {
        expect(
          screen.getAllByText("Previous recommendation").length
        ).toBeGreaterThan(0);
      } else {
        await finishWelcomeTypewriter();
        expect(
          screen.getByText(
            "Welcome 👋 Set a monthly spending limit before you browse, or jump straight in."
          )
        ).toBeTruthy();
        expect(screen.getAllByTestId("budget-form").length).toBeGreaterThan(0);
        expect(screen.getAllByTestId("example-chip")).toHaveLength(5);
        expect(screen.getAllByText("🛡️ Set my monthly budget")[0]).toBeTruthy();
        expect(screen.getAllByText("Browse dresses")[0]).toBeTruthy();
      }
      expect(localStorage.getItem("shopping_user_id")).toBe(currentUserId);
      expect(sessionStorage.getItem("shopping_user_id")).toBeNull();
    }
  );

  it("clears the persistent and legacy user id only on explicit reset", async () => {
    sessionStorage.setItem("shopping_user_id", currentUserId);
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

    expect(localStorage.getItem("shopping_user_id")).toBe(currentUserId);
    expect(sessionStorage.getItem("shopping_user_id")).toBeNull();
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

  it("does not append a duplicate monthly budget line", async () => {
    requestHistory.mockResolvedValue({
      ok: true,
      json: async () => ({
        context: "",
      }),
    });
    const view = renderChatbox();
    await finishWelcomeTypewriter();

    requestHistory.mockClear();
    requestHistory.mockResolvedValue({
      ok: true,
      json: async () => ({
        context: "Earlier recommendation MONTHLY BUDGET: $50.00",
      }),
    });
    fireEvent.click(screen.getAllByRole("button", { name: "$50" })[0]);

    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);
    expect(requestHistory).toHaveBeenCalledTimes(1);
    expect(String(requestHistory.mock.calls[0][0])).toBe("/api/context/1");
    expect(requestHistory.mock.calls[0][1]?.method).toBeUndefined();
    view.unmount();
  });
});
