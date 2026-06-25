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
  datasets: '/app/datasets',
  datasetDetail: (datasetId: string) => `/app/datasets/${datasetId}`,
  datasetSampleDetail: (datasetId: string, sampleId: string) =>
    `/app/datasets/${datasetId}/samples/${sampleId}`,
  predictions: '/app/predictions',
  predictionDetail: (id: string) => `/app/predictions/${id}`,
  research: '/app/research',
  researchResult: (evaluationId: string) => `/app/research/${evaluationId}`,
  appModel: '/app/model',
  help: '/app/help',
  preferences: '/app/preferences',
} as const
