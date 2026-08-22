import { useEffect, useState } from 'react'

type Theme = 'bay' | 'light-table'

const THEMES: { id: Theme; label: string }[] = [
  { id: 'bay', label: 'the editing bay' },
  { id: 'light-table', label: 'the light table' }
]

const STORAGE_KEY = 'publikclip-theme'

function readStoredTheme(): Theme {
  return localStorage.getItem(STORAGE_KEY) === 'light-table' ? 'light-table' : 'bay'
}

export default function ThemeSwitcher() {
  const [theme, setTheme] = useState<Theme>(readStoredTheme)

  useEffect(() => {
    if (theme === 'bay') document.documentElement.removeAttribute('data-theme')
    else document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  return (
    <div className="theme-switcher">
      <span className="theme-switcher-label mono">theme</span>
      {THEMES.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`theme-swatch theme-swatch-${t.id} ${theme === t.id ? 'theme-swatch-on' : ''}`}
          onClick={() => setTheme(t.id)}
          title={t.label}
          aria-label={t.label}
          aria-pressed={theme === t.id}
        />
      ))}
    </div>
  )
}
