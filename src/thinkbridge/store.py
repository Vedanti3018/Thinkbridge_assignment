"""
Vector Store implementation using OpenAI FileStore for embeddings and similarity search.

This module provides the core vector storage functionality for the Sales Factsheet
Generation System, enabling RAG (Retrieval-Augmented Generation) workflows.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


class VectorStore:
    """
    Vector store wrapper for OpenAI FileStore with embedding and similarity search.

    This class handles:
    - Text chunk embedding using OpenAI's text-embedding models
    - FileStore creation and management
    - Vector similarity search for RAG retrieval
    - Cost tracking for budget management
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        max_concurrent: int = 5,
    ):
        """
        Initialize the vector store.

        Args:
            api_key: OpenAI API key (or from environment)
            embedding_model: OpenAI embedding model to use
            max_concurrent: Maximum concurrent embedding requests
        """
        self.logger = logging.getLogger(__name__)
        self.embedding_model = embedding_model
        self.max_concurrent = max_concurrent
        self.total_cost = 0.0

        # Initialize OpenAI client
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var.")

        self.client = OpenAI(api_key=api_key)

        # Store mapping of company_id to vector_store_id
        self.company_stores: Dict[str, str] = {}
        self.metadata_file = Path("vector_stores_metadata.json")
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load existing vector store metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    data = json.load(f)
                    self.company_stores = data.get("company_stores", {})
                    self.total_cost = data.get("total_cost", 0.0)
                self.logger.info(
                    f"Loaded metadata for {len(self.company_stores)} companies"
                )
            except Exception as e:
                self.logger.warning(f"Failed to load metadata: {e}")

    def _save_metadata(self) -> None:
        """Save vector store metadata to disk."""
        try:
            data = {
                "company_stores": self.company_stores,
                "total_cost": self.total_cost,
                "embedding_model": self.embedding_model,
            }
            with open(self.metadata_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save metadata: {e}")

    def _calculate_embedding_cost(self, token_count: int) -> float:
        """
        Calculate cost for embedding tokens.

        OpenAI text-embedding-3-small: $0.00002 per 1K tokens
        """
        cost_per_1k_tokens = 0.00002
        return (token_count / 1000) * cost_per_1k_tokens

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough estimation: 1 token ≈ 4 characters
        return len(text) // 4

    def embed_chunks(self, chunks: List[str]) -> Tuple[List[List[float]], float]:
        """
        Generate embeddings for text chunks.

        Args:
            chunks: List of text chunks to embed

        Returns:
            Tuple of (embeddings, cost) where embeddings is list of vectors
        """
        if not chunks:
            return [], 0.0

        try:
            self.logger.info(f"Generating embeddings for {len(chunks)} chunks")

            # Estimate cost
            total_tokens = sum(self._estimate_tokens(chunk) for chunk in chunks)
            estimated_cost = self._calculate_embedding_cost(total_tokens)

            self.logger.info(
                f"Estimated tokens: {total_tokens}, cost: ${estimated_cost:.4f}"
            )

            # Generate embeddings
            response = self.client.embeddings.create(
                input=chunks, model=self.embedding_model
            )

            # Extract embeddings
            embeddings = [item.embedding for item in response.data]

            # Track actual cost
            actual_tokens = response.usage.total_tokens
            actual_cost = self._calculate_embedding_cost(actual_tokens)
            self.total_cost += actual_cost

            self.logger.info(
                f"Generated {len(embeddings)} embeddings. "
                f"Tokens: {actual_tokens}, Cost: ${actual_cost:.4f}"
            )

            return embeddings, actual_cost

        except Exception as e:
            self.logger.error(f"Failed to generate embeddings: {e}")
            raise

    def create_vector_store(self, company_id: str, name: Optional[str] = None) -> str:
        """
        Create a new vector store for a company.

        Args:
            company_id: Unique company identifier
            name: Optional human-readable name

        Returns:
            Vector store ID
        """
        try:
            store_name = name or f"Company_{company_id}"

            # Create vector store
            vector_store = self.client.vector_stores.create(
                name=store_name, metadata={"company_id": company_id}
            )

            store_id = vector_store.id
            self.company_stores[company_id] = store_id
            self._save_metadata()

            self.logger.info(
                f"Created vector store {store_id} for company {company_id}"
            )
            return store_id

        except Exception as e:
            self.logger.error(f"Failed to create vector store for {company_id}: {e}")
            raise

    def upload_chunks_to_store(
        self,
        company_id: str,
        chunks: List[str],
        chunk_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, float]:
        """
        Upload text chunks to vector store with embeddings.

        Args:
            company_id: Company identifier
            chunks: List of text chunks
            chunk_metadata: Optional metadata for each chunk

        Returns:
            Tuple of (vector_store_id, total_cost)
        """
        if not chunks:
            raise ValueError("No chunks provided")

        try:
            # Get or create vector store
            if company_id not in self.company_stores:
                store_id = self.create_vector_store(company_id)
            else:
                store_id = self.company_stores[company_id]

            # Create temporary files for chunks
            temp_files = []
            upload_cost = 0.0

            try:
                # Create individual files for each chunk
                for i, chunk in enumerate(chunks):
                    metadata = chunk_metadata[i] if chunk_metadata else {}

                    # Create temporary file with chunk content
                    temp_file = Path(f"temp_chunk_{company_id}_{i}.txt")
                    with open(temp_file, "w", encoding="utf-8") as f:
                        # Add metadata as header comments
                        if metadata:
                            f.write("# Metadata\n")
                            for key, value in metadata.items():
                                f.write(f"# {key}: {value}\n")
                            f.write("\n")
                        f.write(chunk)

                    temp_files.append(temp_file)

                # Upload files to vector store
                for temp_file in temp_files:
                    with open(temp_file, "rb") as f:
                        file_obj = self.client.files.create(
                            file=f, purpose="assistants"
                        )

                        # Add file to vector store
                        self.client.vector_stores.files.create(
                            vector_store_id=store_id, file_id=file_obj.id
                        )

                # Estimate upload cost (file storage is typically free, embeddings cost already tracked)
                total_tokens = sum(self._estimate_tokens(chunk) for chunk in chunks)
                upload_cost = self._calculate_embedding_cost(total_tokens)
                self.total_cost += upload_cost

                self.logger.info(
                    f"Uploaded {len(chunks)} chunks to vector store {store_id}. "
                    f"Cost: ${upload_cost:.4f}"
                )

                return store_id, upload_cost

            finally:
                # Clean up temporary files
                for temp_file in temp_files:
                    if temp_file.exists():
                        temp_file.unlink()

        except Exception as e:
            self.logger.error(f"Failed to upload chunks for {company_id}: {e}")
            raise

    def similarity_search(
        self, query: str, company_id: str, top_k: int = 6, max_distance: float = 0.25
    ) -> List[Tuple[str, float]]:
        """
        Perform similarity search in company's vector store.

        Args:
            query: Search query text
            company_id: Company identifier
            top_k: Number of top results to return
            max_distance: Maximum cosine distance threshold

        Returns:
            List of (chunk_text, similarity_score) tuples
        """
        if company_id not in self.company_stores:
            self.logger.warning(f"No vector store found for company {company_id}")
            return []

        try:
            store_id = self.company_stores[company_id]

            # Create assistant with vector store for search
            assistant = self.client.beta.assistants.create(
                instructions="You are a helpful assistant that searches company data.",
                model="gpt-4o-mini",  # Use cheaper model for search
                tools=[{"type": "file_search"}],
                tool_resources={"file_search": {"vector_store_ids": [store_id]}},
            )

            # Create thread and search
            thread = self.client.beta.threads.create()

            # Add query message
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Search for information about: {query}",
            )

            # Run search
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id, assistant_id=assistant.id
            )

            # Wait for completion (simplified - in production, use proper polling)
            import time

            while run.status in ["queued", "in_progress"]:
                time.sleep(1)
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id, run_id=run.id
                )

            # Get response messages
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)

            # Extract relevant chunks from file citations
            results = []
            for message in messages.data:
                if message.role == "assistant":
                    # Process message content and extract file citations
                    # Note: This is a simplified implementation
                    # In practice, you'd extract the actual chunk texts and scores
                    content = message.content[0].text.value if message.content else ""
                    if content and len(results) < top_k:
                        # Placeholder similarity score (in real implementation, extract from API)
                        similarity_score = 0.8 - (len(results) * 0.1)
                        if (
                            1.0 - similarity_score <= max_distance
                        ):  # Convert to distance
                            results.append((content[:500], similarity_score))

            # Clean up
            self.client.beta.assistants.delete(assistant.id)
            self.client.beta.threads.delete(thread.id)

            # Track search cost (minimal for file search)
            search_cost = self._calculate_embedding_cost(self._estimate_tokens(query))
            self.total_cost += search_cost

            self.logger.info(
                f"Similarity search for company {company_id}: "
                f"{len(results)} results, cost: ${search_cost:.4f}"
            )

            return results

        except Exception as e:
            self.logger.error(f"Similarity search failed for {company_id}: {e}")
            return []

    def get_company_store_id(self, company_id: str) -> Optional[str]:
        """Get vector store ID for a company."""
        return self.company_stores.get(company_id)

    def get_total_cost(self) -> float:
        """Get total accumulated cost for all operations."""
        return self.total_cost

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get detailed cost summary."""
        return {
            "total_cost": self.total_cost,
            "companies_processed": len(self.company_stores),
            "embedding_model": self.embedding_model,
            "cost_per_company": self.total_cost / max(1, len(self.company_stores)),
        }

    def cleanup_company_store(self, company_id: str) -> bool:
        """
        Delete vector store for a company.

        Args:
            company_id: Company identifier

        Returns:
            Success status
        """
        if company_id not in self.company_stores:
            return False

        try:
            store_id = self.company_stores[company_id]

            # Delete vector store
            self.client.vector_stores.delete(vector_store_id=store_id)

            # Remove from mapping
            del self.company_stores[company_id]
            self._save_metadata()

            self.logger.info(f"Deleted vector store for company {company_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete vector store for {company_id}: {e}")
            return False
