export const routes = {
  // Public
  home: '/',
  demo: '/demo',
  howItWorks: '/how-it-works',
  technology: '/technology',
  model: '/model',
  privacy: '/privacy',
  limitations: '/limitations',
  accessibility: '/accessibility',
  status: '/status',
  login: '/login',
  register: '/register',

  // Authenticated
  app: '/app',
  analyze: '/app/analyze',
  predictions: '/app/predictions',
  predictionDetail: (id: string) => `/app/predictions/${id}`,
  appModel: '/app/model',
  help: '/app/help',
  preferences: '/app/preferences',
} as const
