import { describe, expect, it } from "vitest";
import {
  MAX_FONT_BYTES,
  formatFromFileName,
  validateFontFile,
} from "@/lib/fonts";

function fakeFile(name: string, size: number): File {
  return new File([new Uint8Array(size)], name);
}

describe("validateFontFile", () => {
  it("accepts woff2/woff/ttf/otf", () => {
    for (const name of ["a.woff2", "a.woff", "a.ttf", "a.otf"]) {
      expect(validateFontFile(fakeFile(name, 1024))).toBeNull();
    }
  });

  it("rejects unsupported extensions", () => {
    for (const name of ["a.exe", "a.pdf", "a.ttc", "a"]) {
      expect(validateFontFile(fakeFile(name, 1024))).not.toBeNull();
    }
  });

  it("accepts large CJK fonts up to 50MB and rejects larger files", () => {
    expect(validateFontFile(fakeFile("cjk.ttf", 32 * 1024 * 1024))).toBeNull();
    const problem = validateFontFile(
      fakeFile("big.woff2", MAX_FONT_BYTES + 1)
    );
    expect(problem).toContain("过大");
  });

  it("rejects empty files", () => {
    expect(validateFontFile(fakeFile("empty.woff2", 0))).not.toBeNull();
  });
});

describe("formatFromFileName", () => {
  it("maps extensions to css font formats", () => {
    expect(formatFromFileName("X.woff2")).toBe("woff2");
    expect(formatFromFileName("X.woff")).toBe("woff");
    expect(formatFromFileName("X.otf")).toBe("opentype");
    expect(formatFromFileName("X.ttf")).toBe("truetype");
    expect(formatFromFileName("X.WOFF2")).toBe("woff2"); // case-insensitive
  });
});
