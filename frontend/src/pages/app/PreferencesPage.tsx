import { useAccessibilityPreferences } from '@/features/accessibility-preferences/use-accessibility-preferences'
import type { Contrast, Motion, TextSize } from '@/features/accessibility-preferences/types'

const textSizeOptions: { value: TextSize; label: string }[] = [
  { value: 'standard', label: 'Standard' },
  { value: 'large', label: 'Large' },
  { value: 'extra-large', label: 'Extra large' },
]

const contrastOptions: { value: Contrast; label: string }[] = [
  { value: 'standard', label: 'Standard' },
  { value: 'increased', label: 'Increased' },
]

const motionOptions: { value: Motion; label: string }[] = [
  { value: 'system', label: 'Match system setting' },
  { value: 'reduced', label: 'Reduced' },
]

export function PreferencesPage() {
  const { preferences, setPreferences } = useAccessibilityPreferences()

  return (
    <div className="flex max-w-2xl flex-col gap-10">
      <div>
        <h1 className="text-h1 text-text-primary">Accessibility preferences</h1>
        <p className="mt-2 text-lg text-text-secondary">
          These settings are stored only on this device and apply across the whole application.
        </p>
      </div>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-h3 text-text-primary">Text size</legend>
        {textSizeOptions.map((option) => (
          <label key={option.value} className="flex items-center gap-3 text-base">
            <input
              type="radio"
              name="textSize"
              className="h-5 w-5"
              checked={preferences.textSize === option.value}
              onChange={() => setPreferences({ ...preferences, textSize: option.value })}
            />
            {option.label}
          </label>
        ))}
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-h3 text-text-primary">Contrast</legend>
        {contrastOptions.map((option) => (
          <label key={option.value} className="flex items-center gap-3 text-base">
            <input
              type="radio"
              name="contrast"
              className="h-5 w-5"
              checked={preferences.contrast === option.value}
              onChange={() => setPreferences({ ...preferences, contrast: option.value })}
            />
            {option.label}
          </label>
        ))}
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-h3 text-text-primary">Motion</legend>
        {motionOptions.map((option) => (
          <label key={option.value} className="flex items-center gap-3 text-base">
            <input
              type="radio"
              name="motion"
              className="h-5 w-5"
              checked={preferences.motion === option.value}
              onChange={() => setPreferences({ ...preferences, motion: option.value })}
            />
            {option.label}
          </label>
        ))}
      </fieldset>
    </div>
  )
}
