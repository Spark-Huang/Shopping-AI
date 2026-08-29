export interface CatalogProduct {
  category: string;
  subcategory: string;
  name: string;
  description: string;
  url: string;
  price: number;
  image: string;
  /** Cultural / intangible-heritage story for showcase products. */
  story?: string;
  /** Catalog provenance and transparency fields. */
  sourceName?: string;
  sourceUrl?: string;
  verifiedAt?: string;
  imageType?: "illustration" | "merchant-photo";
}

export interface ProductsResponse {
  products: CatalogProduct[];
}
