import * as Dialog from '@radix-ui/react-dialog'
import { Menu, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet } from 'react-router-dom'

import { DemoLink } from '@/components/navigation/DemoLink'
import { LanguageSwitcher } from '@/components/navigation/LanguageSwitcher'
import { SkipLink } from '@/components/layout/SkipLink'
import { brand } from '@/config/brand'
import { publicNavItems } from '@/config/navigation'
import { routes } from '@/config/routes'

export function PublicLayout() {
  const { t } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <SkipLink />

      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex h-20 max-w-6xl items-center justify-between px-4">
          <Link to={routes.home} className="text-h3 font-bold text-text-primary">
            {brand.shortName}
          </Link>

          <nav aria-label="Primary" className="hidden items-center gap-6 lg:flex">
            {publicNavItems.map((item) => (
              <NavLink
                key={item.href}
                to={item.href}
                className={({ isActive }) =>
                  isActive
                    ? 'text-base font-semibold text-primary'
                    : 'text-base font-medium text-text-secondary hover:text-text-primary'
                }
              >
                {t(item.labelKey)}
              </NavLink>
            ))}
          </nav>

          <div className="hidden items-center gap-4 lg:flex">
            <LanguageSwitcher />
            <Link to={routes.login} className="text-base font-medium text-text-secondary">
              {t('nav.login')}
            </Link>
            <DemoLink className="h-11 rounded-(--radius-md) bg-primary px-5 text-base font-medium text-text-inverse flex items-center">
              {t('nav.tryDemo')}
            </DemoLink>
          </div>

          <Dialog.Root open={menuOpen} onOpenChange={setMenuOpen}>
            <Dialog.Trigger asChild>
              <button
                type="button"
                aria-label={t('nav.openMenu')}
                className="flex h-11 w-11 items-center justify-center rounded-(--radius-md) text-text-primary lg:hidden"
              >
                <Menu aria-hidden size={26} />
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-(--color-overlay)" />
              <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col gap-6 bg-surface p-6 shadow-(--shadow-elevated)">
                <div className="flex items-center justify-between">
                  <Dialog.Title className="text-h3 text-text-primary">{t('nav.menu')}</Dialog.Title>
                  <Dialog.Close asChild>
                    <button
                      type="button"
                      aria-label={t('nav.closeMenu')}
                      className="flex h-11 w-11 items-center justify-center rounded-(--radius-md) text-text-primary"
                    >
                      <X aria-hidden size={24} />
                    </button>
                  </Dialog.Close>
                </div>
                <nav aria-label="Primary" className="flex flex-col gap-1">
                  {publicNavItems.map((item) => (
                    <NavLink
                      key={item.href}
                      to={item.href}
                      onClick={() => setMenuOpen(false)}
                      className="rounded-(--radius-md) px-3 py-3 text-lg font-medium text-text-primary hover:bg-surface-subtle"
                    >
                      {t(item.labelKey)}
                    </NavLink>
                  ))}
                </nav>
                <div className="mt-auto flex flex-col gap-3">
                  <LanguageSwitcher />
                  <Link
                    to={routes.login}
                    onClick={() => setMenuOpen(false)}
                    className="h-13 flex items-center justify-center rounded-(--radius-md) border border-border text-base font-medium text-text-primary"
                  >
                    {t('nav.login')}
                  </Link>
                  <DemoLink
                    onClick={() => setMenuOpen(false)}
                    className="h-13 flex items-center justify-center rounded-(--radius-md) bg-primary text-base font-medium text-text-inverse"
                  >
                    {t('nav.tryDemo')}
                  </DemoLink>
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>
      </header>

      <main id="main-content" className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-10 text-sm text-text-muted">
          <div className="flex flex-wrap gap-4">
            <Link to={routes.privacy}>{t('footer.privacy')}</Link>
            <Link to={routes.limitations}>{t('footer.limitations')}</Link>
            <Link to={routes.accessibility}>{t('footer.accessibility')}</Link>
            <Link to={routes.status}>{t('footer.status')}</Link>
            {brand.githubUrl && (
              <a href={brand.githubUrl} target="_blank" rel="noreferrer">
                {t('footer.github')}
              </a>
            )}
          </div>
          <p>{t('footer.disclaimer')}</p>
        </div>
      </footer>
    </div>
  )
}
