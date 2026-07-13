import { cn } from "@/lib/utils";

interface AuroraAvatarProps {
  url?: string | null;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const SIZES = {
  sm: "h-8 w-8 text-[11px]",
  md: "h-9 w-9 text-xs",
  lg: "h-14 w-14 text-xl",
  xl: "h-[4.5rem] w-[4.5rem] text-2xl",
} as const;

/** Reusable Aurora avatar — custom image or default monogram. */
export function AuroraAvatar({ url, size = "md", className }: AuroraAvatarProps) {
  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full",
        "bg-gradient-to-br from-[#19c37d] to-[#0e8f6a] text-white font-semibold",
        "ring-1 ring-white/10 shadow-[0_0_0_1px_rgba(16,163,127,0.25)]",
        SIZES[size],
        className,
      )}
      aria-hidden
    >
      {url ? (
        <img src={url} alt="" className="h-full w-full object-cover" />
      ) : (
        <span className="select-none tracking-tight">A</span>
      )}
    </div>
  );
}

export function UserAvatar({ size = "md", className }: Omit<AuroraAvatarProps, "url">) {
  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full",
        "bg-[#2f2f2f] text-white/75 font-semibold ring-1 ring-white/10",
        SIZES[size],
        className,
      )}
      aria-hidden
    >
      <span className="select-none tracking-tight">U</span>
    </div>
  );
}
