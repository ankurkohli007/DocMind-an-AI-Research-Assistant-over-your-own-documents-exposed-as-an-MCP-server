function DocumentSidebar({ documents, onRefresh }) {
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
          </li>
        ))}
      </ul>
    </div>
  )
}

export default DocumentSidebar