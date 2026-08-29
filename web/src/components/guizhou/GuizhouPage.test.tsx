import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import GuizhouPage, { FILTER_SUBCATEGORIES } from "./GuizhouPage";
import { CatalogProduct } from "../../types/product";
import "../../i18n";

vi.mock("react-toastify", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const products: CatalogProduct[] = [
  {
    category: "guizhou",
    subcategory: "苗银",
    name: "苗族流苏耳饰",
    description: "苗银耳饰",
    url: "https://example.com/silver",
    price: 35,
    image: "https://example.com/silver.jpg",
  },
  {
    category: "guizhou",
    subcategory: "酱香白酒",
    name: "贵州酱香酒",
    description: "酱香型白酒",
    url: "https://example.com/liquor",
    price: 128,
    image: "https://example.com/liquor.jpg",
  },
];

describe("GuizhouPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    cleanup();
  });

  it("maps the four discovery filters to source subcategories", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ products }),
      })
    );

    render(<GuizhouPage />);
    await waitFor(() => screen.getAllByText("苗族流苏耳饰"));
    expect(screen.getAllByText("贵州酱香酒").length).toBeGreaterThan(0);
  });
});

describe("GuizhouPage category mapping", () => {
  it("maps every filter tab to the expected source subcategories", () => {
    expect(FILTER_SUBCATEGORIES["ethnic-wear"]).toContain("苗银");
    expect(FILTER_SUBCATEGORIES.craft).toEqual(["苗银", "蜡染", "苗绣"]);
    expect(FILTER_SUBCATEGORIES.food).toContain("酸汤底料");
    expect(FILTER_SUBCATEGORIES.drink).toContain("酱香白酒");
  });
});
