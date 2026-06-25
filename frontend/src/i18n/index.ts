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
    fallbackLng: 'en',
    defaultNS: 'common',
    lng: env.defaultLocale,
    interpolation: { escapeValue: false },
  })

export default i18next
