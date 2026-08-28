"use client";

import { useState, useEffect, useRef, useSyncExternalStore } from "react";
import { ChevronDown, Check, Sparkles, AlertCircle, FileText, Utensils, Timer, Trash2, Printer } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const SCENARIOS = [
  { id: "apple-interactive", label: "苹果设计互动测试 (添加/碎纸)", category: "实时互动测试", icon: Sparkles },
  { id: "evidence-normal", label: "标准综合解答", category: "完整回答", icon: Sparkles },
  { id: "polaroid-printer", label: "拍立得打印 & CoverFlow 证据流", category: "打印/装载动画", icon: Printer },
  { id: "passbook-shredder", label: "iOS6 Passbook 碎纸机粉碎", category: "删除/销毁动画", icon: Trash2 },
  { id: "evidence-degraded", label: "低置信度 / 降级回答", category: "边界防护", icon: AlertCircle },
  { id: "evidence-refused", label: "非医学受限回答", category: "伦理边界", icon: AlertCircle },
  { id: "evidence-streaming", label: "流式数据响应中", category: "实时流", icon: Sparkles },
  { id: "meal-estimated", label: "餐食热量确认流", category: "写操作确认", icon: Utensils },
  { id: "fasting-confirmation", label: "断食计时确认流", category: "写操作确认", icon: Timer },
  { id: "document-summary", label: "文献 / PDF 多层摘要", category: "文档分析", icon: FileText },
  { id: "api-error", label: "服务器异常 (500)", category: "错误处理", icon: AlertCircle },
  { id: "network-timeout", label: "网络连接超时", category: "错误处理", icon: AlertCircle },
  { id: "unsupported-module", label: "未知渲染模块 (Fallback)", category: "异常兜底", icon: AlertCircle },
];

export function ScenarioSwitcher() {
  const isClient = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false
  );
  const [scenario, setScenario] = useState(() =>
    typeof window === "undefined"
      ? "evidence-normal"
      : localStorage.getItem("evilife_mock_scenario") || "evidence-normal"
  );
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (
    process.env.NODE_ENV !== "development" ||
    process.env.NEXT_PUBLIC_USE_MOCKS !== "true" ||
    !isClient
  ) {
    return null;
  }

  const currentItem = SCENARIOS.find(s => s.id === scenario) || SCENARIOS[0];

  const handleSelect = (id: string) => {
    setScenario(id);
    localStorage.setItem("evilife_mock_scenario", id);
    setIsOpen(false);
    window.location.reload();
  };

  return (
    <div className="relative w-full text-left" ref={menuRef}>
      {/* Sidebar bottom trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-black/5 hover:bg-black/10 border border-border-divider/50 transition-all text-text-primary text-xs group"
      >
        <div className="flex flex-col text-left truncate">
          <span className="text-[10px] text-text-secondary font-medium">Mock Scenario</span>
          <span className="font-semibold text-brand truncate">{currentItem.label}</span>
        </div>
        <ChevronDown 
          size={14} 
          className={`text-text-secondary flex-shrink-0 transition-transform duration-200 ml-1 ${isOpen ? "rotate-180" : ""}`} 
        />
      </button>

      {/* Popover Menu popping UPWARDS from bottom */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute left-0 bottom-full mb-2 w-64 bg-white/90 backdrop-blur-xl border border-white/60 shadow-2xl rounded-2xl p-2 z-50 divide-y divide-border-divider/50"
          >
            <div className="px-3 py-2 text-xs font-medium text-text-secondary">
              Mock 场景模拟器 (仅开发环境)
            </div>
            
            <div className="py-1 max-h-[360px] overflow-y-auto space-y-0.5">
              {SCENARIOS.map((item) => {
                const isSelected = item.id === scenario;
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleSelect(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left text-sm transition-all ${
                      isSelected 
                        ? "bg-brand/10 text-brand font-medium" 
                        : "text-text-primary hover:bg-black/5"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 overflow-hidden">
                      <Icon size={16} className={isSelected ? "text-brand" : "text-text-secondary"} />
                      <div className="flex flex-col truncate">
                        <span className="truncate">{item.label}</span>
                        <span className="text-[10px] text-text-secondary opacity-70">{item.category}</span>
                      </div>
                    </div>
                    {isSelected && <Check size={16} className="text-brand flex-shrink-0 ml-2" />}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
