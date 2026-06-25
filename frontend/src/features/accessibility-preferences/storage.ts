import { type AccessibilityPreferences, DEFAULT_PREFERENCES } from './types'

const STORAGE_KEY = 'medrisk.accessibility-preferences'

export function loadPreferences(): AccessibilityPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_PREFERENCES
    return { ...DEFAULT_PREFERENCES, ...(JSON.parse(raw) as Partial<AccessibilityPreferences>) }
  } catch {
    return DEFAULT_PREFERENCES
  }
}

export function savePreferences(preferences: AccessibilityPreferences): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
}

/** Maps preferences onto `data-*` attributes on <html>, consumed by globals.css /
 * motion.css. Exported standalone so it can run both from React and from the
 * before-paint inline script in index.html (which can't import React modules). */
export function applyPreferencesToDocument(preferences: AccessibilityPreferences): void {
  const root = document.documentElement
  root.setAttribute('data-text-size', preferences.textSize)
  root.setAttribute('data-contrast', preferences.contrast)
  root.setAttribute('data-motion', preferences.motion)
}
