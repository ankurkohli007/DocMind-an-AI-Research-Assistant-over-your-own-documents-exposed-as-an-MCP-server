function DocumentSidebar({ documents, onRefresh, backendUrl }) {
  const handleDelete = async (doc) => {
    if (!window.confirm(`Delete "${doc.filename}"? This can't be undone.`)) return
    try {
      const res = await fetch(`${backendUrl}/api/v1/documents/${doc.id}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error('Delete failed')
      onRefresh()
    } catch (err) {
      alert('Could not delete the document. Please try again.')
    }
  }

  if (!documents || documents.length === 0) {
    return (
      <div className="document-sidebar">
        <div className="sidebar-header">
          <h3>Documents</h3>
          <button onClick={onRefresh} className="btn-refresh" title="Refresh">
            ⟳
          </button>
        </div>
        <div className="empty-state">
          No documents uploaded yet.
        </div>
      </div>
    )
  }

  return (
    <div className="document-sidebar">
      <div className="sidebar-header">
        <h3>Documents ({documents.length})</h3>
        <button onClick={onRefresh} className="btn-refresh" title="Refresh">
          ⟳
        </button>
      </div>
      <ul className="document-list">
        {documents.map((doc) => (
          <li key={doc.id} className="document-item">
            <div className="doc-info">
              <span className="doc-filename" title={doc.filename}>
                {doc.filename}
              </span>
              {doc.uploaded_at && (
                <span className="doc-date">
                  {new Date(doc.uploaded_at).toLocaleDateString()}
                </span>
              )}
            </div>
            <button
              onClick={() => handleDelete(doc)}
              className="btn-delete"
              title="Delete document"
              aria-label={`Delete ${doc.filename}`}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default DocumentSidebar