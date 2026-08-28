const createMonthlyBudgetPattern = () =>
  /(?:monthly\s+budget|月预算|每月预算)\D*?(\d+(?:\.\d+)?)/i;

export const parseMonthlyBudget = (context: string): number | null => {
  const matches = context.match(
    new RegExp(createMonthlyBudgetPattern().source, "gi")
  );
  if (!matches) return null;
  const latest = matches[matches.length - 1];
  const match = latest.match(createMonthlyBudgetPattern());
  if (!match) return null;
  const budget = Number(match[1]);
  return Number.isFinite(budget) && budget > 0 ? budget : null;
};

export const formatMonthlyBudget = (budget: number): string =>
  `MONTHLY BUDGET: $${budget.toFixed(2)}`;

export const replaceMonthlyBudget = (
  context: string,
  budget: number
): string => {
  const budgetLine = formatMonthlyBudget(budget);
  if (!context.trim()) return budgetLine;
  return createMonthlyBudgetPattern().test(context)
    ? context.replace(
        new RegExp(createMonthlyBudgetPattern().source, "gi"),
        budgetLine
      )
    : `${context.trimEnd()} ${budgetLine}`;
};
