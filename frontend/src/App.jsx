import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import SearchPage from './pages/SearchPage'
import VideoPage from './pages/VideoPage'
import SliceDetailPage from './pages/SliceDetailPage'
import ChatPage from './pages/ChatPage'
import DirectMatchPage from './pages/DirectMatchPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="direct-match" element={<DirectMatchPage />} />
          <Route path="video" element={<VideoPage />} />
          <Route path="video/:videoId" element={<VideoPage />} />
          <Route path="video/:videoId/slices" element={<SliceDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App