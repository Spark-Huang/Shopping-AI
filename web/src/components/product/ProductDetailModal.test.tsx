import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductDetailModal from "./ProductDetailModal";
import { CatalogProduct } from "../../types/product";
import "../../i18n";

vi.mock("react-toastify", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const product: CatalogProduct = {
  category: "guizhou",
  subcategory: "ethnic-wear",
  name: "苗银凤冠",
  description: "黔东南苗族节庆银冠，银匠全手工錾刻。",
  url: "https://search.jd.com/Search?keyword=苗银凤冠",
  price: 288,
  image: "/images/products/guizhou/miao-silver-phoenix-crown.png",
  story: "苗银锻造技艺是国家级非物质文化遗产。",
  sourceName: "贵州省文旅公开资料",
  sourceUrl: "https://www.mct.gov.cn/whzx/qgwhxxlb/gz/201811/t20181129_836276.htm",
  verifiedAt: "2026-08-29",
  imageType: "illustration",
};

describe("ProductDetailModal", () => {
  it("renders the product details with JD and Taobao buy links", () => {
    render(<ProductDetailModal product={product} onClose={vi.fn()} />);

    expect(screen.getByText("苗银凤冠")).toBeTruthy();
    // The price shows both in the price line and the specifications table.
    expect(screen.getAllByText("¥288.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Origin and culture")).toBeTruthy();
    expect(
      screen.getByText("苗银锻造技艺是国家级非物质文化遗产。")
    ).toBeTruthy();

    const jdLink = screen.getByRole("link", { name: /buy on jd\.com/i });
    expect(jdLink.getAttribute("href")).toBe(
      "https://search.jd.com/Search?keyword=苗银凤冠"
    );
    expect(jdLink.getAttribute("target")).toBe("_blank");
    expect(jdLink.getAttribute("rel")).toBe("noopener noreferrer");

    const taobaoLink = screen.getByRole("link", { name: /buy on taobao/i });
    expect(taobaoLink.getAttribute("href")).toBe(
      `https://s.taobao.com/search?q=${encodeURIComponent("苗银凤冠")}`
    );
    expect(taobaoLink.getAttribute("target")).toBe("_blank");
  });

  it("closes through the close button, the overlay and Escape", () => {
    const onClose = vi.fn();
    render(<ProductDetailModal product={product} onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId("product-detail-overlay"));
    expect(onClose).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("does not close when clicking inside the modal body", () => {
    const onClose = vi.fn();
    render(<ProductDetailModal product={product} onClose={onClose} />);

    fireEvent.click(screen.getByText("苗银凤冠"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("adds the product to the cart through the orchestrator API", async () => {
    const onCartChange = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ProductDetailModal
        product={product}
        onClose={vi.fn()}
        onCartChange={onCartChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /add to cart/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/cart/1",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          item: "苗银凤冠",
          amount: 1,
          price: 288,
          url: "https://search.jd.com/Search?keyword=苗银凤冠",
        }),
      })
    );
    await waitFor(() => expect(onCartChange).toHaveBeenCalledOnce());
  });

  it("renders the specifications table with mapped category labels", () => {
    render(<ProductDetailModal product={product} onClose={vi.fn()} />);

    expect(screen.getByText("Specifications")).toBeTruthy();
    expect(screen.getByText("Category")).toBeTruthy();
    expect(screen.getByText("Guizhou specialties")).toBeTruthy();
    expect(screen.getByText("Subcategory")).toBeTruthy();
    expect(screen.getByText("Ethnic Wear")).toBeTruthy();
    expect(screen.getByText("Source")).toBeTruthy();
    expect(screen.getByText("search.jd.com")).toBeTruthy();
  });

  it("hides the specifications section when no field has data", () => {
    render(
      <ProductDetailModal
        product={{
          ...product,
          category: "",
          subcategory: "",
          url: "",
          price: 0,
        }}
        onClose={vi.fn()}
      />
    );

    expect(screen.queryByText("Specifications")).toBeNull();
    expect(screen.queryByText("Category")).toBeNull();
    expect(screen.queryByText("Subcategory")).toBeNull();
    expect(screen.queryByText("Source")).toBeNull();
  });

  it("shows provenance and purchase checks instead of fabricated reviews", () => {
    render(<ProductDetailModal product={product} onClose={vi.fn()} />);

    expect(screen.getByText("Information verification")).toBeTruthy();
    expect(screen.getByText(/Catalog reviewed on 2026-08-29/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "贵州省文旅公开资料" })).toBeTruthy();
    expect(screen.getByText("Check before purchase")).toBeTruthy();
    expect(screen.queryByText("Customer reviews")).toBeNull();
  });
});
