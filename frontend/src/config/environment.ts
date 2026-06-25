function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing required environment variable "${name}". Copy .env.example to .env and fill it in.`,
    )
  }
  return value
}

function flag(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) return fallback
  return value === 'true'
}

export const env = {
  apiBaseUrl: required('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL),
  defaultLocale: import.meta.env.VITE_DEFAULT_LOCALE ?? 'en',
  enableDemoMode: flag(import.meta.env.VITE_ENABLE_DEMO_MODE, false),
  enableMockApi: flag(import.meta.env.VITE_ENABLE_MOCK_API, false),
  isDev: import.meta.env.DEV,
}
