import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Composer } from "@/components/composer/Composer";


describe("Composer clipboard attachments", () => {
  afterEach(cleanup);
  beforeEach(() => {
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:preview"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
  });

  it("pastes a clipboard image and submits the original File", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} />);
    const image = new File(["image"], "clipboard-shot.png", { type: "image/png" });

    fireEvent.paste(screen.getByRole("textbox", { name: "问题" }), {
      clipboardData: {
        items: [{ kind: "file", getAsFile: () => image }],
        files: [image],
      },
    });

    expect(screen.getByText("clipboard-shot.png")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("发送"));
    expect(onSend).toHaveBeenCalledWith("", image);
  });

  it("uses clipboardData.files for copied documents", () => {
    render(<Composer />);
    const document = new File(["report"], "evidence-report.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    fireEvent.paste(screen.getByRole("textbox", { name: "问题" }), {
      clipboardData: { items: [], files: [document] },
    });

    expect(screen.getByText("evidence-report.docx")).toBeInTheDocument();
  });

  it("keeps pasted plain text behavior and rejects unsupported files", () => {
    render(<Composer />);
    const textbox = screen.getByRole("textbox", { name: "问题" });
    fireEvent.paste(textbox, {
      clipboardData: { items: [], files: [] },
    });
    expect(textbox).toHaveValue("");

    const archive = new File(["zip"], "records.zip", { type: "application/zip" });
    fireEvent.paste(textbox, {
      clipboardData: {
        items: [{ kind: "file", getAsFile: () => archive }],
        files: [archive],
      },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("仅支持 JPG");
  });
});
