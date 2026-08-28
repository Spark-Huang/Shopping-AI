import { ImageContent } from "../types/chat";

export const FAVORITES_STORAGE_KEY = "shopping_favorites";

export const readFavorites = (): ImageContent[] => {
  try {
    const raw = localStorage.getItem(FAVORITES_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

export const toggleFavorite = (product: ImageContent): ImageContent[] => {
  const favorites = readFavorites();
  const exists = favorites.some(
    (item) => item.productName === product.productName
  );
  const next = exists
    ? favorites.filter((item) => item.productName !== product.productName)
    : [product, ...favorites];
  localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(next));
  return next;
};
