import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MePage from "./MePage";
import "../../i18n";

afterEach(cleanup);

describe("Me page safety toggle", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("updates the first-screen hint and requests the disabled state", () => {
    const onChange = vi.fn();
    render(
      <MePage
        onSafetyChange={onChange}
        safetyEnabled={true}
        onAddToCart={undefined}
        onOrderChange={undefined}
      />
    );

    expect(
      screen.getByText(/A mandatory high-risk blocklist always remains active/i)
    ).toBeTruthy();
    fireEvent.click(screen.getByTestId("safety-switch"));

    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("shows the off-state hint while the mandatory baseline remains active", () => {
    render(
      <MePage safetyEnabled={false} onSafetyChange={vi.fn()} />
    );

    expect(
      screen.getByText(/A mandatory high-risk blocklist still blocks/i)
    ).toBeTruthy();
  });
});
