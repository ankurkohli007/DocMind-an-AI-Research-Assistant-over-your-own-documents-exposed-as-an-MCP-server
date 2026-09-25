import { useState, useEffect } from 'react'
import FileUpload from './components/FileUpload'
import ChatInterface from './components/ChatInterface'
import DocumentSidebar from './components/DocumentSidebar'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

function App() {
  const [documents, setDocuments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/documents/`)
      if (res.ok) {
        const data = await res.json()
        setDocuments(data.documents || [])
      }
    } catch (err) {
      console.error('Failed to fetch documents:', err)
    }
  }

  useEffect(() => {
    fetchDocuments()
  }, [])

  // const handleUploadComplete = (newDoc) => {
  //   setDocuments((prev) => [newDoc, ...prev])
  // }

  const handleUploadComplete = () => {
    fetchDocuments()
  }
  

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          >
            {sidebarOpen ? '◀' : '▶'}
          </button>
          <h1>DocMind</h1>
        </div>
      </header>

      <div className="main-layout">
        <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
          <DocumentSidebar
            documents={documents}
            onRefresh={fetchDocuments}
          />
        </aside>

        <main className="main-content">
          <FileUpload
            backendUrl={BACKEND_URL}
            onUploadComplete={handleUploadComplete}
          />
          <ChatInterface backendUrl={BACKEND_URL} />
        </main>
      </div>
    </div>
  )
}

export default App