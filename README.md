# DocMind — AI Research Assistant Over Your Own Documents, Exposed as an MCP Server

DocMind lets you upload your own PDFs and ask questions about them, getting answers grounded in the actual text with citations back to the source — not a hallucinated summary. The same retrieval and answering logic is also exposed as an **MCP (Model Context Protocol) server**, so an AI client like Claude Desktop can search and query your documents directly as a tool, not just through a web chat window.

**Live demo:** [Document Upload UI](https://doc-mind-an-ai-research-assistant-o.vercel.app/)
**API docs:** [Backend Test](https://docmind-an-ai-research-assistant-over.onrender.com//docs)

---

## Problem statement

Reading through long PDFs to find one answer is slow, and generic AI chatbots either can't see private documents at all or answer from general training knowledge instead of the document, with no way to tell which is which. DocMind only answers from what's actually been uploaded, always with a citation back to the exact passage it used, and does this through both a web UI and as a tool any MCP-compatible AI agent can call directly.

---

## Architecture

```
[React Frontend (Vercel)]
        |
        | HTTPS
        v
[FastAPI Backend (Render)] -------> [OpenAI API: embeddings + chat completion]
        |
        | SQL (asyncpg / SQLAlchemy)
        v
[Postgres + pgvector (Supabase)]
   - documents  (id, filename, uploaded_at)
   - chunks     (id, document_id, content, embedding vector(768), chunk_index)
   - queries    (id, question, answer, created_at)

[MCP Server — thin client, calls the deployed API]
        |
        | stdio
        v
[Claude Desktop / any MCP client]
```

Two client surfaces (the web frontend, and the MCP server) both go through the same FastAPI backend and the same database. A document uploaded through the web app is immediately answerable through the MCP tools, and vice versa, because there is exactly one source of truth: the Postgres database.

### Why the MCP server calls the API instead of the database directly

The original design had `mcp_server.py` connect to Supabase directly, sharing `core/` logic with the FastAPI routes but bypassing the API layer. This worked from Render's servers but was unreliable from a home network: large payloads (the ~14KB embedding vectors used in similarity search) would hang or drop mid-query, while small queries worked fine — a sign of a network path issue, not a code bug. Rather than fight an unreliable local network connection to the database, the MCP server was changed to call the already-deployed, already-reliable API over HTTPS, the same way the web frontend does. This also means the local MCP config no longer needs database credentials or an OpenAI key on disk — only the public API URL.

---

## Why these specific platforms

| Choice | Why |
|---|---|
| **Supabase (Postgres)** | Free tier includes a real, always-on Postgres instance with the `pgvector` extension pre-installable, which is what makes vector similarity search possible without running a separate vector database. Free vector databases (Pinecone, etc.) exist but add a second system to manage; Postgres + pgvector keeps relational data (documents, chunks, query logs) and vector search in one database, one connection, one set of joins. |
| **Render (backend hosting)** | Free tier that runs a real, always-listening web service (not just static files), which FastAPI needs. The free tier sleeps after inactivity and has a cold-start delay on the first request — a known, worthwhile tradeoff for a portfolio project with no ongoing cost. |
| **Vercel (frontend hosting)** | Free, purpose-built for exactly this: a Vite/React static build with instant global CDN delivery and zero-config deploys from GitHub. |
| **OpenAI API** | Used for both embeddings (`text-embedding-3-small`, truncated to 768 dimensions via the API's native `dimensions` parameter — not manual vector slicing, which would break cosine similarity) and answer generation (`gpt-4o-mini`). Not free, but low-cost at this scale; a fully free alternative (local models via Ollama) is a possible future iteration. |
| **MCP (Model Context Protocol)** | The emerging standard for exposing tools to AI agents/clients like Claude Desktop, rather than just to a custom web UI. This is what turns DocMind from "a RAG chatbot" into a tool usable by any MCP-aware AI system. |

---

## Database: what and why

**PostgreSQL with the `pgvector` extension**, hosted on Supabase.

- `documents` — one row per uploaded PDF (id, filename, uploaded_at)
- `chunks` — one row per text chunk (id, document_id FK, content, `embedding vector(768)`, chunk_index)
- `queries` — a log of every question asked and its answer, for basic history/auditing

An **HNSW index** (`vector_cosine_ops`) is built on `chunks.embedding` to make cosine-similarity search fast at scale — without it, a similarity search would require scanning every row and computing distance one by one; HNSW is an approximate-nearest-neighbor index structure that makes this sub-linear.

**Why relational Postgres instead of a dedicated vector DB:** the chunks need a real foreign key to their parent document (for citations, for deletion cascades, for listing "what's been uploaded"), and the query log is inherently relational. Pgvector means one database serves both needs instead of syncing two systems.

---

## RAG architecture: what kind, and why

DocMind uses **naive (single-hop) RAG**, not Graph RAG, not multi-hop/agentic RAG, and not a re-ranking pipeline. Concretely:

1. **Chunking:** each PDF is split into overlapping, token-counted chunks (~500 tokens, ~50 token overlap), using `tiktoken` to count actual tokens rather than approximating from word/character count — an early bug in this project used a word-count approximation, which produced chunks that looked small but were actually oversized once the PDF's raw text had lost normal whitespace (common with multi-column academic PDFs), causing OpenAI's 8192-token embedding limit to be exceeded silently.
2. **Embedding:** each chunk is embedded once at ingestion time and stored with its vector.
3. **Retrieval:** a question is embedded the same way, and the top-k (5) most similar chunks are retrieved by cosine distance, in a single database query — no multi-step retrieval, no query decomposition, no graph traversal between entities.
4. **Generation:** the retrieved chunks are passed as context to the LLM in one prompt, which answers using only that context and returns citations (filename + snippet + similarity score) alongside the answer.

**Why naive RAG and not Graph RAG:** Graph RAG builds an explicit knowledge graph of entities and relationships extracted from documents, and answers by traversing that graph — it's stronger for multi-hop reasoning across many interconnected documents ("how does concept A in document 1 relate to concept B in document 3") but is significantly more expensive to build (an extra LLM-driven entity/relationship extraction pass over every document) and unnecessary for DocMind's actual use case: answering questions grounded in one or a few documents at a time, where direct semantic-similarity retrieval already finds the right passages. Naive RAG is the right tool for "what does this document say about X", not a lesser choice for lack of sophistication — knowing when *not* to reach for a heavier architecture is itself part of the design decision, worth being able to explain as such.

**A known limitation, worth raising directly:** retrieval currently searches across *all* uploaded documents with no way to scope a question to a single one. A generic question like "what is this paper about?" with several unrelated PDFs uploaded returns a poor answer, because there's no "current document" concept, only a global similarity search. The fix is a straightforward one — adding an optional `document_id` filter to the retrieval query and the API/MCP tool signatures — but it's not implemented yet, and is listed under "what I'd build next" below.

---

## How the pieces work together

1. **Upload** — PDF → text extraction (pdfplumber/pypdf) → token-based chunking → OpenAI embedding per chunk → stored in Postgres.
2. **Ask (web)** — question → embedded → pgvector cosine search → top chunks → LLM prompt → answer + citations → shown in the React UI.
3. **Ask (MCP)** — same question, but the request comes from Claude Desktop calling the `ask_documents` tool, which is a thin wrapper that POSTs to the same `/api/v1/queries/` endpoint the web UI uses. Same backend, same database, same answer.

---

## MCP tools exposed

| Tool | What it does |
|---|---|
| `ask_documents(question)` | Full RAG: retrieves relevant chunks and returns a synthesized, cited answer |
| `search_documents(query)` | Returns the raw matching passages and similarity scores behind an answer |
| `list_documents()` | Lists every uploaded document's filename and upload date |

---

## Local setup

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`backend/.env`:
```
DATABASE_URL=postgresql+asyncpg://<your-supabase-connection-string>
OPENAI_API_KEY=<your-openai-api-key>
SECRET_KEY=<any-random-string>
```

```bash
alembic upgrade head
uvicorn app.main:app --reload
```
API: `http://localhost:8000` · Docs: `http://localhost:8000/docs`

### Frontend
```bash
cd frontend
npm install
```
`frontend/.env`:
```
VITE_BACKEND_URL=http://localhost:8000
```
```bash
npm run dev
```
`http://localhost:5173`

### MCP server (Claude Desktop)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
```json
{
  "mcpServers": {
    "docmind": {
      "command": "/absolute/path/to/DocMind/backend/.venv/bin/python",
      "args": ["/absolute/path/to/DocMind/backend/mcp_server.py"],
      "env": {
        "DOCMIND_API_URL": "https://your-render-url-here"
      }
    }
  }
}
```
Fully restart Claude Desktop after saving. "docmind" should appear under Connectors with three tools available.

---

## Deployment

- **Backend → Render** (free tier): root directory `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, environment variables `DATABASE_URL`, `OPENAI_API_KEY`, `SECRET_KEY`, `PYTHON_VERSION=3.10.13` set explicitly (Render's newer default Python version broke a dependency that had no prebuilt wheel for it).
- **Frontend → Vercel** (free tier): root directory `frontend`, `VITE_BACKEND_URL` set to the live Render URL.
- **Database → Supabase** (free tier): Postgres with `pgvector` enabled under Database → Extensions.

---

## Real problems hit during development, and how they were diagnosed

Worth knowing well for an interview — these were genuine bugs, not hypothetical ones:

**1. Silent chunk-size bug from word-count token estimation.** The chunker approximated tokens from word count (`words_per_token ≈ 0.75`), which broke whenever PDF text extraction lost whitespace (common in tables and multi-column layouts) — a chunk that looked small by word count was secretly much larger in real tokens, causing OpenAI's 8192-token embedding limit to be exceeded. **Fix:** count tokens directly with `tiktoken` instead of estimating, plus a safety truncation as a second line of defense.

**2. pgvector type not recognized by a raw asyncpg connection.** Supabase installs the `vector` extension into its `extensions` schema, not `public`, but the Python `pgvector` library's `register_vector()` (in the version used) only looks in `public` — producing `unknown type: public.vector`. **Fix:** `ALTER EXTENSION vector SET SCHEMA public;` in Supabase, matching the library's expectation, rather than patching the library.

**3. Dropped connections under Supabase's pooler.** Sequential one-row-at-a-time inserts during ingestion kept a transaction open long enough for Supabase's connection pooler to kill it mid-operation. **Fix:** `statement_cache_size=0` (required for pgbouncer transaction-mode pooling) and batched inserts (`executemany`) instead of one round-trip per row.

**4. SSL handshake hanging on a home network, but not from Render's servers.** The exact same connection code that answered instantly from Render would hang for minutes locally. Diagnosed by testing progressively larger payloads directly against the database, bypassing the app entirely: a plain `SELECT 1` worked, but anything carrying a large parameter (like a 768-float embedding, ~14KB) hung and then failed with `connection was closed in the middle of operation` — pointing to a local network path dropping larger packets, not a code defect. **Resolution:** rather than fight an unreliable local network path, the MCP server was redesigned to call the already-deployed API over HTTPS instead of connecting to the database directly.

**5. Python version mismatch on Render.** Render defaulted to a newer Python version than local development used, and `pydantic-core` had no prebuilt wheel for it, forcing a Rust compile that failed in Render's read-only build environment. **Fix:** explicit `PYTHON_VERSION` environment variable pinning the same version used locally.

**6. CORS trailing-slash mismatch.** `allow_origins` had a trailing slash on the deployed frontend's URL; browsers send the `Origin` header without one, so the exact-string match silently failed every cross-origin request. A reminder that CORS origin matching is literal, not path-normalized.

---

## Known limitations (honest, for the README and for interviews)

- **No authentication.** Anyone with the URL can upload, query, and delete documents. Fine for a personal demo with only non-sensitive documents; a real product needs per-user accounts (Supabase Auth) with documents scoped by `user_id`.
- **No per-document scoping in retrieval.** Questions search across all uploaded documents at once; there's no way to ask "only within this paper."
- **Render free tier cold starts.** The first request after a period of inactivity can take 30–60 seconds.
- **Single global RAG pass, no re-ranking or query rewriting.** Retrieval is a direct top-k similarity search; there's no step that reformulates ambiguous questions or re-ranks results with a cross-encoder before generation.

---

## What I'd build next

- Per-user accounts and document ownership (Supabase Auth)
- A `document_id` filter for scoped retrieval
- A local-first mode: index PDFs from a local folder via the MCP server without uploading them to the cloud database at all, for users who don't want documents leaving their machine
- Re-ranking retrieved chunks with a cross-encoder before generation, for higher answer precision on larger document sets
- Streaming responses in the chat UI

---

<!-- ## Video

[to be soon, stay tuned.....] -->
