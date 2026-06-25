import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { ApiError } from '@/api/errors'
import { brand } from '@/config/brand'
import { Button } from '@/components/ui/Button'
import { PasswordField } from '@/components/ui/PasswordField'
import { TextField } from '@/components/ui/TextField'
import { useAuth } from '@/features/auth/use-auth'
import { emailSchema, MIN_PASSWORD_LENGTH, newPasswordSchema } from '@/lib/validation'

const registerSchema = z
  .object({
    fullName: z.string().trim().min(1, 'Enter your full name.').max(255),
    email: emailSchema,
    password: newPasswordSchema,
    confirmPassword: z.string(),
    acceptedResearchNotice: z.literal(true, {
      error: 'You must acknowledge this is a research project before continuing.',
    }),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match.',
    path: ['confirmPassword'],
  })

type RegisterFormValues = z.infer<typeof registerSchema>

export function RegisterPage() {
  const { register: registerUser, login } = useAuth()
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) })

  async function onSubmit(values: RegisterFormValues) {
    setFormError(null)
    try {
      // Password confirmation is a client-side check only - never sent to the backend.
      await registerUser({
        full_name: values.fullName,
        email: values.email,
        password: values.password,
      })
      await login({ email: values.email, password: values.password })
      navigate('/app', { replace: true })
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message)
      } else {
        setFormError('Something went wrong. Please try again.')
      }
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-8 px-4 py-16">
      <div className="flex flex-col gap-2 text-center">
        <h1 className="text-h1 text-text-primary">Create an account</h1>
        <p className="text-base text-text-secondary">
          Set up access to the {brand.name} research demo.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
        <TextField
          label="Full name"
          autoComplete="name"
          error={errors.fullName?.message}
          {...register('fullName')}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <PasswordField
          label="Password"
          autoComplete="new-password"
          helperText={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          error={errors.password?.message}
          {...register('password')}
        />
        <PasswordField
          label="Confirm password"
          autoComplete="new-password"
          error={errors.confirmPassword?.message}
          {...register('confirmPassword')}
        />

        <label className="flex items-start gap-3 text-base text-text-secondary">
          <input
            type="checkbox"
            className="mt-1 h-5 w-5 shrink-0 rounded-(--radius-sm) border-border-strong"
            {...register('acceptedResearchNotice')}
          />
          <span>
            I understand {brand.shortName} is a research and educational project, not a medical
            device, and I will not upload personal or identifying medical information.
          </span>
        </label>
        {errors.acceptedResearchNotice && (
          <p role="alert" className="text-sm font-medium text-danger">
            {errors.acceptedResearchNotice.message}
          </p>
        )}

        {formError && (
          <p role="alert" className="text-base font-medium text-danger">
            {formError}
          </p>
        )}

        <Button type="submit" size="full" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </Button>

        <p className="text-center text-base text-text-secondary">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  )
}
