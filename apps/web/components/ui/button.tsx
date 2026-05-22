"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "outline" | "ghost" | "accent";
type Size = "default" | "sm" | "lg" | "icon";

const base =
  "inline-flex items-center justify-center font-mono text-[11px] uppercase tracking-widest " +
  "transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-foreground " +
  "disabled:pointer-events-none disabled:opacity-40 select-none";

const variants: Record<Variant, string> = {
  default: "bg-foreground text-background hover:bg-foreground/90",
  outline:
    "hairline bg-transparent text-foreground hover:bg-foreground hover:text-background",
  ghost: "text-muted hover:text-foreground",
  accent: "bg-accent text-accent-fg hover:bg-accent/90",
};

const sizes: Record<Size, string> = {
  default: "h-10 px-5",
  sm: "h-8 px-3",
  lg: "h-12 px-7 text-xs",
  icon: "h-9 w-9",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => (
    <button ref={ref} className={cn(base, variants[variant], sizes[size], className)} {...props} />
  ),
);
Button.displayName = "Button";
