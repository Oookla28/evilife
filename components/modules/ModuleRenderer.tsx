"use client";

import { motion, useReducedMotion } from "framer-motion";
import { getModuleComponent } from "@/lib/module-registry";
import { ModulePlanItem } from "@/lib/api/types";
import type { RunPhase } from "@/lib/chat/run-state";

interface ModuleRendererProps {
  modulePlan: ModulePlanItem[];
  runPhase?: RunPhase;
}

export function ModuleRenderer({ modulePlan, runPhase = "ready" }: ModuleRendererProps) {
  const reduceMotion = useReducedMotion();
  const isProducing = ["starting", "routing", "collecting", "streaming"].includes(runPhase);
  if (!modulePlan || modulePlan.length === 0) return null;

  return (
    <div className="flex flex-col gap-4 w-full">
      {modulePlan.map((item, index) => {
        const Component = getModuleComponent(item.type);
        
        return (
          <motion.div
            key={item.module_id}
            initial={reduceMotion ? false : { opacity: 0, y: 12, scale: 0.985 }}
            animate={{
              opacity: isProducing ? 0.72 : 1,
              y: isProducing ? -6 : 0,
              scale: isProducing ? 0.992 : 1,
              filter: isProducing ? "saturate(0.82)" : "saturate(1)",
            }}
            transition={{ 
              duration: reduceMotion ? 0 : 0.32,
              ease: [0.175, 0.885, 0.32, 1.1], // spring-like but not too bouncy
              delay: index * 0.05
            }}
            className="relative w-full overflow-hidden"
          >
            <Component {...item.props} type={item.type} status={item.status} />
            {isProducing && !reduceMotion ? (
              <motion.div
                aria-hidden="true"
                className="pointer-events-none absolute inset-x-0 top-0 h-14 bg-gradient-to-b from-white/85 to-transparent"
                animate={{ y: ["-100%", "650%"] }}
                transition={{ duration: 2.4, ease: [0.22, 0.61, 0.36, 1], repeat: Infinity }}
              />
            ) : null}
          </motion.div>
        );
      })}
    </div>
  );
}
