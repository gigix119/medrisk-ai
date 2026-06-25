import { describe, expect, it } from 'vitest'

import en from './en/common.json'
import pl from './pl/common.json'

/** Phrases that imply this platform diagnoses or treats the *user themselves* (a real
 * patient) rather than running research inference on a known dataset sample. Unlike
 * "diagnosis"/"patient" alone - which legitimately appear inside the project's own
 * negated disclaimers ("must not be used to diagnose... real patients") - none of these
 * have a legitimate negated use, so their mere presence anywhere in the locale files is
 * itself the bug. */
const BANNED_PHRASES = [
  'your diagnosis',
  'your condition',
  'your symptoms',
  'physician',
  'treatment plan',
  'medical record',
  'your scan',
  'patient portal',
  'doctor will',
  'your x-ray',
  'your biopsy',
  'your tissue',
  'upload your',
  'upload an image of yourself',
]

function collectStrings(value: unknown, out: string[] = []): string[] {
  if (typeof value === 'string') {
    out.push(value)
  } else if (Array.isArray(value)) {
    value.forEach((item) => collectStrings(item, out))
  } else if (value !== null && typeof value === 'object') {
    Object.values(value).forEach((item) => collectStrings(item, out))
  }
  return out
}

describe.each([
  ['en', en],
  ['pl', pl],
])('locale %s has no clinical/patient-facing wording', (_locale, catalog) => {
  const strings = collectStrings(catalog)

  it.each(BANNED_PHRASES)('never contains the phrase "%s"', (phrase) => {
    const offending = strings.filter((value) => value.toLowerCase().includes(phrase))
    expect(offending).toEqual([])
  })
})
