"use client";

import {
  useState,
  useRef,
  useEffect,
  type ClipboardEvent,
  type DragEvent,
  type ChangeEvent,
} from "react";
import { ArrowUp, Paperclip, X, Image as ImageIcon, FileText, Loader2, StopCircle, ShieldAlert } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ATTACHMENT_ACCEPT,
  filesFromClipboard,
  getAttachmentKind,
  validateAttachment,
} from "@/lib/attachments";

export type ComposerState = "default" | "inputting" | "sending" | "streaming" | "error" | "disabled";

interface ComposerProps {
  onSend?: (text: string, file: File | null) => void;
  onStop?: () => void;
  state?: ComposerState;
  errorMessage?: string;
  responseMode?: "life" | "professional";
}

export function Composer({ onSend, onStop, state = "default", errorMessage, responseMode = "life" }: ComposerProps) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 192)}px`;
    }
  }, [text]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (state === "sending" || state === "streaming" || state === "disabled") return;
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (state === "sending" || state === "streaming" || state === "disabled") return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      handleFileSelection(droppedFile);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelection(e.target.files[0]);
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
    if (state === "sending" || state === "streaming" || state === "disabled") return;
    const pastedFiles = filesFromClipboard(event.clipboardData);
    if (pastedFiles.length === 0) return;
    event.preventDefault();
    handleFileSelection(pastedFiles[0]);
  };

  const handleFileSelection = (selectedFile: File) => {
    const validationError = validateAttachment(selectedFile);
    if (validationError) {
      setFileError(validationError);
    } else {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setFile(selectedFile);
      setPreviewUrl(
        getAttachmentKind(selectedFile) === "image"
          ? URL.createObjectURL(selectedFile)
          : null
      );
      setFileError("");
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeFile = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
    setFileError("");
  };

  const handleSend = () => {
    if ((text.trim() || file) && onSend && state !== "sending" && state !== "streaming") {
      onSend(text, file);
      setText("");
      setFile(null);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isSending = state === "sending";
  const isStreaming = state === "streaming";
  const isDisabled = state === "disabled" || isSending || isStreaming;
  const showStop = isSending || isStreaming;

  return (
    <div className="w-full relative">
      <div 
        className={`bg-white border rounded-2xl shadow-sm p-3 flex flex-col gap-2 transition-all ${
          isDragging ? "border-brand bg-brand/5" : 
          state === "error" ? "border-risk-refused" : 
          isDisabled ? "bg-bg-page/40 border-border-divider/70" : "border-border-divider"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onPaste={handlePaste}
      >
        <AnimatePresence>
          {file && (
            <motion.div 
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="px-2 pt-2"
            >
              <div className="relative group inline-flex items-center gap-3 p-2 pr-4 bg-bg-page border border-border-divider rounded-xl">
                <div className="w-10 h-10 flex items-center justify-center bg-white rounded-lg shadow-sm text-brand">
                  {previewUrl ? (
                    <span
                      role="img"
                      aria-label="图片预览"
                      className="h-full w-full rounded-lg bg-cover bg-center"
                      style={{ backgroundImage: `url(${previewUrl})` }}
                    />
                  ) : getAttachmentKind(file) === "image" ? <ImageIcon size={20} /> : <FileText size={20} />}
                </div>
                <div className="flex flex-col max-w-[200px]">
                  <span className="text-sm font-medium text-text-primary truncate">{file.name}</span>
                  <span className="text-xs text-text-secondary">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
                </div>
                {!isDisabled && (
                  <button 
                    type="button"
                    onClick={removeFile}
                    className="absolute -right-2 -top-2 rounded-full bg-text-secondary p-1 text-white opacity-100 transition-opacity hover:bg-risk-refused md:opacity-0 md:group-hover:opacity-100"
                    aria-label="移除附件"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <textarea 
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          aria-label="问题"
          className="w-full resize-none outline-none max-h-48 overflow-y-auto bg-transparent placeholder:text-text-secondary/50 text-text-primary px-2 pt-2 disabled:opacity-60 disabled:cursor-not-allowed"
          placeholder={isDragging ? "松开上传附件" : isStreaming ? "正在整理回答和来源…" : responseMode === "professional" ? "输入临床问题、PICO 或文献主题…" : "把问题发过来，咱们一起查查…"}
          rows={1}
        />
        
        <div className="flex justify-between items-center mt-1 px-1">
          <div className="flex gap-1">
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              onChange={handleFileChange}
              accept={ATTACHMENT_ACCEPT}
            />
            <button 
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isDisabled || file !== null}
              className="p-2 text-text-secondary hover:bg-black/5 hover:text-text-primary rounded-full transition-colors disabled:opacity-30" 
              title="上传或粘贴图片和文件"
              aria-label="上传或粘贴图片和文件"
            >
              <Paperclip size={20} />
            </button>
          </div>
          
          {showStop ? (
            <button 
              type="button"
              onClick={onStop}
              className="bg-text-primary text-white p-2 rounded-full hover:bg-text-secondary transition-colors"
              title="停止生成"
            >
              <StopCircle size={20} />
            </button>
          ) : (
            <button 
              type="button"
              onClick={handleSend}
              disabled={(!text.trim() && !file) || isDisabled}
              className="bg-brand text-white p-2 rounded-full hover:bg-brand/90 transition-colors disabled:opacity-30 disabled:bg-text-secondary"
              title="发送"
            >
              {isSending ? <Loader2 size={20} className="animate-spin" /> : <ArrowUp size={20} />}
            </button>
          )}
        </div>
      </div>
      
      {state === "error" && errorMessage && (
        <div className="text-risk-refused text-xs mt-2 font-medium px-2">
          {errorMessage}
        </div>
      )}

      {fileError ? (
        <div role="alert" className="mt-2 px-2 text-xs font-medium text-risk-refused">
          {fileError}
        </div>
      ) : null}
      
      <div className="flex items-center justify-center gap-1.5 mt-3 px-3 py-1 text-[11px] md:text-xs text-brand/90 bg-brand/5 border border-brand/15 rounded-full max-w-fit mx-auto backdrop-blur-xs font-medium text-center shadow-2xs">
        <ShieldAlert size={13} className="text-brand flex-shrink-0" />
        <span>{responseMode === "professional" ? "输出用于循证决策支持，需结合患者情况与临床判断。" : "EviLife不是诊断工具，结果仅供参考，不能替代专业医疗建议。"}</span>
      </div>
    </div>
  );
}
