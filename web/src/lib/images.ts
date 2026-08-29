import { ImageContent, ProductInfo } from "../types/chat";

export type ProductPayload = Record<string, string | ProductInfo>;

export const parseImagesPayload = (
  payload: ProductPayload
): ImageContent[] => {
  return Object.entries(payload)
    .map(([productName, info]) => {
      if (typeof info === "string") {
        return { productUrl: info, productName };
      }

      const entry: ImageContent = {
        productUrl: info.image || "",
        productName,
      };
      if (info.url) entry.externalUrl = info.url;
      if (typeof info.price === "number") entry.price = info.price;
      if (typeof info.currency === "string") entry.currency = info.currency;
      if (typeof info.rating === "number") entry.rating = info.rating;
      return entry;
    })
    .filter((entry) => Boolean(entry.productUrl));
};
