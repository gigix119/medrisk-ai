import { Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { PublicLayout } from '@/components/layout/PublicLayout'
import { ScrollToTop } from '@/components/layout/ScrollToTop'
import { routes } from '@/config/routes'
import { AnalyzePage } from '@/pages/app/AnalyzePage'
import { DashboardPage } from '@/pages/app/DashboardPage'
import { PredictionHistoryPage } from '@/pages/app/PredictionHistoryPage'
import { PredictionResultPage } from '@/pages/app/PredictionResultPage'
import { PreferencesPage } from '@/pages/app/PreferencesPage'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { NotFoundPage } from '@/pages/errors/NotFoundPage'
import { ComingSoonPage } from '@/pages/public/ComingSoonPage'
import { LandingPage } from '@/pages/public/LandingPage'

export function AppRoutes() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path={routes.home} element={<LandingPage />} />
          <Route path={routes.demo} element={<ComingSoonPage title="Guided product preview" />} />
          <Route path={routes.howItWorks} element={<ComingSoonPage title="How it works" />} />
          <Route path={routes.technology} element={<ComingSoonPage title="Technology" />} />
          <Route path={routes.model} element={<ComingSoonPage title="Model transparency" />} />
          <Route path={routes.privacy} element={<ComingSoonPage title="Privacy" />} />
          <Route path={routes.limitations} element={<ComingSoonPage title="Limitations" />} />
          <Route path={routes.accessibility} element={<ComingSoonPage title="Accessibility" />} />
          <Route path={routes.status} element={<ComingSoonPage title="System status" />} />
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
          <Route path={routes.predictions} element={<PredictionHistoryPage />} />
          <Route
            path={routes.predictionDetail(':predictionId')}
            element={<PredictionResultPage />}
          />
          <Route path={routes.appModel} element={<ComingSoonPage title="Active model" />} />
          <Route path={routes.help} element={<ComingSoonPage title="Help center" />} />
          <Route path={routes.preferences} element={<PreferencesPage />} />
        </Route>
      </Routes>
    </>
  )
}
