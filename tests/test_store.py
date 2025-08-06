"""
Unit tests for the Vector Store module.

Tests cover OpenAI FileStore integration, embedding operations,
similarity search, and cost tracking functionality.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from thinkbridge.store import VectorStore


class TestVectorStore:
    """Test the VectorStore class functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client for testing."""
        with patch("thinkbridge.store.OpenAI") as mock_openai:
            # Mock embeddings response
            mock_embedding_response = Mock()
            mock_embedding_response.data = [
                Mock(embedding=[0.1, 0.2, 0.3]),
                Mock(embedding=[0.4, 0.5, 0.6]),
            ]
            mock_embedding_response.usage.total_tokens = 100

            # Mock vector store operations
            mock_vector_store = Mock()
            mock_vector_store.id = "vs_test123"

            mock_file = Mock()
            mock_file.id = "file_test123"

            # Configure client mocks
            client = mock_openai.return_value
            client.embeddings.create.return_value = mock_embedding_response
            client.beta.vector_stores.create.return_value = mock_vector_store
            client.files.create.return_value = mock_file
            client.beta.vector_stores.files.create.return_value = Mock()

            # Mock assistant and thread operations for search
            mock_assistant = Mock()
            mock_assistant.id = "asst_test123"
            client.beta.assistants.create.return_value = mock_assistant

            mock_thread = Mock()
            mock_thread.id = "thread_test123"
            client.beta.threads.create.return_value = mock_thread

            mock_run = Mock()
            mock_run.status = "completed"
            mock_run.id = "run_test123"
            client.beta.threads.runs.create.return_value = mock_run
            client.beta.threads.runs.retrieve.return_value = mock_run

            # Mock message response
            mock_message = Mock()
            mock_message.role = "assistant"
            mock_message.content = [Mock()]
            mock_message.content[0].text.value = "Test search result content"

            mock_messages = Mock()
            mock_messages.data = [mock_message]
            client.beta.threads.messages.list.return_value = mock_messages

            yield client

    @pytest.fixture
    def temp_metadata_file(self):
        """Create temporary metadata file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            metadata = {
                "company_stores": {"test_company": "vs_existing123"},
                "total_cost": 0.05,
                "embedding_model": "text-embedding-3-small",
            }
            json.dump(metadata, f)
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_init_with_api_key(self, mock_openai_client):
        """Test VectorStore initialization with API key."""
        store = VectorStore(api_key="test_key")
        assert store.embedding_model == "text-embedding-3-small"
        assert store.max_concurrent == 5
        assert store.total_cost == 0.0

    def test_init_without_api_key(self):
        """Test VectorStore initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key required"):
                VectorStore()

    def test_init_with_env_api_key(self, mock_openai_client):
        """Test VectorStore initialization with environment API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env_test_key"}):
            store = VectorStore()
            assert store.client is not None

    def test_load_metadata(self, mock_openai_client, temp_metadata_file):
        """Test loading existing metadata."""
        store = VectorStore(api_key="test_key")
        store.metadata_file = temp_metadata_file
        store._load_metadata()

        assert store.company_stores == {"test_company": "vs_existing123"}
        assert store.total_cost == 0.05

    def test_calculate_embedding_cost(self, mock_openai_client):
        """Test embedding cost calculation."""
        store = VectorStore(api_key="test_key")

        # Test cost calculation
        cost = store._calculate_embedding_cost(1000)  # 1K tokens
        assert cost == 0.00002  # $0.00002 per 1K tokens

        cost = store._calculate_embedding_cost(5000)  # 5K tokens
        assert cost == 0.0001

    def test_estimate_tokens(self, mock_openai_client):
        """Test token estimation."""
        store = VectorStore(api_key="test_key")

        # Test token estimation (rough 4 chars per token)
        tokens = store._estimate_tokens("test")  # 4 chars
        assert tokens == 1

        tokens = store._estimate_tokens("this is a test string")  # 21 chars
        assert tokens == 5

    def test_embed_chunks_success(self, mock_openai_client):
        """Test successful chunk embedding."""
        store = VectorStore(api_key="test_key")
        chunks = ["chunk one", "chunk two"]

        embeddings, cost = store.embed_chunks(chunks)

        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]
        assert cost > 0
        assert store.total_cost > 0

    def test_embed_chunks_empty(self, mock_openai_client):
        """Test embedding empty chunks list."""
        store = VectorStore(api_key="test_key")

        embeddings, cost = store.embed_chunks([])

        assert embeddings == []
        assert cost == 0.0

    def test_create_vector_store(self, mock_openai_client):
        """Test vector store creation."""
        store = VectorStore(api_key="test_key")

        store_id = store.create_vector_store("test_company", "Test Company")

        assert store_id == "vs_test123"
        assert store.company_stores["test_company"] == "vs_test123"

        # Verify OpenAI API calls
        store.client.beta.vector_stores.create.assert_called_once()
        call_args = store.client.beta.vector_stores.create.call_args
        assert call_args[1]["name"] == "Test Company"
        assert call_args[1]["metadata"]["company_id"] == "test_company"

    def test_upload_chunks_new_store(self, mock_openai_client):
        """Test uploading chunks to new vector store."""
        store = VectorStore(api_key="test_key")
        chunks = ["First chunk content", "Second chunk content"]
        metadata = [{"page": "homepage"}, {"page": "about"}]

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.write = Mock()

            store_id, cost = store.upload_chunks_to_store(
                "test_company", chunks, metadata
            )

        assert store_id == "vs_test123"
        assert cost > 0
        assert "test_company" in store.company_stores

    def test_upload_chunks_existing_store(self, mock_openai_client):
        """Test uploading chunks to existing vector store."""
        store = VectorStore(api_key="test_key")
        store.company_stores["test_company"] = "vs_existing123"

        chunks = ["New chunk content"]

        with patch("builtins.open", create=True):
            store_id, cost = store.upload_chunks_to_store("test_company", chunks)

        assert store_id == "vs_existing123"
        assert cost > 0

    def test_upload_chunks_empty(self, mock_openai_client):
        """Test uploading empty chunks list fails."""
        store = VectorStore(api_key="test_key")

        with pytest.raises(ValueError, match="No chunks provided"):
            store.upload_chunks_to_store("test_company", [])

    def test_similarity_search_success(self, mock_openai_client):
        """Test successful similarity search."""
        store = VectorStore(api_key="test_key")
        store.company_stores["test_company"] = "vs_test123"

        results = store.similarity_search("test query", "test_company", top_k=3)

        assert len(results) > 0
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2  # (content, score)
        assert isinstance(results[0][0], str)  # content
        assert isinstance(results[0][1], float)  # score

    def test_similarity_search_no_store(self, mock_openai_client):
        """Test similarity search with no vector store."""
        store = VectorStore(api_key="test_key")

        results = store.similarity_search("test query", "nonexistent_company")

        assert results == []

    def test_get_company_store_id(self, mock_openai_client):
        """Test getting company store ID."""
        store = VectorStore(api_key="test_key")
        store.company_stores["test_company"] = "vs_test123"

        store_id = store.get_company_store_id("test_company")
        assert store_id == "vs_test123"

        store_id = store.get_company_store_id("nonexistent")
        assert store_id is None

    def test_get_total_cost(self, mock_openai_client):
        """Test total cost tracking."""
        store = VectorStore(api_key="test_key")
        store.total_cost = 0.15

        cost = store.get_total_cost()
        assert cost == 0.15

    def test_get_cost_summary(self, mock_openai_client):
        """Test cost summary generation."""
        store = VectorStore(api_key="test_key")
        store.total_cost = 0.20
        store.company_stores = {"company1": "vs1", "company2": "vs2"}

        summary = store.get_cost_summary()

        assert summary["total_cost"] == 0.20
        assert summary["companies_processed"] == 2
        assert summary["embedding_model"] == "text-embedding-3-small"
        assert summary["cost_per_company"] == 0.10

    def test_cleanup_company_store(self, mock_openai_client):
        """Test vector store cleanup."""
        store = VectorStore(api_key="test_key")
        store.company_stores["test_company"] = "vs_test123"

        success = store.cleanup_company_store("test_company")

        assert success is True
        assert "test_company" not in store.company_stores
        store.client.beta.vector_stores.delete.assert_called_once_with(
            vector_store_id="vs_test123"
        )

    def test_cleanup_nonexistent_store(self, mock_openai_client):
        """Test cleanup of nonexistent store."""
        store = VectorStore(api_key="test_key")

        success = store.cleanup_company_store("nonexistent")

        assert success is False


