import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import OrdersPage from "./OrdersPage";
import "../../i18n";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

afterEach(cleanup);

describe("OrdersPage budget comparison", () => {
  it("renders the empty state after user 1 data is cleared", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/orders/1")) {
        return { ok: true, json: async () => ({ orders: [] }) };
      }
      return { ok: true, json: async () => ({ context: "" }) };
    });

    render(<OrdersPage refreshSignal={0} onBack={vi.fn()} />);

    expect(await screen.findByRole("status")).toBeTruthy();
    expect(screen.getByText("No orders yet")).toBeTruthy();
  });

  it("renders the monthly progress bar from persisted context", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/orders/1")) {
        return {
          ok: true,
          json: async () => ({
            orders: [
              {
                id: 1,
                item: "Silk Dress",
                price: 69.99,
                purchased_at: new Date().toISOString(),
              },
            ],
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({ context: "MONTHLY BUDGET: $50.00" }),
      };
    });

    render(<OrdersPage refreshSignal={0} onBack={vi.fn()} />);

    expect(await screen.findByTestId("orders-budget")).toBeTruthy();
    expect(screen.getByText("CNY ¥19.99 over")).toBeTruthy();
    expect(screen.getByRole("progressbar")).toBeTruthy();
  });

  it("uses the latest persisted monthly budget", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/context/")) {
        return {
          ok: true,
          json: async () => ({
            context:
              "MONTHLY BUDGET: $25.00 Other history MONTHLY BUDGET: $50.00",
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          orders: [
            {
              id: 1,
              item: "Silk Dress",
              price: 69.99,
              purchased_at: new Date().toISOString(),
            },
          ],
        }),
      };
    });

    render(<OrdersPage refreshSignal={0} onBack={vi.fn()} />);

    expect(
      await screen.findByText("Budget CNY ¥50.00 — spent ¥69.99")
    ).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuemax")).toBe(
      "50"
    );
  });
});

describe("OrdersPage fetch errors", () => {
  it("renders the backend error state", async () => {
    fetchMock.mockImplementation(async () => ({ ok: false, status: 502 }));

    render(<OrdersPage refreshSignal={0} onBack={vi.fn()} />);

    expect(await screen.findByText("Could not load orders.")).toBeTruthy();
  });
});
