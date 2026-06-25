export type TextSize = 'standard' | 'large' | 'extra-large'
export type Contrast = 'standard' | 'increased'
export type Motion = 'system' | 'reduced'

export interface AccessibilityPreferences {
  textSize: TextSize
  contrast: Contrast
  motion: Motion
}

export const DEFAULT_PREFERENCES: AccessibilityPreferences = {
  textSize: 'standard',
  contrast: 'standard',
  motion: 'system',
}
