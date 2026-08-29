/**
 * Product catalog API for showcase pages (e.g. Guizhou specialties).
 */

import { config } from "../config/appConfig";
import { authFetch } from "../lib/auth";
import { CatalogProduct, ProductsResponse } from "../types/product";

/**
 * Fetch catalog products, optionally filtered by category (e.g. "guizhou").
 * Throws on network / HTTP errors so callers can render an error state.
 */
export const fetchProducts = async (
  category?: string
): Promise<CatalogProduct[]> => {
  const url = category
    ? `${config.api.baseUrl}/products?category=${encodeURIComponent(category)}`
    : `${config.api.baseUrl}/products`;
  const response = await authFetch(url);
  if (!response.ok) {
    throw new Error(`Products fetch failed: HTTP ${response.status}`);
  }
  const data = (await response.json()) as Partial<ProductsResponse>;
  return Array.isArray(data.products) ? data.products : [];
};
