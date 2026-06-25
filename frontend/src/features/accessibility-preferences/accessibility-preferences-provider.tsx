import { type ReactNode, useCallback, useEffect, useState } from 'react'

import { AccessibilityPreferencesContext } from './accessibility-preferences-context'
import { applyPreferencesToDocument, loadPreferences, savePreferences } from './storage'
import { type AccessibilityPreferences } from './types'

export function AccessibilityPreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferencesState] = useState<AccessibilityPreferences>(loadPreferences)

  useEffect(() => {
    applyPreferencesToDocument(preferences)
  }, [preferences])

  const setPreferences = useCallback((next: AccessibilityPreferences) => {
    setPreferencesState(next)
    savePreferences(next)
  }, [])

  return (
    <AccessibilityPreferencesContext value={{ preferences, setPreferences }}>
      {children}
    </AccessibilityPreferencesContext>
  )
}
