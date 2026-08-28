import { describe, expect, it } from "vitest";
import {
  formatMonthlyBudget,
  parseMonthlyBudget,
  replaceMonthlyBudget,
} from "./budget";

describe("monthly budget helpers", () => {
  it.each([
    ["", null],
    ["No preference stored", null],
    ["MONTHLY BUDGET: $50.00", 50],
    ["earlier $25 monthly budget; latest MONTHLY BUDGET: $75.50", 75.5],
    ["每月预算：500", 500],
  ])("parses %s as %s", (context, expected) => {
    expect(parseMonthlyBudget(context)).toBe(expected);
  });

  it("appends the first budget and replaces later budget values", () => {
    expect(replaceMonthlyBudget("Chat history", 75)).toBe(
      `Chat history ${formatMonthlyBudget(75)}`
    );
    expect(
      replaceMonthlyBudget(
        "Earlier MONTHLY BUDGET: $25.00 and chat history",
        75
      )
    ).toBe(`Earlier ${formatMonthlyBudget(75)} and chat history`);
  });
});
