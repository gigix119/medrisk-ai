import { Home, ImagePlus, MoreHorizontal, History } from 'lucide-react'

import { routes } from './routes'

export const publicNavItems = [
  { label: 'Product', href: routes.home },
  { label: 'How it works', href: routes.howItWorks },
  { label: 'Technology', href: routes.technology },
  { label: 'Model', href: routes.model },
  { label: 'Safety', href: routes.limitations },
]

export const appSidebarItems = [
  { label: 'Overview', href: routes.app, icon: Home },
  { label: 'New analysis', href: routes.analyze, icon: ImagePlus },
  { label: 'History', href: routes.predictions, icon: History },
]

/** Bottom nav is capped at 4 entries (Home/Analyze/History/More) per the age-inclusive
 * design rule against more than five items. */
export const appBottomNavItems = [
  { label: 'Home', href: routes.app, icon: Home },
  { label: 'Analyze', href: routes.analyze, icon: ImagePlus },
  { label: 'History', href: routes.predictions, icon: History },
  { label: 'More', href: null, icon: MoreHorizontal },
] as const
