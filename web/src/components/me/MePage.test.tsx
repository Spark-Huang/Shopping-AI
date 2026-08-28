import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MePage from "./MePage";
import "../../i18n";

afterEach(cleanup);

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

describe("Me page safety toggle", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("updates the first-screen hint and requests the disabled state", () => {
    const onChange = vi.fn();
    render(
      <MePage
        onSafetyChange={onChange}
        safetyEnabled={true}
        onAddToCart={undefined}
        onOrderChange={undefined}
      />
    );

    expect(
      screen.getByText(/A mandatory high-risk blocklist always remains active/i)
    ).toBeTruthy();
    fireEvent.click(screen.getByTestId("safety-switch"));

    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("shows the off-state hint while the mandatory baseline remains active", () => {
    render(<MePage safetyEnabled={false} onSafetyChange={vi.fn()} />);

    expect(
      screen.getByText(/A mandatory high-risk blocklist still blocks/i)
    ).toBeTruthy();
  });

  it("loads and saves the optional monthly budget", async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/context/")) {
        return {
          ok: true,
          json: async () => ({
            context:
              fetchMock.mock.calls.filter(([url]) =>
                String(url).includes("/context/")
              ).length > 1
                ? "Earlier recommendation MONTHLY BUDGET: $75.00"
                : "Earlier recommendation",
          }),
        };
      }
      return { ok: true, json: async () => ({}) };
    });

    render(<MePage safetyEnabled={true} onSafetyChange={vi.fn()} />);

    expect(await screen.findByText("Not set")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Monthly budget"), {
      target: { value: "75" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save budget" }));

    await waitFor(() => expect(screen.getByText("$75.00")).toBeTruthy());
    const posts = fetchMock.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST"
    );
    expect(posts).toHaveLength(1);
    expect((posts[0][1] as { body: string }).body).toBe(
      JSON.stringify({
        new_context: "Earlier recommendation MONTHLY BUDGET: $75.00",
      })
    );
  });
});
