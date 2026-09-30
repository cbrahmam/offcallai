import * as React from "react"
import { X } from "lucide-react"
import { cn } from "../../lib/utils"

interface SheetProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: React.ReactNode
}

const Sheet: React.FC<SheetProps> = ({ open, onOpenChange, children }) => {
  const contextValue = React.useMemo(
    () => ({ open: open ?? false, onOpenChange: onOpenChange ?? (() => {}) }),
    [open, onOpenChange]
  )
  return (
    <SheetContext.Provider value={contextValue}>
      {children}
    </SheetContext.Provider>
  )
}

const SheetContext = React.createContext<{
  open: boolean
  onOpenChange: (open: boolean) => void
}>({ open: false, onOpenChange: () => {} })

const SheetTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }
>(({ children, onClick, asChild, ...props }, ref) => {
  const { onOpenChange } = React.useContext(SheetContext)

  return (
    <button
      ref={ref}
      type="button"
      onClick={(e) => {
        onOpenChange(true)
        onClick?.(e)
      }}
      {...props}
    >
      {children}
    </button>
  )
})
SheetTrigger.displayName = "SheetTrigger"

const SheetClose = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement>
>(({ children, onClick, ...props }, ref) => {
  const { onOpenChange } = React.useContext(SheetContext)

  return (
    <button
      ref={ref}
      type="button"
      onClick={(e) => {
        onOpenChange(false)
        onClick?.(e)
      }}
      {...props}
    >
      {children}
    </button>
  )
})
SheetClose.displayName = "SheetClose"

const SheetPortal: React.FC<{ children: React.ReactNode }> = ({ children }) => <>{children}</>
SheetPortal.displayName = "SheetPortal"

const SheetOverlay = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("fixed inset-0 z-50 bg-black/60", className)}
    {...props}
  />
))
SheetOverlay.displayName = "SheetOverlay"

interface SheetContentProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: "top" | "right" | "bottom" | "left"
}

const sideClasses: Record<string, string> = {
  top: "inset-x-0 top-0 border-b border-border",
  bottom: "inset-x-0 bottom-0 border-t border-border",
  left: "inset-y-0 left-0 h-full w-3/4 sm:max-w-sm border-r border-border",
  right: "inset-y-0 right-0 h-full w-3/4 sm:max-w-sm border-l border-border",
}

const SheetContent = React.forwardRef<HTMLDivElement, SheetContentProps>(
  ({ side = "right", className, children, ...props }, ref) => {
    const { open, onOpenChange } = React.useContext(SheetContext)

    if (!open) return null

    return (
      <>
        <div className="fixed inset-0 z-50 bg-black/60" onClick={() => onOpenChange(false)} />
        <div
          ref={ref}
          className={cn(
            "fixed z-50 bg-background p-6 transition-transform duration-200 shadow-elevation-3",
            sideClasses[side],
            className
          )}
          {...props}
        >
          <button
            onClick={() => onOpenChange(false)}
            className="absolute right-4 top-4 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </button>
          {children}
        </div>
      </>
    )
  }
)
SheetContent.displayName = "SheetContent"

const SheetHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn("flex flex-col space-y-2 text-center sm:text-left", className)}
    {...props}
  />
)
SheetHeader.displayName = "SheetHeader"

const SheetFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}
    {...props}
  />
)
SheetFooter.displayName = "SheetFooter"

const SheetTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h2
    ref={ref}
    className={cn("text-base font-medium text-foreground", className)}
    {...props}
  />
))
SheetTitle.displayName = "SheetTitle"

const SheetDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
SheetDescription.displayName = "SheetDescription"

export {
  Sheet,
  SheetPortal,
  SheetOverlay,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
}