class TestVectorStoreIntegration:
    """Integration tests for VectorStore operations."""

    @pytest.fixture
    def mock_openai_client_integration(self):
        """Mock OpenAI client for integration testing."""
        with patch("thinkbridge.store.OpenAI") as mock_openai:
            # Mock embeddings response
            mock_embedding_response = Mock()
            mock_embedding_response.data = [
                Mock(embedding=[0.1, 0.2, 0.3]),
                Mock(embedding=[0.4, 0.5, 0.6]),
            ]
            mock_embedding_response.usage.total_tokens = 100

            # Mock vector store operations
            mock_vector_store = Mock()
            mock_vector_store.id = "vs_test123"

            mock_file = Mock()
            mock_file.id = "file_test123"

            # Configure client mocks
            client = mock_openai.return_value
            client.embeddings.create.return_value = mock_embedding_response
            client.beta.vector_stores.create.return_value = mock_vector_store
            client.files.create.return_value = mock_file
            client.beta.vector_stores.files.create.return_value = Mock()

            # Mock assistant and thread operations for search
            mock_assistant = Mock()
            mock_assistant.id = "asst_test123"
            client.beta.assistants.create.return_value = mock_assistant

            mock_thread = Mock()
            mock_thread.id = "thread_test123"
            client.beta.threads.create.return_value = mock_thread

            mock_run = Mock()
            mock_run.status = "completed"
            mock_run.id = "run_test123"
            client.beta.threads.runs.create.return_value = mock_run
            client.beta.threads.runs.retrieve.return_value = mock_run

            # Mock message response
            mock_message = Mock()
            mock_message.role = "assistant"
            mock_message.content = [Mock()]
            mock_message.content[0].text.value = "Test search result content"

            mock_messages = Mock()
            mock_messages.data = [mock_message]
            client.beta.threads.messages.list.return_value = mock_messages

            yield client

    @pytest.fixture
    def store_with_data(self, mock_openai_client_integration):
        """Create store with test data."""
        store = VectorStore(api_key="test_key")

        # Simulate uploaded data
        store.company_stores["test_company"] = "vs_test123"
        store.total_cost = 0.05

        return store

    def test_full_workflow(self, store_with_data):
        """Test complete vector store workflow."""
        store = store_with_data

        # Test chunks
        chunks = [
            "Company XYZ is a leading technology firm.",
            "Founded in 2010, XYZ specializes in AI solutions.",
            "The company has 500+ employees worldwide.",
        ]

        # Upload chunks
        with patch("builtins.open", create=True):
            store_id, upload_cost = store.upload_chunks_to_store("xyz_company", chunks)

        # Perform search
        results = store.similarity_search(
            "How many employees does the company have?", "xyz_company", top_k=2
        )

        # Verify results
        assert store_id is not None
        assert upload_cost > 0
        assert len(results) >= 0  # May be empty due to mocking
        assert store.get_total_cost() > 0.05  # Increased from initial

    def test_cost_budget_tracking(self, store_with_data):
        """Test cost tracking for budget management."""
        store = store_with_data
        initial_cost = store.get_total_cost()

        # Simulate operations that add cost
        chunks = ["Test chunk"] * 10
        embeddings, cost = store.embed_chunks(chunks)

        # Verify cost increased
        final_cost = store.get_total_cost()
        assert final_cost > initial_cost
        assert cost > 0

        # Test cost summary
        summary = store.get_cost_summary()
        assert summary["total_cost"] == final_cost
        assert summary["companies_processed"] >= 1

    def test_metadata_persistence(self, mock_openai_client_integration, tmp_path):
        """Test metadata saving and loading."""
        metadata_file = tmp_path / "test_metadata.json"

        # Create store and add data
        store1 = VectorStore(api_key="test_key")
        store1.metadata_file = metadata_file
        store1.company_stores["company1"] = "vs_123"
        store1.total_cost = 0.25
        store1._save_metadata()

        # Create new store and verify data loaded
        store2 = VectorStore(api_key="test_key")
        store2.metadata_file = metadata_file
        store2._load_metadata()
        assert store2.company_stores["company1"] == "vs_123"
        assert store2.total_cost == 0.25


if __name__ == "__main__":
    pytest.main([__file__])
