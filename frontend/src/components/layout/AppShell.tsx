import * as Dialog from '@radix-ui/react-dialog'
import { Settings, HelpCircle, LogOut, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet } from 'react-router-dom'

import { LanguageSwitcher } from '@/components/navigation/LanguageSwitcher'
import { SkipLink } from '@/components/layout/SkipLink'
import { brand } from '@/config/brand'
import { appBottomNavItems, appSidebarItems } from '@/config/navigation'
import { routes } from '@/config/routes'
import { useAuth } from '@/features/auth/use-auth'

function navLinkClass({ isActive }: { isActive: boolean }) {
  return isActive
    ? 'flex items-center gap-3 rounded-(--radius-md) bg-primary-soft px-4 py-3 text-base font-semibold text-primary'
    : 'flex items-center gap-3 rounded-(--radius-md) px-4 py-3 text-base font-medium text-text-secondary hover:bg-surface-subtle'
}

export function AppShell() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const [moreOpen, setMoreOpen] = useState(false)

  return (
    <div className="flex min-h-screen flex-col bg-background lg:flex-row">
      <SkipLink />

      {/* Desktop sidebar */}
      <aside className="hidden w-64 flex-col border-r border-border bg-surface lg:flex">
        <Link to={routes.app} className="px-6 py-6 text-h3 font-bold text-text-primary">
          {brand.shortName}
        </Link>
        <nav aria-label="Primary" className="flex flex-1 flex-col gap-1 px-3">
          {appSidebarItems.map((item) => (
            <NavLink key={item.href} to={item.href} className={navLinkClass}>
              <item.icon aria-hidden size={22} />
              {t(item.labelKey)}
            </NavLink>
          ))}
        </nav>
        <div className="flex flex-col gap-1 border-t border-border px-3 py-4">
          <NavLink to={routes.appModel} className={navLinkClass}>
            <Settings aria-hidden size={22} />
            {t('appNav.model')}
          </NavLink>
          <NavLink to={routes.help} className={navLinkClass}>
            <HelpCircle aria-hidden size={22} />
            {t('appNav.help')}
          </NavLink>
          <NavLink to={routes.preferences} className={navLinkClass}>
            {t('appNav.preferences')}
          </NavLink>
          <LanguageSwitcher />
          <button
            type="button"
            onClick={() => void logout()}
            className="flex items-center gap-3 rounded-(--radius-md) px-4 py-3 text-base font-medium text-text-secondary hover:bg-surface-subtle"
          >
            <LogOut aria-hidden size={22} />
            {t('appNav.logout')}
          </button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        {/* Mobile top header */}
        <header className="flex h-16 items-center justify-between border-b border-border bg-surface px-4 lg:hidden">
          <Link to={routes.app} className="text-h3 font-bold text-text-primary">
            {brand.shortName}
          </Link>
          {user && <span className="text-sm text-text-muted">{user.full_name.split(' ')[0]}</span>}
        </header>

        <main id="main-content" className="flex-1 px-4 py-8 pb-28 lg:px-10 lg:py-10 lg:pb-10">
          <Outlet />
        </main>

        {/* Mobile bottom nav */}
        <nav
          aria-label="Primary"
          className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-surface pb-(env(safe-area-inset-bottom)) lg:hidden"
        >
          {appBottomNavItems.map((item) =>
            item.href ? (
              <NavLink
                key={item.labelKey}
                to={item.href}
                className={({ isActive }) =>
                  isActive
                    ? 'flex flex-1 flex-col items-center gap-1 py-2.5 text-xs font-semibold text-primary'
                    : 'flex flex-1 flex-col items-center gap-1 py-2.5 text-xs font-medium text-text-muted'
                }
              >
                <item.icon aria-hidden size={24} />
                {t(item.labelKey)}
              </NavLink>
            ) : (
              <Dialog.Root key={item.labelKey} open={moreOpen} onOpenChange={setMoreOpen}>
                <Dialog.Trigger asChild>
                  <button
                    type="button"
                    className="flex flex-1 flex-col items-center gap-1 py-2.5 text-xs font-medium text-text-muted"
                  >
                    <item.icon aria-hidden size={24} />
                    {t(item.labelKey)}
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 z-40 bg-(--color-overlay)" />
                  <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 flex flex-col gap-2 rounded-t-(--radius-lg) bg-surface p-4 pb-(env(safe-area-inset-bottom))">
                    <div className="mb-2 flex items-center justify-between">
                      <Dialog.Title className="text-h3 text-text-primary">
                        {t('appNav.more')}
                      </Dialog.Title>
                      <Dialog.Close asChild>
                        <button
                          type="button"
                          aria-label="Close"
                          className="flex h-11 w-11 items-center justify-center"
                        >
                          <X aria-hidden size={24} />
                        </button>
                      </Dialog.Close>
                    </div>
                    <NavLink
                      to={routes.appModel}
                      onClick={() => setMoreOpen(false)}
                      className="rounded-(--radius-md) px-4 py-3 text-lg font-medium text-text-primary hover:bg-surface-subtle"
                    >
                      {t('appNav.model')}
                    </NavLink>
                    <NavLink
                      to={routes.help}
                      onClick={() => setMoreOpen(false)}
                      className="rounded-(--radius-md) px-4 py-3 text-lg font-medium text-text-primary hover:bg-surface-subtle"
                    >
                      {t('appNav.help')}
                    </NavLink>
                    <NavLink
                      to={routes.preferences}
                      onClick={() => setMoreOpen(false)}
                      className="rounded-(--radius-md) px-4 py-3 text-lg font-medium text-text-primary hover:bg-surface-subtle"
                    >
                      {t('appNav.preferences')}
                    </NavLink>
                    <button
                      type="button"
                      onClick={() => void logout()}
                      className="rounded-(--radius-md) px-4 py-3 text-left text-lg font-medium text-text-primary hover:bg-surface-subtle"
                    >
                      {t('appNav.logout')}
                    </button>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
            ),
          )}
        </nav>
      </div>
    </div>
  )
}
