/**
 * Cart operations proxied through the orchestrator API.
 */

import { config } from "../config/appConfig";
import { authFetch } from "../lib/auth";
import { CartResponse } from "../types/cart";
import { ImageContent } from "../types/chat";

/**
 * Fetch the cart for the given user id.
 * Throws on network / HTTP errors so callers can render an error state.
 */
export const fetchCart = async (userId: number): Promise<CartResponse> => {
  const url = `${config.api.baseUrl}/cart/${userId}`;
  const response = await authFetch(url);
  if (!response.ok) {
    throw new Error(`Cart fetch failed: HTTP ${response.status}`);
  }
  return (await response.json()) as CartResponse;
};

/** Add a displayed catalog product directly without a full agent turn. */
export const addCartProduct = async (
  userId: number,
  product: ImageContent
): Promise<void> => {
  const response = await authFetch(`${config.api.baseUrl}/cart/${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      item: product.productName,
      amount: 1,
      price: product.price ?? null,
      url:
        product.externalUrl &&
        product.externalUrl.startsWith("https://")
          ? product.externalUrl
          : "",
    }),
  });
  if (!response.ok) {
    throw new Error(`Cart add failed: HTTP ${response.status}`);
  }
};

/** Remove one or more units of a cart line after an external purchase. */
export const removeCartProduct = async (
  userId: number,
  item: string,
  amount = 1
): Promise<void> => {
  const response = await authFetch(`${config.api.baseUrl}/cart/${userId}/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item, amount }),
  });
  if (!response.ok) {
    throw new Error(`Cart remove failed: HTTP ${response.status}`);
  }
};
