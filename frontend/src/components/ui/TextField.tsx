import { forwardRef, type InputHTMLAttributes, useId } from 'react'

import { cn } from '@/lib/cn'

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  helperText?: string
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  ({ label, error, helperText, id, className, ...props }, ref) => {
    const generatedId = useId()
    const inputId = id ?? generatedId
    const errorId = `${inputId}-error`
    const helperId = `${inputId}-helper`

    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-base font-medium text-text-primary">
          {label}
        </label>
        <input
          ref={ref}
          id={inputId}
          className={cn(
            'h-13 rounded-(--radius-md) border border-border bg-surface px-4 text-base text-text-primary',
            'placeholder:text-text-muted focus-visible:border-focus',
            error && 'border-danger',
            className,
          )}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          {...props}
        />
        {helperText && !error && (
          <p id={helperId} className="text-sm text-text-muted">
            {helperText}
          </p>
        )}
        {error && (
          <p id={errorId} role="alert" className="text-sm font-medium text-danger">
            {error}
          </p>
        )}
      </div>
    )
  },
)
TextField.displayName = 'TextField'
