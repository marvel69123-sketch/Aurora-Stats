import { cn } from "@/lib/utils";

interface AuroraAvatarProps {
  url?: string | null;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const SIZES = {
  sm: "h-9 w-9 text-[12px]",
  md: "h-10 w-10 text-[13px]",
  lg: "h-16 w-16 text-2xl",
  xl: "h-[5.25rem] w-[5.25rem] text-[1.75rem]",
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
