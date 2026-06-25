import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/** React Router does client-side navigation without a full page load, so the browser
 * never resets scroll position on its own - without this, navigating to a new page can
 * land the user mid-scroll on the previous page's content. */
export function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return null
}
