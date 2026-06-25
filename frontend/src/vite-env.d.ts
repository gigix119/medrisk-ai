/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_NAME: string
  readonly VITE_APP_SHORT_NAME: string
  readonly VITE_APP_TAGLINE: string
  readonly VITE_PUBLIC_SITE_URL: string
  readonly VITE_GITHUB_URL: string
  readonly VITE_CONTACT_EMAIL: string
  readonly VITE_API_BASE_URL: string
  readonly VITE_DEFAULT_LOCALE: string
  readonly VITE_ENABLE_DEMO_MODE: string
  readonly VITE_ENABLE_MOCK_API: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
