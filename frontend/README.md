# DocMind Frontend

React + Vite frontend for the DocMind document intelligence system.

## Features

- **File Upload**: Drag-and-drop PDF upload with progress tracking
- **Chat Interface**: Ask questions about uploaded documents with cited answers
- **Document Sidebar**: List of uploaded documents with timestamps
- **Responsive Design**: Works on desktop and mobile

## Setup

```bash
cd frontend
npm install
```

## Development

```bash
npm run dev
```

The dev server runs at `http://localhost:5173` and proxies API requests to `http://localhost:8000`.

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_BACKEND_URL=http://localhost:8000
```

## Building for Production

```bash
npm run build
```

Output goes to `dist/`.

## Project Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── styles.css
│   └── components/
│       ├── FileUpload.jsx
│       ├── ChatInterface.jsx
│       └── DocumentSidebar.jsx
```

## API Endpoints Used

- `GET /documents/` - List uploaded documents
- `POST /documents/` - Upload and ingest a PDF
- `POST /queries/` - Ask a question (returns answer with citations)