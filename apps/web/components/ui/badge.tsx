import { cn } from "@/lib/utils";

type Variant = "default" | "accent" | "outline";

const variants: Record<Variant, string> = {
  default: "bg-foreground/8 text-muted",
  accent: "bg-accent text-accent-fg",
  outline: "hairline text-muted",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-[2px] font-mono text-[9px] uppercase tracking-widest",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
