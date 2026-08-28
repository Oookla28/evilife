import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MascotSlot } from "@/components/mascot/MascotSlot";

describe("crisis mascot state", () => {
  it("uses companionship language instead of refusal language", () => {
    render(<MascotSlot state="care" />);

    expect(screen.getByAltText("是非题吉祥物正在陪着你")).toBeInTheDocument();
    expect(screen.queryByAltText("是非题吉祥物拒绝回答")).not.toBeInTheDocument();
  });
});
