/**
 * Single source of truth for product naming and copy that varies by deployment.
 * Changing the brand should mean changing environment variables, not editing components.
 */

const fallback = {
  name: 'MedRisk AI',
  shortName: 'MedRisk',
  tagline: 'Transparent AI research for histopathology image analysis.',
  taglinePl: 'Przejrzysta analiza obrazów histopatologicznych z wykorzystaniem AI.',
  disclaimer:
    'Research and educational project only. This is not a medical device and must not be ' +
    'used to diagnose, treat, or make decisions about real patients.',
}

export const brand = {
  name: import.meta.env.VITE_APP_NAME || fallback.name,
  shortName: import.meta.env.VITE_APP_SHORT_NAME || fallback.shortName,
  tagline: import.meta.env.VITE_APP_TAGLINE || fallback.tagline,
  taglinePl: fallback.taglinePl,
  disclaimer: fallback.disclaimer,
  siteUrl: import.meta.env.VITE_PUBLIC_SITE_URL || 'http://localhost:5173',
  githubUrl: import.meta.env.VITE_GITHUB_URL || undefined,
  contactEmail: import.meta.env.VITE_CONTACT_EMAIL || undefined,
}

export type Brand = typeof brand
