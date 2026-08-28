import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CartPanel from "./CartPanel";
import "../../i18n";

const toastMock = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
}));

vi.mock("react-toastify", () => ({
  toast: toastMock,
}));

const ok = (body: unknown) => ({
  ok: true,
  json: async () => body,
});

describe("CartPanel purchased cart sync", () => {
  it("marks the order, removes the cart line, and shows the synced toast", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        ok({
          cart: [{ item: "Silk Dress", amount: 2, price: 49.99 }],
        })
      )
      .mockResolvedValueOnce(ok({}))
      .mockResolvedValueOnce(ok({}));
    vi.stubGlobal("fetch", fetchMock);

    render(<CartPanel refreshSignal={0} onOrderChange={vi.fn()} />);

    fireEvent.click(
      await screen.findByRole("button", { name: /mark as bought/i })
    );

    await waitFor(() =>
      expect(toastMock.success).toHaveBeenCalledWith("Moved to Orders ✓")
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/orders/1",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/cart/1/remove",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ item: "Silk Dress", amount: 2 }),
      })
    );
  });
});

describe("CartPanel sharing", () => {
  it("copies the cart through the execCommand fallback over HTTP", async () => {
    const writeText = vi.fn();
    const execCommand = vi.fn(() => true);
    vi.stubGlobal("navigator", Object.assign(navigator, { clipboard: {} }));
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });
    const fetchMock = vi.fn().mockResolvedValue(
      ok({
        cart: [{ item: "Silk Dress", amount: 1, price: 49.99 }],
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<CartPanel refreshSignal={0} />);

    fireEvent.click(
      await screen.findByRole("button", { name: /share my list/i })
    );

    await waitFor(() => expect(toastMock.success).toHaveBeenCalledOnce());
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(toastMock.success).toHaveBeenCalledWith("Copied to clipboard");
  });
});
