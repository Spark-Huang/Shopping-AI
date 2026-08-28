import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { SAFETY_STORAGE_KEY } from "./safetyToggle";
import "./i18n";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App safety state", () => {
  beforeEach(() => {
    localStorage.clear();
    // Seed a session so the login gate renders the app shell, not AuthPage.
    localStorage.setItem(
      "shopping_auth_user",
      JSON.stringify({ id: 1, username: "alice" })
    );
    localStorage.setItem("shopping_auth_token", "test-token");
  });

  it("persists the Me-page toggle", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ context: "" }),
      })
    );
    render(<App />);

    fireEvent.click(screen.getByTestId("tab-me"));
    fireEvent.click(screen.getByTestId("safety-switch"));

    expect(localStorage.getItem(SAFETY_STORAGE_KEY)).toBe("false");
  });
});
