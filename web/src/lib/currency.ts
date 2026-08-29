const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: "¥",
  USD: "$",
  EUR: "€",
  GBP: "£",
  JPY: "¥",
};

const cnyFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** All catalog amounts are reference prices in Chinese yuan. */
export const formatCny = (value: number): string => cnyFormatter.format(value);

export const currencySymbol = (currency: string): string =>
  CURRENCY_SYMBOLS[currency.toUpperCase()] ?? "";

/** Format a price with the symbol of its currency code (falls back to CNY). */
export const formatPrice = (value: number, currency?: string): string => {
  if (!currency || currency.toUpperCase() === "CNY") {
    return formatCny(value);
  }
  return `${currencySymbol(currency)}${value.toFixed(2)}`;
};
