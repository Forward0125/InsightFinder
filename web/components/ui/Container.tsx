import { cn } from '@/lib/utils'

type ContainerSize = 'sm' | 'md' | 'lg' | 'xl' | 'full'

interface ContainerProps {
  children:   React.ReactNode
  className?: string
  size?:      ContainerSize
  as?:        React.ElementType
}

const maxWidths: Record<ContainerSize, string> = {
  sm:   'max-w-3xl',
  md:   'max-w-4xl',
  lg:   'max-w-5xl',
  xl:   'max-w-7xl',
  full: 'max-w-full',
}

export function Container({
  children,
  className,
  size = 'xl',
  as: Tag = 'div',
}: ContainerProps) {
  return (
    <Tag
      className={cn(
        'mx-auto w-full px-4 sm:px-6 lg:px-8',
        maxWidths[size],
        className,
      )}
    >
      {children}
    </Tag>
  )
}
