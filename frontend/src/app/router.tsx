import { Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { PublicLayout } from '@/components/layout/PublicLayout'
import { ScrollToTop } from '@/components/layout/ScrollToTop'
import { routes } from '@/config/routes'
import { AnalyzePage } from '@/pages/app/AnalyzePage'
import { DashboardPage } from '@/pages/app/DashboardPage'
import { DatasetDetailPage } from '@/pages/app/DatasetDetailPage'
import { DatasetExplorerPage } from '@/pages/app/DatasetExplorerPage'
import { DatasetSampleDetailPage } from '@/pages/app/DatasetSampleDetailPage'
import { PredictionHistoryPage } from '@/pages/app/PredictionHistoryPage'
import { PredictionResultPage } from '@/pages/app/PredictionResultPage'
import { PreferencesPage } from '@/pages/app/PreferencesPage'
import { ResearchOverviewPage } from '@/pages/app/ResearchOverviewPage'
import { ResearchResultPage } from '@/pages/app/ResearchResultPage'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { NotFoundPage } from '@/pages/errors/NotFoundPage'
import { ComingSoonPage } from '@/pages/public/ComingSoonPage'
import { DemoRedirectPage } from '@/pages/public/DemoRedirectPage'
import { InfoPage } from '@/pages/public/InfoPage'
import { LandingPage } from '@/pages/public/LandingPage'

export function AppRoutes() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path={routes.home} element={<LandingPage />} />
          <Route path={routes.demo} element={<DemoRedirectPage />} />
          <Route path={routes.howItWorks} element={<InfoPage pageKey="howItWorks" />} />
          <Route path={routes.technology} element={<InfoPage pageKey="technology" />} />
          <Route path={routes.model} element={<InfoPage pageKey="model" />} />
          <Route path={routes.privacy} element={<InfoPage pageKey="privacy" />} />
          <Route path={routes.limitations} element={<InfoPage pageKey="limitations" />} />
          <Route path={routes.accessibility} element={<InfoPage pageKey="accessibility" />} />
          <Route path={routes.status} element={<InfoPage pageKey="status" />} />
          <Route path={routes.login} element={<LoginPage />} />
          <Route path={routes.register} element={<RegisterPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>

        <Route
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route path={routes.app} element={<DashboardPage />} />
          <Route path={routes.analyze} element={<AnalyzePage />} />
          <Route path={routes.datasets} element={<DatasetExplorerPage />} />
          <Route path={routes.datasetDetail(':datasetId')} element={<DatasetDetailPage />} />
          <Route
            path={routes.datasetSampleDetail(':datasetId', ':sampleId')}
            element={<DatasetSampleDetailPage />}
          />
          <Route path={routes.predictions} element={<PredictionHistoryPage />} />
          <Route
            path={routes.predictionDetail(':predictionId')}
            element={<PredictionResultPage />}
          />
          <Route path={routes.research} element={<ResearchOverviewPage />} />
          <Route path={routes.researchResult(':evaluationId')} element={<ResearchResultPage />} />
          <Route path={routes.appModel} element={<ComingSoonPage title="Active model" />} />
          <Route path={routes.help} element={<ComingSoonPage title="Help center" />} />
          <Route path={routes.preferences} element={<PreferencesPage />} />
        </Route>
      </Routes>
    </>
  )
}
