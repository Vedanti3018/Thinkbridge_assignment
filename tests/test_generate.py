"""
Unit tests for the generation engine module.
"""

import unittest
from unittest.mock import Mock, patch

import pytest

from thinkbridge.generate import FactsheetGenerator


class TestFactsheetGenerator(unittest.TestCase):
    """Test cases for FactsheetGenerator class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Mock dependencies to avoid real API calls
        with (
            patch("thinkbridge.generate.OpenAI"),
            patch("thinkbridge.generate.VectorStore"),
            patch("thinkbridge.generate.TemplateManager"),
        ):
            self.generator = FactsheetGenerator(
                openai_api_key="test_key",
                model="gpt-4",
                max_tokens=1000,
                temperature=0.3,
            )

    def test_init_default_params(self) -> None:
        """Test initialization with default parameters."""
        with (
            patch("thinkbridge.generate.OpenAI"),
            patch("thinkbridge.generate.VectorStore"),
            patch("thinkbridge.generate.TemplateManager"),
        ):
            generator = FactsheetGenerator(openai_api_key="test_key")

            assert generator.model == "gpt-4"
            assert generator.max_tokens == 2000
            assert generator.temperature == 0.3
            assert generator.target_word_count == 800
            assert generator.top_k_chunks == 6

    def test_init_custom_params(self) -> None:
        """Test initialization with custom parameters."""
        with (
            patch("thinkbridge.generate.OpenAI"),
            patch("thinkbridge.generate.VectorStore"),
            patch("thinkbridge.generate.TemplateManager"),
        ):
            generator = FactsheetGenerator(
                openai_api_key="test_key",
                model="gpt-3.5-turbo",
                max_tokens=1500,
                temperature=0.7,
            )

            assert generator.model == "gpt-3.5-turbo"
            assert generator.max_tokens == 1500
            assert generator.temperature == 0.7

    def test_init_missing_api_key(self) -> None:
        """Test initialization without API key raises error."""
        with (
            patch("thinkbridge.generate.VectorStore"),
            patch("thinkbridge.generate.TemplateManager"),
            patch.dict("os.environ", {}, clear=True),
        ):
            with pytest.raises(ValueError, match="OpenAI API key required"):
                FactsheetGenerator()

    def test_extract_company_name(self) -> None:
        """Test company name extraction from URLs."""
        test_cases = [
            ("https://www.example.com", "Example"),
            ("http://company.co.uk", "Company"),
            ("https://my-startup.io", "My-startup"),
            ("www.test.org", "Test"),
            ("invalid-url", "Invalid-url"),  # Takes first part
        ]

        for url, expected in test_cases:
            with self.subTest(url=url):
                result = self.generator._extract_company_name(url)
                assert result == expected

    def test_create_search_queries(self) -> None:
        """Test search query creation from template placeholders."""
        placeholders = [
            "company_overview",
            "business_focus",
            "products_services",
            "technology_stack",
            "unknown_placeholder",
        ]

        queries = self.generator._create_search_queries(placeholders)

        # Should return limited number of queries
        assert len(queries) <= 4

        # Should include company overview
        assert any("company overview" in query for query in queries)

        # Should handle known placeholders
        assert any("business focus" in query for query in queries)
        assert any("products services" in query for query in queries)

    def test_validate_word_count(self) -> None:
        """Test word count validation."""
        # Valid word count (800 words)
        valid_text = " ".join(["word"] * 800)
        is_valid, count = self.generator._validate_word_count(valid_text)
        assert is_valid is True
        assert count == 800

        # Too short (500 words)
        short_text = " ".join(["word"] * 500)
        is_valid, count = self.generator._validate_word_count(short_text)
        assert is_valid is False
        assert count == 500

        # Too long (1200 words)
        long_text = " ".join(["word"] * 1200)
        is_valid, count = self.generator._validate_word_count(long_text)
        assert is_valid is False
        assert count == 1200

        # Boundary cases
        min_valid = " ".join(["word"] * 600)
        is_valid, count = self.generator._validate_word_count(min_valid)
        assert is_valid is True
        assert count == 600

        max_valid = " ".join(["word"] * 1000)
        is_valid, count = self.generator._validate_word_count(max_valid)
        assert is_valid is True
        assert count == 1000

    def test_estimate_generation_cost(self) -> None:
        """Test generation cost estimation."""
        prompt = "This is a test prompt with some content."
        completion = "This is a generated completion with more content."

        cost = self.generator._estimate_generation_cost(prompt, completion)

        # Should return a positive float
        assert isinstance(cost, float)
        assert cost > 0
        assert cost < 1.0  # Should be reasonable for test text

    @patch("thinkbridge.generate.VectorStore")
    def test_retrieve_relevant_chunks_success(self, mock_vector_store_class) -> None:
        """Test successful chunk retrieval."""
        # Setup mock vector store
        mock_vector_store = Mock()
        mock_vector_store_class.return_value = mock_vector_store

        mock_vector_store.get_company_store_id.return_value = "vs_test123"
        mock_vector_store.similarity_search.return_value = [
            {"content": "Company overview content", "score": 0.9},
            {"content": "Business focus content", "score": 0.8},
        ]

        self.generator.vector_store = mock_vector_store

        placeholders = ["company_overview", "business_focus"]
        chunks = self.generator._retrieve_relevant_chunks(
            "https://example.com", placeholders
        )

        assert len(chunks) == 2
        assert chunks[0]["content"] == "Company overview content"
        assert chunks[1]["content"] == "Business focus content"

    @patch("thinkbridge.generate.VectorStore")
    def test_retrieve_relevant_chunks_no_store(self, mock_vector_store_class) -> None:
        """Test chunk retrieval when no vector store exists."""
        mock_vector_store = Mock()
        mock_vector_store_class.return_value = mock_vector_store

        mock_vector_store.get_company_store_id.return_value = None

        self.generator.vector_store = mock_vector_store

        chunks = self.generator._retrieve_relevant_chunks(
            "https://example.com", ["company_overview"]
        )

        assert chunks == []

    def test_create_generation_prompt(self) -> None:
        """Test generation prompt creation."""
        company_url = "https://example.com"
        industry = "Technology"
        template = "# {company_name}\n## Overview\n{company_overview}"
        evidence_chunks = [
            {"content": "Example.com is a technology company."},
            {"content": "They specialize in web services."},
        ]

        prompt = self.generator._create_generation_prompt(
            company_url, industry, template, evidence_chunks
        )

        # Check prompt includes all required elements
        assert company_url in prompt
        assert industry in prompt
        assert template in prompt
        assert "Example.com is a technology company." in prompt
        assert "They specialize in web services." in prompt
        assert str(self.generator.target_word_count) in prompt
        assert "Evidence 1:" in prompt
        assert "Evidence 2:" in prompt

    @patch("thinkbridge.generate.TemplateManager")
    @patch("thinkbridge.generate.VectorStore")
    def test_generate_factsheet_success(
        self, mock_vector_store_class, mock_template_manager_class
    ) -> None:
        """Test successful factsheet generation."""
        # Setup mocks
        mock_template_manager = Mock()
        mock_template_manager_class.return_value = mock_template_manager
        mock_template_manager.get_template.return_value = (
            "# {company_name}\n{company_overview}"
        )
        mock_template_manager.get_template_placeholders.return_value = {
            "company_name",
            "company_overview",
        }

        mock_vector_store = Mock()
        mock_vector_store_class.return_value = mock_vector_store
        mock_vector_store.get_company_store_id.return_value = "vs_test123"
        mock_vector_store.similarity_search.return_value = [
            {"content": "Example company overview content"}
        ]

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = " ".join(
            ["word"] * 800
        )  # Valid word count

        self.generator.template_manager = mock_template_manager
        self.generator.vector_store = mock_vector_store
        self.generator.openai_client.chat.completions.create.return_value = (
            mock_response
        )

        result = self.generator.generate_factsheet("https://example.com", "Technology")

        assert result["status"] == "success"
        assert result["company_url"] == "https://example.com"
        assert result["industry"] == "Technology"
        assert result["word_count"] == 800
        assert result["word_count_valid"] is True
        assert "factsheet" in result
        assert "generation_cost" in result

    @patch("thinkbridge.generate.TemplateManager")
    @patch("thinkbridge.generate.VectorStore")
    def test_generate_factsheet_no_data(
        self, mock_vector_store_class, mock_template_manager_class
    ) -> None:
        """Test factsheet generation when no data available."""
        mock_template_manager = Mock()
        mock_template_manager_class.return_value = mock_template_manager
        mock_template_manager.get_template.return_value = "# {company_name}"
        mock_template_manager.get_template_placeholders.return_value = {"company_name"}

        mock_vector_store = Mock()
        mock_vector_store_class.return_value = mock_vector_store
        mock_vector_store.get_company_store_id.return_value = None

        self.generator.template_manager = mock_template_manager
        self.generator.vector_store = mock_vector_store

        result = self.generator.generate_factsheet("https://example.com", "Technology")

        assert result["status"] == "error"
        assert "No relevant data found" in result["error"]

    @patch("thinkbridge.generate.TemplateManager")
    @patch("thinkbridge.generate.VectorStore")
    def test_generate_factsheet_word_count_retry(
        self, mock_vector_store_class, mock_template_manager_class
    ) -> None:
        """Test factsheet generation with word count retry."""
        # Setup mocks
        mock_template_manager = Mock()
        mock_template_manager_class.return_value = mock_template_manager
        mock_template_manager.get_template.return_value = "# {company_name}"
        mock_template_manager.get_template_placeholders.return_value = {"company_name"}

        mock_vector_store = Mock()
        mock_vector_store_class.return_value = mock_vector_store
        mock_vector_store.get_company_store_id.return_value = "vs_test123"
        mock_vector_store.similarity_search.return_value = [{"content": "Test content"}]

        # Mock OpenAI responses - first too short, second valid
        mock_response_short = Mock()
        mock_response_short.choices = [Mock()]
        mock_response_short.choices[0].message.content = " ".join(
            ["word"] * 500
        )  # Too short

        mock_response_valid = Mock()
        mock_response_valid.choices = [Mock()]
        mock_response_valid.choices[0].message.content = " ".join(
            ["word"] * 800
        )  # Valid

        self.generator.template_manager = mock_template_manager
        self.generator.vector_store = mock_vector_store
        self.generator.openai_client.chat.completions.create.side_effect = [
            mock_response_short,
            mock_response_valid,
        ]

        result = self.generator.generate_factsheet("https://example.com", "Technology")

        assert result["status"] == "success"
        assert result["word_count"] == 800
        assert result["word_count_valid"] is True
        assert result["attempt"] == 2  # Should show retry happened

    def test_generate_multiple_factsheets(self) -> None:
        """Test generating multiple factsheets."""
        # Mock the single generation method
        with patch.object(self.generator, "generate_factsheet") as mock_generate:
            mock_generate.side_effect = [
                {"status": "success", "company_url": "https://example1.com"},
                {"status": "success", "company_url": "https://example2.com"},
            ]

            companies = [
                ("https://example1.com", "Technology"),
                ("https://example2.com", "Construction"),
            ]

            with patch("time.sleep"):  # Speed up test
                results = self.generator.generate_multiple_factsheets(companies)

            assert len(results) == 2
            assert results[0]["company_url"] == "https://example1.com"
            assert results[1]["company_url"] == "https://example2.com"

            # Should have called generate_factsheet twice
            assert mock_generate.call_count == 2

    def test_get_cost_summary(self) -> None:
        """Test cost summary generation."""
        self.generator.total_generation_cost = 0.05

        summary = self.generator.get_cost_summary()

        assert summary["total_generation_cost"] == 0.05
        assert summary["model_used"] == "gpt-4"
        assert summary["temperature"] == 0.3
        assert summary["target_word_count"] == 800
        assert "cost_per_factsheet_avg" in summary


class TestFactsheetGeneratorIntegration(unittest.TestCase):
    """Integration tests for FactsheetGenerator with real components."""

    def setUp(self) -> None:
        """Set up integration test fixtures."""
        # Use real template manager but mock OpenAI and vector store
        with (
            patch("thinkbridge.generate.OpenAI"),
            patch("thinkbridge.generate.VectorStore"),
        ):
            self.generator = FactsheetGenerator(openai_api_key="test_key")

    def test_template_integration(self) -> None:
        """Test integration with real template manager."""
        # Should be able to get real templates
        available_templates = self.generator.template_manager.get_available_templates()
        assert len(available_templates) > 0
        assert "generic" in available_templates

        # Should be able to get template content
        template = self.generator.template_manager.get_template("technology")
        assert len(template) > 0
        assert "{company_name}" in template

    def test_search_query_generation_with_real_templates(self) -> None:
        """Test search query generation with real template placeholders."""
        placeholders = self.generator.template_manager.get_template_placeholders(
            "construction"
        )
        queries = self.generator._create_search_queries(list(placeholders))

        assert len(queries) > 0
        assert len(queries) <= 4  # Should limit queries

        # Should have meaningful queries
        all_queries_text = " ".join(queries).lower()
        assert "company" in all_queries_text or "business" in all_queries_text

    def test_prompt_creation_with_real_template(self) -> None:
        """Test prompt creation with real template."""
        template = self.generator.template_manager.get_template("technology")

        evidence_chunks = [
            {"content": "Test company is a technology startup."},
            {"content": "They develop software solutions."},
        ]

        prompt = self.generator._create_generation_prompt(
            "https://test.com", "Technology", template, evidence_chunks
        )

        # Should contain all required elements
        assert "https://test.com" in prompt
        assert "Technology" in prompt
        assert template in prompt
        assert "Test company is a technology startup." in prompt
        assert len(prompt) > 1000  # Should be substantial


if __name__ == "__main__":
    unittest.main()
