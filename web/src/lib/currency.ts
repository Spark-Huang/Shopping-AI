const cnyFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** All catalog amounts are reference prices in Chinese yuan. */
export const formatCny = (value: number): string => cnyFormatter.format(value);
