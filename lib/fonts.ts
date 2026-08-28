"use client";

/**
 * Custom global font management (Settings -> 字体上传).
 *
 * The uploaded font is stored in localStorage as a base64 data URL (woff/woff2
 * are typically small enough for localStorage. Larger CJK fonts may exceed
 * the browser quota: they still apply for the current session, while
 * persistence gracefully falls back to requiring a new selection on reload.
 * A <style> block injects the @font-face, and the body's font-family is
 * overridden so every page element inherits the custom face.
 */

export const FONT_STORAGE_KEY = "evilife_custom_font_v1";
export const FONT_FACE_ID = "evilife-custom-font-face";
export const FONT_FAMILY = "EviLifeCustom";
export const MAX_FONT_BYTES = 50 * 1024 * 1024; // 50 MB

const ALLOWED_EXTENSIONS = [".woff2", ".woff", ".ttf", ".otf"];

export interface CustomFontState {
  name: string;
  dataUrl: string;
  format: string;
  appliedAt: string;
}

export function validateFontFile(file: File): string | null {
  const lower = file.name.toLowerCase();
  const hasAllowedExt = ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
  if (!hasAllowedExt) {
    return "仅支持 woff2 / woff / ttf / otf 格式的字体文件。";
  }
  if (file.size > MAX_FONT_BYTES) {
    return "字体文件过大（超过 50 MB），请压缩后再上传。";
  }
  if (file.size === 0) {
    return "字体文件为空。";
  }
  return null;
}

export function formatFromFileName(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".woff2")) return "woff2";
  if (lower.endsWith(".woff")) return "woff";
  if (lower.endsWith(".otf")) return "opentype";
  return "truetype";
}

export function readFontAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("读取字体文件失败"));
    reader.readAsDataURL(file);
  });
}

export function getStoredFont(): CustomFontState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(FONT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CustomFontState;
    if (!parsed?.dataUrl || !parsed?.name) return null;
    return parsed;
  } catch {
    return null;
  }
}

function ensureFontFaceStyle(): HTMLStyleElement | null {
  if (typeof document === "undefined") return null;
  let style = document.getElementById(FONT_FACE_ID) as HTMLStyleElement | null;
  if (!style) {
    style = document.createElement("style");
    style.id = FONT_FACE_ID;
    document.head.appendChild(style);
  }
  return style;
}

export function applyCustomFont(font: CustomFontState): void {
  const style = ensureFontFaceStyle();
  if (!style || typeof document === "undefined") return;
  style.textContent = `@font-face {
  font-family: '${FONT_FAMILY}';
  src: url(${font.dataUrl}) format('${font.format}');
  font-display: swap;
}`;
  document.body.style.fontFamily = `'${FONT_FAMILY}', var(--font-inter), var(--font-noto-sans-sc), "Microsoft YaHei", system-ui, sans-serif`;
  try {
    localStorage.setItem(FONT_STORAGE_KEY, JSON.stringify(font));
  } catch {
    // Quota exceeded: apply for this session but skip persistence.
  }
}

export function clearCustomFont(): void {
  if (typeof document !== "undefined") {
    document.getElementById(FONT_FACE_ID)?.remove();
    document.body.style.fontFamily = "";
  }
  try {
    localStorage.removeItem(FONT_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function initCustomFont(): void {
  const stored = getStoredFont();
  if (stored) applyCustomFont(stored);
}
