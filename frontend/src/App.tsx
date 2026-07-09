import { Route, Routes } from 'react-router-dom'
import { SearchPalette } from './components/SearchPalette'
import { TopBar } from './components/TopBar'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { AlertsPage } from './pages/AlertsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { BondDetailPage } from './pages/BondDetailPage'
import { DashboardPage } from './pages/DashboardPage'

export default function App() {
  useKeyboardShortcuts()

  return (
    <div className="flex h-screen flex-col">
      <TopBar />
      <main className="min-h-0 flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/bond/:cusip" element={<BondDetailPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
        </Routes>
      </main>
      <SearchPalette />
    </div>
  )
}
