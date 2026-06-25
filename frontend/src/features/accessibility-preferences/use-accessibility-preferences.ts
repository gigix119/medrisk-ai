import { use } from 'react'

import { AccessibilityPreferencesContext } from './accessibility-preferences-context'

export function useAccessibilityPreferences() {
  const context = use(AccessibilityPreferencesContext)
  if (!context) {
    throw new Error(
      'useAccessibilityPreferences must be used within an AccessibilityPreferencesProvider',
    )
  }
  return context
}
