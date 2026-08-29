export interface CartItemData {
  item: string;
  amount: number;
  price: number | null;
  url?: string | null;
  image?: string | null;
}

export interface CartResponse {
  user_id: number;
  cart: CartItemData[];
}
