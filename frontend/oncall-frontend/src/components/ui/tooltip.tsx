import * as React from "react"
import { cn } from "../../lib/utils"

interface TooltipProviderProps {
  children: React.ReactNode
  delayDuration?: number
}

const TooltipContext = React.createContext<{ delay: number }>({ delay: 300 })

const TooltipProvider: React.FC<TooltipProviderProps> = ({ children, delayDuration = 300 }) => (
  <TooltipContext.Provider value={{ delay: delayDuration }}>
    {children}
  </TooltipContext.Provider>
)

interface TooltipProps {
  children: React.ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

const Tooltip: React.FC<TooltipProps> = ({ children, open: controlledOpen, onOpenChange }) => {
  const [internalOpen, setInternalOpen] = React.useState(false)
  const open = controlledOpen ?? internalOpen
  const setOpen = onOpenChange ?? setInternalOpen

  return (
    <TooltipStateContext.Provider value={{ open, setOpen }}>
      <div className="relative inline-flex">{children}</div>
    </TooltipStateContext.Provider>
  )
}

const TooltipStateContext = React.createContext<{
  open: boolean
  setOpen: (open: boolean) => void
}>({ open: false, setOpen: () => {} })

interface TooltipTriggerProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean
}

const TooltipTrigger = React.forwardRef<HTMLDivElement, TooltipTriggerProps>(
  ({ children, asChild, ...props }, ref) => {
    const { delay } = React.useContext(TooltipContext)
    const { setOpen } = React.useContext(TooltipStateContext)
    const timerRef = React.useRef<ReturnType<typeof setTimeout>>(undefined)

    const handleEnter = () => {
      timerRef.current = setTimeout(() => setOpen(true), delay)
    }

    const handleLeave = () => {
      clearTimeout(timerRef.current)
      setOpen(false)
    }

    return (
      <div
        ref={ref}
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        onFocus={handleEnter}
        onBlur={handleLeave}
        {...props}
      >
        {children}
      </div>
    )
  }
)
TooltipTrigger.displayName = "TooltipTrigger"

interface TooltipContentProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: "top" | "right" | "bottom" | "left"
  align?: "start" | "center" | "end"
  sideOffset?: number
}

const TooltipContent = React.forwardRef<HTMLDivElement, TooltipContentProps>(
  ({ className, side = "top", sideOffset = 4, children, hidden, ...props }, ref) => {
    const { open } = React.useContext(TooltipStateContext)

    if (!open || hidden) return null

    const positionClasses: Record<string, string> = {
      top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
      bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
      left: "right-full top-1/2 -translate-y-1/2 mr-2",
      right: "left-full top-1/2 -translate-y-1/2 ml-2",
    }

    return (
      <div
        ref={ref}
        className={cn(
          "absolute z-50 overflow-hidden rounded-md bg-popover border border-border px-3 py-1.5 text-xs text-foreground shadow-elevation-2 animate-fade-in",
          positionClasses[side],
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
