import { Eye, EyeOff } from 'lucide-react'
import { forwardRef, type InputHTMLAttributes, useId, useState } from 'react'

import { cn } from '@/lib/cn'

export interface PasswordFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  helperText?: string
}

export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  ({ label, error, helperText, id, className, ...props }, ref) => {
    const [visible, setVisible] = useState(false)
    const generatedId = useId()
    const inputId = id ?? generatedId
    const errorId = `${inputId}-error`
    const helperId = `${inputId}-helper`

    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-base font-medium text-text-primary">
          {label}
        </label>
        <div className="relative">
          <input
            ref={ref}
            id={inputId}
            type={visible ? 'text' : 'password'}
            className={cn(
              'h-13 w-full rounded-(--radius-md) border border-border bg-surface px-4 pr-13 text-base text-text-primary',
              'placeholder:text-text-muted focus-visible:border-focus',
              error && 'border-danger',
              className,
            )}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : helperText ? helperId : undefined}
            {...props}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? 'Hide password' : 'Show password'}
            aria-pressed={visible}
            className="absolute inset-y-0 right-0 flex w-13 items-center justify-center text-text-muted hover:text-text-primary"
          >
            {visible ? <EyeOff size={22} aria-hidden /> : <Eye size={22} aria-hidden />}
          </button>
        </div>
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
PasswordField.displayName = 'PasswordField'
