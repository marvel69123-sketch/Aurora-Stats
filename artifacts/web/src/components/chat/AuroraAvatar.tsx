import { cn } from "@/lib/utils";

interface AuroraAvatarProps {
  url?: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const SIZES = {
  sm: "h-7 w-7 text-[10px]",
  md: "h-8 w-8 text-xs",
  lg: "h-16 w-16 text-2xl",
} as const;

/** Reusable Aurora avatar — custom image or default monogram. */
export function AuroraAvatar({ url, size = "md", className }: AuroraAvatarProps) {
  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full",
        "bg-[#10a37f] text-white font-semibold",
        SIZES[size],
        className,
      )}
      aria-hidden
    >
      {url ? (
        <img src={url} alt="" className="h-full w-full object-cover" />
      ) : (
        <span>A</span>
      )}
    </div>
  );
}

export function UserAvatar({ size = "md", className }: Omit<AuroraAvatarProps, "url">) {
  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full",
        "bg-[#2f2f2f] text-white/80 font-semibold border border-white/10",
        SIZES[size],
        className,
      )}
      aria-hidden
    >
      <span>U</span>
    </div>
  );
}
