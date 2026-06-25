import { createContext } from 'react'

import { type AccessibilityPreferences } from './types'

export interface AccessibilityPreferencesContextValue {
  preferences: AccessibilityPreferences
  setPreferences: (preferences: AccessibilityPreferences) => void
}

export const AccessibilityPreferencesContext =
  createContext<AccessibilityPreferencesContextValue | null>(null)
