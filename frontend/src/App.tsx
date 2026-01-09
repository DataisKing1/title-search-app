import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import Layout from '@/components/Layout'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import Dashboard from '@/pages/Dashboard'
import Reports from '@/pages/Reports'
import BatchUpload from '@/pages/BatchUpload'
import Settings from '@/pages/Settings'
import SearchList from '@/pages/searches/SearchList'
import NewSearch from '@/pages/searches/NewSearch'
import SearchDetail from '@/pages/searches/SearchDetail'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="searches" element={<SearchList />} />
        <Route path="searches/new" element={<NewSearch />} />
        <Route path="searches/:id" element={<SearchDetail />} />
        <Route path="reports" element={<Reports />} />
        <Route path="batch" element={<BatchUpload />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
