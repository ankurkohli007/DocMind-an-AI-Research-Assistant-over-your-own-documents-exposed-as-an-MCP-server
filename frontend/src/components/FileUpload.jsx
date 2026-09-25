import { useState } from 'react'

function FileUpload({ backendUrl, onUploadComplete }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState(null)
  const [messageType, setMessageType] = useState('') // 'success' | 'error'

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
        setMessage('Please select a PDF file.')
        setMessageType('error')
        setFile(null)
        return
      }
      setFile(selectedFile)
      setMessage(null)
    }
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!file) {
      setMessage('Please select a file first')
      setMessageType('error')
      return
    }

    setUploading(true)
    setProgress(0)
    setMessage(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      // Use XMLHttpRequest for progress tracking
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        // Use /api/v1/documents/ as specified - vite proxy handles /api -> backend
        xhr.open('POST', `${backendUrl}/api/v1/documents/`)

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            setProgress(Math.round((event.loaded / event.total) * 100))
          }
        }

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText))
          } else {
            const err = JSON.parse(xhr.responseText)
            reject(new Error(err.detail || 'Upload failed'))
          }
        }

        xhr.onerror = () => reject(new Error('Network error'))
        xhr.send(formData)
      })

      setMessage('Document uploaded and ingested successfully!')
      setMessageType('success')
      setFile(null)
      setProgress(100)
      onUploadComplete?.()
    } catch (err) {
      setMessage(err.message || 'Upload failed')
      setMessageType('error')
    } finally {
      setUploading(false)
    }
  }

  // Always render the upload UI - don't return null on initial load
  return (
    <div className="file-upload">
      <h2>Upload Document</h2>
      <form onSubmit={handleUpload}>
        <div className="file-input-wrapper">
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            disabled={uploading}
            id="pdf-upload"
          />
          <label htmlFor="pdf-upload" className="file-input-label">
            {file ? file.name : 'Choose a PDF file'}
          </label>
        </div>

        {progress > 0 && progress < 100 && (
          <div className="progress-bar" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}

        <button
          type="submit"
          disabled={uploading || !file}
          className="btn btn-primary"
        >
          {uploading ? 'Uploading...' : 'Upload & Ingest'}
        </button>
      </form>

      {message && (
        <div className={`message ${messageType}`} role="alert">
          {message}
        </div>
      )}
    </div>
  )
}

export default FileUpload