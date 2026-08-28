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
  idle: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
  welcome: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
  thinking: { src: "/mascot/avatar.png", alt: "EviLife 健康助手正在思考" },
  searching: { src: "/mascot/avatar.png", alt: "EviLife 健康助手正在搜索证据" },
  checking: { src: "/mascot/avatar.png", alt: "EviLife 健康助手正在核对证据" },
  warning: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
  care: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
  refuse: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
  complete: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
  success: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
  error: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
  failure: { src: "/mascot/avatar.png", alt: "EviLife 健康助手" },
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
