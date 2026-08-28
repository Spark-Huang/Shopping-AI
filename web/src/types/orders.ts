export interface OrderData {
  id: number;
  item: string;
  price: number | null;
  purchased_at: string | null;
  note?: string | null;
}

export interface OrdersResponse {
  user_id: number;
  orders: OrderData[];
}

export interface HistoryResponse {
  user_id: number;
  context: string;
}
