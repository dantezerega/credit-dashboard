import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUiStore } from '../store/uiStore'

/** Global shortcuts: Cmd/Ctrl+K or "/" search, g+d dashboard, g+a analytics,
 * g+l alerts, f toggle filters. */
export function useKeyboardShortcuts() {
  const navigate = useNavigate()
  const { setSearchOpen, toggleFilters } = useUiStore()

  useEffect(() => {
    let pendingG = false
    let gTimer: ReturnType<typeof setTimeout> | undefined

    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen(true)
        return
      }
      if (typing) return

      if (e.key === '/') {
        e.preventDefault()
        setSearchOpen(true)
        return
      }
      if (e.key === 'g') {
        pendingG = true
        clearTimeout(gTimer)
        gTimer = setTimeout(() => (pendingG = false), 600)
        return
      }
      if (pendingG) {
        pendingG = false
        if (e.key === 'd') navigate('/')
        if (e.key === 'a') navigate('/analytics')
        if (e.key === 'l') navigate('/alerts')
        return
      }
      if (e.key === 'f') toggleFilters()
    }

    window.addEventListener('keydown', handler)
    return () => {
      window.removeEventListener('keydown', handler)
      clearTimeout(gTimer)
    }
  }, [navigate, setSearchOpen, toggleFilters])
}
