"use client";

import { useState, useEffect, useRef } from "react";
import { X, Moon, Sun, Monitor, ShieldCheck, Database, Trash2, Info, Check, Type, Upload, RotateCcw, FileType2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  applyCustomFont,
  clearCustomFont,
  formatFromFileName,
  getStoredFont,
  readFontAsDataUrl,
  validateFontFile,
  type CustomFontState,
} from "@/lib/fonts";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Theme = "system" | "light" | "dark";

const themes: Array<{ id: Theme; label: string; icon: typeof Monitor }> = [
  { id: "system", label: "跟随系统", icon: Monitor },
  { id: "light", label: "浅色模式", icon: Sun },
  { id: "dark", label: "深色模式", icon: Moon },
];

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [theme, setTheme] = useState<Theme>("system");
  const [showDetailSources, setShowDetailSources] = useState(true);
  const [showLimitations, setShowLimitations] = useState(true);
  const [clearedNotice, setClearedNotice] = useState(false);
  const [fontState, setFontState] = useState<CustomFontState | null>(() =>
    getStoredFont()
  );
  const [fontNotice, setFontNotice] = useState<string | null>(null);
  const [fontError, setFontError] = useState<string | null>(null);
  const fontInputRef = useRef<HTMLInputElement>(null);

  // Close on ESC key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleFontFile = async (file: File | undefined) => {
    setFontError(null);
    setFontNotice(null);
    if (!file) return;
    const problem = validateFontFile(file);
    if (problem) {
      setFontError(problem);
      return;
    }
    try {
      const dataUrl = await readFontAsDataUrl(file);
      const next: CustomFontState = {
        name: file.name,
        dataUrl,
        format: formatFromFileName(file.name),
        appliedAt: new Date().toISOString(),
      };
      applyCustomFont(next);
      setFontState(next);
      setFontNotice(`已应用字体：${file.name}`);
      window.dispatchEvent(new Event("evilife:font-changed"));
    } catch {
      setFontError("读取字体文件失败，请重试。");
    }
  };

  const handleResetFont = () => {
    clearCustomFont();
    setFontState(null);
    setFontError(null);
    setFontNotice("已恢复默认字体");
    window.dispatchEvent(new Event("evilife:font-changed"));
  };

  const handleClearCache = () => {
    localStorage.removeItem("evilife_mock_scenario");
    localStorage.removeItem("evilife_conversations_v1");
    setClearedNotice(true);
    setTimeout(() => {
      setClearedNotice(false);
      window.location.reload();
    }, 1000);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          {/* Backdrop Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
          />

          {/* Floating Card Window */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="relative w-full max-w-lg bg-white/95 backdrop-blur-xl border border-white/60 shadow-2xl rounded-3xl overflow-hidden z-10 flex flex-col max-h-[85vh]"
          >
            {/* Modal Header */}
            <div className="px-6 py-5 border-b border-border-divider/60 flex items-center justify-between bg-bg-page/40">
              <h2 className="text-lg font-bold text-text-primary flex items-center gap-2">
                <span>偏好设置</span>
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="关闭设置"
                className="p-2 text-text-secondary hover:bg-black/5 hover:text-text-primary rounded-full transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm">
              {/* Appearance Section */}
              <div className="space-y-3">
                <label className="text-xs font-semibold text-text-secondary uppercase tracking-wider block">
                  外观主题
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {themes.map((item) => {
                    const Icon = item.icon;
                    const isSelected = theme === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => setTheme(item.id)}
                        className={`flex flex-col items-center gap-2 p-3 rounded-2xl border transition-all text-xs font-medium ${
                          isSelected
                            ? "border-brand bg-brand/10 text-brand shadow-xs"
                            : "border-border-divider/70 bg-bg-page/50 hover:bg-black/5 text-text-secondary"
                        }`}
                      >
                        <Icon size={20} />
                        <span>{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Custom Font Section */}
              <div className="space-y-3 pt-2 border-t border-border-divider/60">
                <label className="text-xs font-semibold text-text-secondary uppercase tracking-wider block">
                  全页面字体
                </label>

                <div className="flex items-start justify-between gap-3 p-3 rounded-2xl border border-border-divider/60 bg-bg-page/30">
                  <div className="flex items-center gap-3 min-w-0">
                    <Type size={18} className="shrink-0 text-brand" />
                    <div className="flex flex-col min-w-0">
                      <span className="font-medium text-text-primary truncate">
                        {fontState
                          ? `当前字体：${fontState.name}`
                          : "上传自定义字体"}
                      </span>
                      <span className="text-xs text-text-secondary">
                        支持 woff2 / woff / ttf / otf（≤ 50 MB），立即应用到全站
                      </span>
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <input
                      ref={fontInputRef}
                      type="file"
                      accept=".woff2,.woff,.ttf,.otf,font/woff2,font/woff,font/ttf,font/otf"
                      className="hidden"
                      onChange={(event) =>
                        handleFontFile(event.target.files?.[0])
                      }
                    />
                    <button
                      type="button"
                      onClick={() => fontInputRef.current?.click()}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-xl bg-brand/10 text-brand hover:bg-brand/20 font-medium transition-colors"
                    >
                      <Upload size={14} />
                      {fontState ? "更换" : "上传"}
                    </button>
                    {fontState ? (
                      <button
                        type="button"
                        onClick={handleResetFont}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-xl bg-bg-page text-text-secondary hover:bg-black/5 font-medium transition-colors"
                      >
                        <RotateCcw size={14} />
                        恢复默认
                      </button>
                    ) : null}
                  </div>
                </div>

                {fontError ? (
                  <p className="flex items-center gap-1.5 text-xs text-risk-refused">
                    <FileType2 size={13} /> {fontError}
                  </p>
                ) : null}
                {fontNotice ? (
                  <p className="flex items-center gap-1.5 text-xs text-evidence-support">
                    <Check size={13} /> {fontNotice}
                  </p>
                ) : null}
              </div>

              {/* Evidence Preferences Section */}
              <div className="space-y-3 pt-2 border-t border-border-divider/60">
                <label className="text-xs font-semibold text-text-secondary uppercase tracking-wider block">
                  证据偏好
                </label>

                <div className="space-y-2">
                  <label className="flex items-center justify-between p-3 rounded-2xl border border-border-divider/60 bg-bg-page/30 cursor-pointer hover:bg-black/5 transition-colors">
                    <div className="flex items-center gap-3">
                      <ShieldCheck size={18} className="text-brand" />
                      <div className="flex flex-col">
                        <span className="font-medium text-text-primary">默认展开原始研究来源</span>
                        <span className="text-xs text-text-secondary">在回答末尾显示完整文献 PMID 与 DOI 链接</span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={showDetailSources}
                      onChange={(e) => setShowDetailSources(e.target.checked)}
                      className="w-4 h-4 accent-brand rounded cursor-pointer"
                    />
                  </label>

                  <label className="flex items-center justify-between p-3 rounded-2xl border border-border-divider/60 bg-bg-page/30 cursor-pointer hover:bg-black/5 transition-colors">
                    <div className="flex items-center gap-3">
                      <Info size={18} className="text-brand" />
                      <div className="flex flex-col">
                        <span className="font-medium text-text-primary">高亮适用人群与局限提示</span>
                        <span className="text-xs text-text-secondary">优先突出提醒不适用人群与研究边界</span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={showLimitations}
                      onChange={(e) => setShowLimitations(e.target.checked)}
                      className="w-4 h-4 accent-brand rounded cursor-pointer"
                    />
                  </label>
                </div>
              </div>

              {/* Data & Storage Section */}
              <div className="space-y-3 pt-2 border-t border-border-divider/60">
                <label className="text-xs font-semibold text-text-secondary uppercase tracking-wider block">
                  数据与缓存
                </label>
                <div className="flex items-center justify-between p-3 rounded-2xl border border-border-divider/60 bg-bg-page/30">
                  <div className="flex items-center gap-3">
                    <Database size={18} className="text-text-secondary" />
                    <div className="flex flex-col">
                      <span className="font-medium text-text-primary">重置本地 Mock 数据</span>
                      <span className="text-xs text-text-secondary">清除场景选择与本地会话缓存</span>
                    </div>
                  </div>
                  <button
                    onClick={handleClearCache}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-xl bg-risk-refused/10 text-risk-refused hover:bg-risk-refused/20 font-medium transition-colors"
                  >
                    {clearedNotice ? <Check size={14} /> : <Trash2 size={14} />}
                    <span>{clearedNotice ? "已重置" : "清除缓存"}</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-border-divider/60 bg-bg-page/60 flex items-center justify-between">
              <span className="text-xs text-text-secondary">是非题 v1.0.0</span>
              <button
                onClick={onClose}
                className="px-5 py-2 rounded-xl bg-brand text-white text-xs font-medium hover:bg-brand/90 transition-colors shadow-xs"
              >
                保存并关闭
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
