import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatMessage from "./MessageItem";
import "../../i18n";

vi.mock("react-toastify", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe("ChatMessage marketing interactions", () => {
  it("does not mark ordinary budget mentions as refusals", () => {
    render(
      <ChatMessage
        role="assistant"
        content="You told me your budget is $80. Here are options that fit it; consider instead a versatile scarf."
        productName=""
      />
    );

    expect(screen.queryAllByText(/Your AI shopper says no/i)).toHaveLength(0);
  });

  it("renders example questions without first-run budget controls", () => {
    render(
      <ChatMessage
        role="assistant"
        content="Welcome"
        productName=""
        exampleQuestions={["Show me summer dresses", "Add a scarf to my cart"]}
      />
    );

    expect(screen.getAllByTestId("example-chip")).toHaveLength(2);
    expect(screen.queryByText("🛡️ Set my monthly budget")).toBeNull();
    expect(screen.queryByText("$50")).toBeNull();
  });

  it("renders shareable says-no bubbles for budget warnings", () => {
    const english = render(
      <ChatMessage
        role="assistant"
        content="Budget alert: both gowns exceed your stated monthly budget of $50.00."
        productName=""
      />
    );

    expect(
      english.getAllByText(/Your AI shopper says no/i).length
    ).toBeGreaterThan(0);
    expect(english.getByRole("button", { name: /share/i })).toBeTruthy();
    english.unmount();

    const chinese = render(
      <ChatMessage
        role="assistant"
        content="Budget alert: 这个价格太贵了，超过我的月预算了。"
        productName=""
      />
    );

    expect(
      chinese.getAllByText(/Your AI shopper says no/i).length
    ).toBeGreaterThan(0);
    expect(chinese.getByRole("button", { name: /share/i })).toBeTruthy();
  });

  it("marks explicit English and Chinese over-budget refusals", () => {
    const { unmount } = render(
      <ChatMessage
        role="assistant"
        content="At $240 this is too expensive, so I'd skip it for now."
        productName=""
      />
    );
    expect(
      screen.getAllByText(/Your AI shopper says no/i).length
    ).toBeGreaterThan(0);
    unmount();

    render(
      <ChatMessage
        role="assistant"
        content="这个价格超预算，建议不买，可以考虑替代。"
        productName=""
      />
    );
    expect(
      screen.getAllByText(/Your AI shopper says no/i).length
    ).toBeGreaterThan(0);
  });

  it("shares a product through the clipboard fallback", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(
      <ChatMessage
        role="image_row"
        content={[
          {
            productUrl: "/images/product.jpg",
            productName: "Silk Dress",
            externalUrl: "https://example.com/silk-dress",
            price: 49.99,
            rating: 4.8,
          },
        ]}
        productName=""
        onAddToCart={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /share silk dress/i }));

    await vi.waitFor(() => expect(writeText).toHaveBeenCalledOnce());
    expect(writeText.mock.calls[0][0]).toContain("Silk Dress");
  });

  it("keeps product add buttons disabled while a direct add is in flight", async () => {
    const onAddToCart = vi.fn(() => new Promise<void>(() => undefined));

    render(
      <ChatMessage
        role="image_row"
        content={[
          {
            productUrl: "/images/product.jpg",
            productName: "Silk Dress",
            externalUrl: "https://example.com/silk-dress",
            price: 49.99,
            rating: 4.8,
          },
        ]}
        productName=""
        onAddToCart={onAddToCart}
        cartAddInFlight
      />
    );

    const button = screen
      .getAllByRole("button", { name: /add to cart/i })
      .at(-1)!;
    expect(button.hasAttribute("disabled")).toBe(true);
    fireEvent.click(button);
    await waitFor(() => expect(onAddToCart).not.toHaveBeenCalled());
  });
});
