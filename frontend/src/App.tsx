import { Route, Routes } from 'react-router'
import { ChatProvider } from './chat/ChatProvider'
import { Layout } from './components/Layout'
import { ChatPage } from './pages/ChatPage'
import { DesignPage } from './pages/DesignPage'
import { LibraryPage } from './pages/LibraryPage'
import { MetricsPage } from './pages/MetricsPage'
import { NotFoundPage } from './pages/NotFoundPage'

export function App() {
  return (
    <ChatProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<LibraryPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="metrics" element={<MetricsPage />} />
          {import.meta.env.DEV && <Route path="design" element={<DesignPage />} />}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ChatProvider>
  )
}
