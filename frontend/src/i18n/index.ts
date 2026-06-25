import i18next from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import { env } from '@/config/environment'

import en from './en/common.json'
import pl from './pl/common.json'

void i18next
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { common: en },
      pl: { common: pl },
    },
    // No `lng` here - it would force this language on every load and override the
    // detector below, so a chosen language would never survive a page reload.
    fallbackLng: env.defaultLocale,
    defaultNS: 'common',
    interpolation: { escapeValue: false },
  })

export default i18next
