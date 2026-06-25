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
import { buildEmailSchema } from '@/lib/validation'

type LoginFormValues = z.infer<ReturnType<typeof buildLoginSchema>>

function buildLoginSchema(t: (key: string) => string) {
  return z.object({
    email: buildEmailSchema(t),
    password: z.string().min(1, t('auth.login.passwordRequired')),
  })
}

export function LoginPage() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [formError, setFormError] = useState<string | null>(null)

  const loginSchema = useMemo(() => buildLoginSchema(t), [t])

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) })

  const redirectTo =
    (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/app'

  async function onSubmit(values: LoginFormValues) {
    setFormError(null)
    try {
      await login(values)
      navigate(redirectTo, { replace: true })
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message)
      } else {
        setFormError(t('auth.login.genericError'))
      }
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-8 px-4 py-16">
      <div className="flex flex-col gap-2 text-center">
        <h1 className="text-h1 text-text-primary">{t('auth.login.title')}</h1>
        <p className="text-base text-text-secondary">
          {t('auth.login.subtitle', { name: brand.shortName })}
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
        <TextField
          label={t('auth.login.emailLabel')}
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <PasswordField
          label={t('auth.login.passwordLabel')}
          autoComplete="current-password"
          error={errors.password?.message}
          {...register('password')}
        />

        {formError && (
          <p role="alert" className="text-base font-medium text-danger">
            {formError}
          </p>
        )}

        <Button type="submit" size="full" disabled={isSubmitting}>
          {isSubmitting ? t('auth.login.submitting') : t('auth.login.submit')}
        </Button>

        <p className="text-center text-base text-text-secondary">
          {t('auth.login.noAccount')}{' '}
          <Link
            to="/register"
            state={location.state}
            className="font-medium text-primary hover:underline"
          >
            {t('auth.login.createAccount')}
          </Link>
        </p>

        <p className="reading-measure mx-auto text-center text-sm text-text-muted">
          {t('common.disclaimer')}
        </p>
      </form>
    </div>
  )
}
