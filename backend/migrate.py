#!/usr/bin/env python
"""
Standalone migration script - runs directly with psycopg2
Bypasses alembic entirely for Supabase compatibility
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def get_db_url():
    """Get database URL from environment"""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL not set in .env")
    # Convert asyncpg URL to psycopg2 URL
    return url.replace("postgresql+asyncpg://", "postgresql://")


def run_migration():
    """Run the initial schema migration"""
    url = get_db_url()
    print(f"Connecting to database...")

    # Connect with autocommit for DDL statements
    conn = psycopg2.connect(url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    try:
        print("Creating pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

        print("Creating documents table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                uploaded_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
            )
        """)

        print("Creating chunks table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id SERIAL PRIMARY KEY,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                embedding VECTOR(768) NOT NULL,
                chunk_index INTEGER NOT NULL
            )
        """)

        print("Creating queries table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
            )
        """)

        print("Creating HNSW index for cosine similarity...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)

        print("\n✅ Migration completed successfully!")

        # Verify tables exist
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('documents', 'chunks', 'queries')
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        print(f"\nCreated tables: {[t[0] for t in tables]}")

        # Verify index
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'chunks' AND indexname = 'ix_chunks_embedding_hnsw'
        """)
        idx = cur.fetchone()
        if idx:
            print(f"HNSW index: {idx[0]} ✅")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_migration()