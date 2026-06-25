import { Database, Home, MoreHorizontal, History } from 'lucide-react'

import { routes } from './routes'

export const publicNavItems = [
  { labelKey: 'nav.product', href: routes.home },
  { labelKey: 'nav.howItWorks', href: routes.howItWorks },
  { labelKey: 'nav.technology', href: routes.technology },
  { labelKey: 'nav.model', href: routes.model },
  { labelKey: 'nav.safety', href: routes.limitations },
]

export const appSidebarItems = [
  { labelKey: 'appNav.home', href: routes.app, icon: Home },
  { labelKey: 'appNav.datasets', href: routes.datasets, icon: Database },
  { labelKey: 'appNav.researchRuns', href: routes.predictions, icon: History },
]

/** Bottom nav is capped at 4 entries (Home/Datasets/Research runs/More) per the
 * age-inclusive design rule against more than five items. The "Datasets" slot replaces
 * what used to be a direct upload entry point - there is no arbitrary-upload control
 * reachable from primary navigation anymore (Phase 6). */
export const appBottomNavItems = [
  { labelKey: 'appNav.home', href: routes.app, icon: Home },
  { labelKey: 'appNav.datasets', href: routes.datasets, icon: Database },
  { labelKey: 'appNav.researchRuns', href: routes.predictions, icon: History },
  { labelKey: 'appNav.more', href: null, icon: MoreHorizontal },
] as const
