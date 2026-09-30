import * as React from "react"
import { cn } from "../../lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info" | "critical"
}

const variants: Record<string, string> = {
  default: "bg-secondary text-muted-foreground border-border",
  secondary: "bg-accent text-muted-foreground border-border",
  destructive: "bg-red-500/10 text-red-400 border-red-500/20",
  outline: "bg-transparent text-muted-foreground border-border",
  success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  warning: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  info: "bg-white/10 text-foreground border-white/20",
  critical: "bg-red-500/10 text-red-400 border-red-500/20",
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium transition-colors",
        variants[variant],
        className
      )}
      {...props}
    />
  )
}

const badgeVariants = (_opts?: { variant?: string }) => {
  const v = _opts?.variant || "default"
  return cn(
    "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium transition-colors",
    variants[v]
  )
}

export { Badge, badgeVariants }
