import { config } from "../config/appConfig";
import type { OrderData, OrdersResponse } from "../types/orders";

export const fetchOrders = async (userId: number): Promise<OrdersResponse> => {
  const response = await fetch(`${config.api.baseUrl}/orders/${userId}`);
  if (!response.ok) {
    throw new Error(`Orders fetch failed: HTTP ${response.status}`);
  }
  return (await response.json()) as OrdersResponse;
};

export const markPurchased = async (
  userId: number,
  order: { item: string; price?: number | null; note?: string }
): Promise<OrderData> => {
  const response = await fetch(`${config.api.baseUrl}/orders/${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(order),
  });
  if (!response.ok) {
    throw new Error(`Mark purchased failed: HTTP ${response.status}`);
  }
  return ((await response.json()) as { order: OrderData }).order;
};
