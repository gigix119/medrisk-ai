import { zodResolver } from '@hookform/resolvers/zod'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { ApiError } from '@/api/errors'
import { brand } from '@/config/brand'
import { Button } from '@/components/ui/Button'
import { PasswordField } from '@/components/ui/PasswordField'
import { TextField } from '@/components/ui/TextField'
import { useAuth } from '@/features/auth/use-auth'
import { buildEmailSchema, buildPasswordSchema, MIN_PASSWORD_LENGTH } from '@/lib/validation'

type RegisterFormValues = z.infer<ReturnType<typeof buildRegisterSchema>>

function buildRegisterSchema(t: (key: string, options?: Record<string, unknown>) => string) {
  return z
    .object({
      fullName: z.string().trim().min(1, t('auth.register.fullNameRequired')).max(255),
      email: buildEmailSchema(t),
      password: buildPasswordSchema(t),
      confirmPassword: z.string(),
      acceptedResearchNotice: z.literal(true, { error: t('auth.register.researchNoticeRequired') }),
    })
    .refine((data) => data.password === data.confirmPassword, {
      message: t('auth.register.passwordMismatch'),
      path: ['confirmPassword'],
    })
}

export function RegisterPage() {
  const { t } = useTranslation()
  const { register: registerUser, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [formError, setFormError] = useState<string | null>(null)

  const registerSchema = useMemo(() => buildRegisterSchema(t), [t])

  const redirectTo =
    (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/app'

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
      navigate(redirectTo, { replace: true })
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message)
      } else {
        setFormError(t('auth.register.genericError'))
      }
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-8 px-4 py-16">
      <div className="flex flex-col gap-2 text-center">
        <h1 className="text-h1 text-text-primary">{t('auth.register.title')}</h1>
        <p className="text-base text-text-secondary">
          {t('auth.register.subtitle', { name: brand.shortName })}
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
        <TextField
          label={t('auth.register.fullNameLabel')}
          autoComplete="name"
          error={errors.fullName?.message}
          {...register('fullName')}
        />
        <TextField
          label={t('auth.register.emailLabel')}
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <PasswordField
          label={t('auth.register.passwordLabel')}
          autoComplete="new-password"
          helperText={t('auth.register.passwordHelper', { count: MIN_PASSWORD_LENGTH })}
          error={errors.password?.message}
          {...register('password')}
        />
        <PasswordField
          label={t('auth.register.confirmPasswordLabel')}
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
          <span>{t('auth.register.researchNotice', { shortName: brand.shortName })}</span>
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
          {isSubmitting ? t('auth.register.submitting') : t('auth.register.submit')}
        </Button>

        <p className="text-center text-base text-text-secondary">
          {t('auth.register.haveAccount')}{' '}
          <Link to="/login" state={location.state} className="font-medium text-primary hover:underline">
            {t('auth.register.login')}
          </Link>
        </p>
      </form>
    </div>
  )
}
