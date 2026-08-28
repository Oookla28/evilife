"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type ExperienceMode = "life" | "professional";

interface ExperienceModeContextValue {
  mode: ExperienceMode;
  setMode: (mode: ExperienceMode) => void;
}

const ExperienceModeContext = createContext<ExperienceModeContextValue | null>(null);
const STORAGE_KEY = "evilife_experience_mode";

export function ExperienceModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ExperienceMode>("life");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "professional" || saved === "life") {
      queueMicrotask(() => setModeState(saved));
    }
  }, []);

  const setMode = (next: ExperienceMode) => {
    setModeState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  const value = useMemo(() => ({ mode, setMode }), [mode]);
  return (
    <ExperienceModeContext.Provider value={value}>
      <div data-experience-mode={mode} className="contents">
        {children}
      </div>
    </ExperienceModeContext.Provider>
  );
}

export function useExperienceMode() {
  const context = useContext(ExperienceModeContext);
  if (!context) throw new Error("useExperienceMode must be used inside ExperienceModeProvider");
  return context;
}
