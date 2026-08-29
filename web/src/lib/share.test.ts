import { describe, expect, it, vi } from "vitest";
import { toast } from "react-toastify";
import { isSaysNo, shareText } from "./share";

vi.mock("react-toastify", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe("share utilities", () => {
  it("uses execCommand when the clipboard API is unavailable", async () => {
    const execCommand = vi.fn(() => true);
    vi.stubGlobal("navigator", Object.assign(navigator, { clipboard: {} }));
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await shareText("cart text", "Copied", "Copy failed");

    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(toast.success).toHaveBeenCalledWith("Copied");
  });

  it.each([
    ["You told me your budget is $80; consider instead a scarf.", false],
    ["At $240 this is too expensive, so I'd skip it for now.", true],
    ["This is above your budget.", true],
    [
      "Budget alert: both gowns exceed your stated monthly budget of $50.00.",
      true,
    ],
    ["all of these exceed the stated budget", true],
    ["The item is above your stated budget.", true],
    ["Would you like to try a different approach and widen the price range?", false],
    ["No matching summer dresses under $150 were found.", false],
    ["This is over budget, so I recommend not buying it.", false],
    ["That is too expensive; skip it for now.", true],
    ["这个价格超预算，建议不买，可以考虑替代。", true],
    ["这个价格太贵了，超过我的月预算了", true],
    ["这个选择超出你的月度预算", true],
    ["要不要换个方式试试？放宽价格范围", false],
    ["没有找到符合条件的夏季连衣裙（$150以下）", false],
    ["超预算了，建议不买", true],
    ["太贵了，换一个更便宜的选择吧", true],
  ])("classifies %s as %s", (message, expected) => {
    expect(isSaysNo(message)).toBe(expected);
  });
});
