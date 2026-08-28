import Image from "next/image";

export type MascotState =
  | "idle"
  | "welcome"
  | "thinking"
  | "searching"
  | "checking"
  | "warning"
  | "care"
  | "refuse"
  | "complete"
  | "success"
  | "error"
  | "failure";

interface MascotSlotProps {
  state: MascotState;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const mascotAssets: Record<MascotState, { src: string; alt: string }> = {
  idle: { src: "/mascot/idle.gif", alt: "是非题吉祥物待机中" },
  welcome: { src: "/mascot/welcome.gif", alt: "是非题吉祥物欢迎你" },
  thinking: { src: "/mascot/thinking.gif", alt: "是非题吉祥物正在思考" },
  searching: { src: "/mascot/thinking.gif", alt: "是非题吉祥物正在搜索证据" },
  checking: { src: "/mascot/thinking.gif", alt: "是非题吉祥物正在核对证据" },
  warning: { src: "/mascot/refuse.gif", alt: "是非题吉祥物无法回答" },
  care: { src: "/mascot/welcome.gif", alt: "是非题吉祥物正在陪着你" },
  refuse: { src: "/mascot/refuse.gif", alt: "是非题吉祥物拒绝回答" },
  complete: { src: "/mascot/success.gif", alt: "是非题吉祥物已完成回答" },
  success: { src: "/mascot/success.gif", alt: "是非题吉祥物成功完成任务" },
  error: { src: "/mascot/failure.gif", alt: "是非题吉祥物遇到失败" },
  failure: { src: "/mascot/failure.gif", alt: "是非题吉祥物遇到失败" },
};

const sizeClasses = {
  sm: "h-8 w-8",
  md: "h-12 w-12",
  lg: "h-28 w-28 sm:h-32 sm:w-32",
} as const;

export function MascotSlot({ state, size = "md", className = "" }: MascotSlotProps) {
  const asset = mascotAssets[state];

  return (
    <div
      className={`relative shrink-0 overflow-visible ${sizeClasses[size]} ${className}`}
      data-mascot-state={state}
    >
      <Image
        src={asset.src}
        alt={asset.alt}
        width={320}
        height={320}
        unoptimized
        priority={size === "lg"}
        className="h-full w-full object-contain"
      />
    </div>
  );
}
