import * as React from "react"
import { cn } from "../../lib/utils"

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link"
  size?: "default" | "sm" | "lg" | "icon"
  asChild?: boolean
}

const variantClasses: Record<string, string> = {
  default: "bg-primary text-primary-foreground hover:bg-white/90 shadow-elevation-1",
  destructive: "bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20",
  outline: "border border-border bg-transparent text-foreground hover:bg-accent hover:text-foreground",
  secondary: "border border-border bg-secondary text-secondary-foreground hover:bg-accent",
  ghost: "text-muted-foreground hover:bg-accent hover:text-foreground",
  link: "text-foreground underline-offset-4 hover:underline",
}

const sizeClasses: Record<string, string> = {
  default: "h-9 px-4 py-2",
  sm: "h-8 px-3 text-xs",
  lg: "h-10 px-6",
  icon: "h-9 w-9",
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", asChild, ...props }, ref) => {
    return (
      <button
        className={cn(
          "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

const buttonVariants = (_opts?: { variant?: string; size?: string; className?: string }) => {
  const v = _opts?.variant || "default"
  const s = _opts?.size || "default"
  return cn(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
    variantClasses[v],
    sizeClasses[s],
    _opts?.className
  )
}

export { Button, buttonVariants }
