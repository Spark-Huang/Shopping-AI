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

describe("CartPanel multi-select checkout", () => {
  it("checks out the selected lines in one request and refreshes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        ok({
          cart: [
            { item: "Silk Dress", amount: 2, price: 49.99 },
            { item: "Lao Gan Ma Chili Crisp", amount: 1, price: 9 },
          ],
        })
      )
      .mockResolvedValueOnce(ok({ message: "checked out" }))
      .mockResolvedValueOnce(ok({ cart: [] }));
    vi.stubGlobal("fetch", fetchMock);

    render(<CartPanel refreshSignal={0} onOrderChange={vi.fn()} />);

    // Select both lines, then hit the checkout button.
    fireEvent.click(
      await screen.findByRole("button", { name: /toggle selection for silk dress/i })
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /toggle selection for lao gan ma chili crisp/i,
      })
    );
    fireEvent.click(
      screen.getByRole("button", { name: /^checkout \(3 · cny ¥108\.98\)$/i })
    );

    await waitFor(() =>
      expect(toastMock.success).toHaveBeenCalledWith(
        "Checkout complete: 3 item(s) moved to orders ✓"
      )
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/cart/1/checkout",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          items: [
            { item: "Silk Dress", price: 49.99 },
            { item: "Lao Gan Ma Chili Crisp", price: 9 },
          ],
        }),
      })
    );
  });
});

describe("CartPanel item deletion", () => {
  it("removes the whole line when the delete button is pressed", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        ok({ cart: [{ item: "Silk Dress", amount: 2, price: 49.99 }] })
      )
      .mockResolvedValueOnce(ok({}))
      .mockResolvedValueOnce(ok({ cart: [] }));
    vi.stubGlobal("fetch", fetchMock);

    render(<CartPanel refreshSignal={0} />);

    fireEvent.click(
      await screen.findByRole("button", { name: /delete silk dress/i })
    );

    await waitFor(() =>
      expect(toastMock.success).toHaveBeenCalledWith(
        "🗑️ Removed Silk Dress from cart"
      )
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/cart/1/remove",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ item: "Silk Dress", amount: 2 }),
      })
    );
  });
});

describe("CartPanel quantity stepper", () => {
  it("sets the new absolute quantity through the cart add endpoint", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        ok({ cart: [{ item: "Silk Dress", amount: 2, price: 49.99 }] })
      )
      .mockResolvedValueOnce(ok({}))
      .mockResolvedValueOnce(
        ok({ cart: [{ item: "Silk Dress", amount: 3, price: 49.99 }] })
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<CartPanel refreshSignal={0} />);

    fireEvent.click(
      await screen.findByRole("button", { name: /increase quantity of silk dress/i })
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "/api/cart/1",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            item: "Silk Dress",
            amount: 3,
            price: 49.99,
            url: "",
            idempotent: true,
          }),
        })
      )
    );
  });
});

describe("CartPanel sharing", () => {
  it("copies the cart through the execCommand fallback over HTTP", async () => {
    // The module-level toast mock keeps its call history across tests in
    // this file; clear it so the once-assertion below is meaningful.
    toastMock.success.mockClear();
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
