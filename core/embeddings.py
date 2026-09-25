"""OpenAI embeddings module for generating vector embeddings."""

import logging
import os
import sys
from pathlib import Path
from typing import List

import tiktoken
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load .env from backend directory
backend_dir = Path(__file__).parent.parent / "backend"
load_dotenv(backend_dir / ".env")

# Initialize OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 768
MAX_TOKENS = 8192  # OpenAI's hard limit for text-embedding-3-small
SAFE_TOKEN_LIMIT = 8000  # Leave headroom below the hard limit

# Initialize tiktoken encoder for text-embedding-3-small (cl100k_base)
_ENCODER = tiktoken.get_encoding("cl100k_base")

logger = logging.getLogger(__name__)


async def get_embedding(text: str) -> List[float]:
    """Generate embedding for text using OpenAI's text-embedding-3-small model.

    Args:
        text: Input text to embed.

    Returns:
        List of 768 floats representing the embedding vector.

    Raises:
        ValueError: If OPENAI_API_KEY is not set or API call fails.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # Safety net: count actual tokens and truncate if exceeding safe limit
    token_count = len(_ENCODER.encode(text))
    if token_count > SAFE_TOKEN_LIMIT:
        logger.warning(
            f"Input text exceeds safe token limit ({token_count} > {SAFE_TOKEN_LIMIT}). "
            f"Truncating to {SAFE_TOKEN_LIMIT} tokens."
        )
        # Truncate to safe limit
        tokens = _ENCODER.encode(text)[:SAFE_TOKEN_LIMIT]
        text = _ENCODER.decode(tokens)
        token_count = SAFE_TOKEN_LIMIT

    try:
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding
    except Exception as e:
        raise ValueError(f"Failed to generate embedding: {e}")