export type AttachmentKind = "image" | "document";

export const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
export const DOCUMENT_MAX_BYTES = 20 * 1024 * 1024;

const IMAGE_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const DOCUMENT_MIME_TYPES = new Set([
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/rtf",
  "text/plain",
  "text/markdown",
]);
const IMAGE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "webp"]);
const DOCUMENT_EXTENSIONS = new Set(["pdf", "doc", "docx", "rtf", "txt", "md"]);

function extensionOf(file: File) {
  return file.name.split(".").pop()?.toLowerCase() ?? "";
}

export function getAttachmentKind(file: File): AttachmentKind | null {
  const extension = extensionOf(file);
  if (IMAGE_MIME_TYPES.has(file.type) || IMAGE_EXTENSIONS.has(extension)) {
    return "image";
  }
  if (DOCUMENT_MIME_TYPES.has(file.type) || DOCUMENT_EXTENSIONS.has(extension)) {
    return "document";
  }
  return null;
}

export function validateAttachment(file: File): string | null {
  const kind = getAttachmentKind(file);
  if (!kind) {
    return "仅支持 JPG、PNG、WebP、PDF、Word、RTF、TXT 或 Markdown 文件。";
  }
  if (kind === "image" && file.size > IMAGE_MAX_BYTES) {
    return "图片不能超过 10 MB。";
  }
  if (kind === "document" && file.size > DOCUMENT_MAX_BYTES) {
    return "文件不能超过 20 MB。";
  }
  return null;
}

export function filesFromClipboard(data: DataTransfer): File[] {
  const itemFiles = Array.from(data.items)
    .filter((item) => item.kind === "file")
    .map((item) => item.getAsFile())
    .filter((file): file is File => file !== null);
  return itemFiles.length > 0 ? itemFiles : Array.from(data.files);
}

export const ATTACHMENT_ACCEPT = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/rtf",
  "text/plain",
  "text/markdown",
  ".jpg",
  ".jpeg",
  ".png",
  ".webp",
  ".pdf",
  ".doc",
  ".docx",
  ".rtf",
  ".txt",
  ".md",
].join(",");
