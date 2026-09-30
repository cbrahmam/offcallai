import * as React from "react"

interface CollapsibleProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  defaultOpen?: boolean
  children: React.ReactNode
  className?: string
}

const CollapsibleContext = React.createContext<{
  open: boolean
  toggle: () => void
}>({ open: false, toggle: () => {} })

const Collapsible: React.FC<CollapsibleProps> = ({
  open: controlledOpen,
  onOpenChange,
  defaultOpen = false,
  children,
  className,
}) => {
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen)
  const open = controlledOpen ?? internalOpen
  const toggle = () => {
    const next = !open
    setInternalOpen(next)
    onOpenChange?.(next)
  }

  return (
    <CollapsibleContext.Provider value={{ open, toggle }}>
      <div className={className} data-state={open ? "open" : "closed"}>
        {children}
      </div>
    </CollapsibleContext.Provider>
  )
}

interface CollapsibleTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean
}

const CollapsibleTrigger = React.forwardRef<HTMLButtonElement, CollapsibleTriggerProps>(
  ({ children, onClick, asChild, ...props }, ref) => {
    const { toggle } = React.useContext(CollapsibleContext)

    return (
      <button
        ref={ref}
        type="button"
        onClick={(e) => {
          toggle()
          onClick?.(e)
        }}
        {...props}
      >
        {children}
      </button>
    )
  }
)
CollapsibleTrigger.displayName = "CollapsibleTrigger"

interface CollapsibleContentProps extends React.HTMLAttributes<HTMLDivElement> {}

const CollapsibleContent: React.FC<CollapsibleContentProps> = ({ children, className, ...props }) => {
  const { open } = React.useContext(CollapsibleContext)

  if (!open) return null

  return (
    <div className={className} {...props}>
      {children}
    </div>
  )
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
