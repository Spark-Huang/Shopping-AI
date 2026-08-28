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
