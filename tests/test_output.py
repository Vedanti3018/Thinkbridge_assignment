"""
Unit tests for the output/writer module.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from thinkbridge.output import FactsheetWriter


class TestFactsheetWriter(unittest.TestCase):
    """Test cases for FactsheetWriter class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create temporary directory for test outputs
        self.temp_dir = tempfile.mkdtemp()
        self.writer = FactsheetWriter(output_dir=self.temp_dir)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Clean up any files created during tests
        try:
            self.writer.cleanup_files()
        except Exception:
            pass

        # Remove temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_default_output_dir(self) -> None:
        """Test initialization with default output directory."""
        writer = FactsheetWriter()
        assert writer.output_dir == Path("factsheets")
        assert writer.min_word_count == 600
        assert writer.max_word_count == 1000

    def test_init_custom_output_dir(self) -> None:
        """Test initialization with custom output directory."""
        import tempfile

        custom_dir = tempfile.mkdtemp()
        writer = FactsheetWriter(output_dir=custom_dir)
        assert str(writer.output_dir) == custom_dir
        # Cleanup
        import shutil

        shutil.rmtree(custom_dir)

    def test_slugify_company_name_with_name(self) -> None:
        """Test company name slugification with provided name."""
        test_cases = [
            ("TechCorp Inc.", "techcorp"),
            ("Amazing Company!", "amazing-company"),
            ("Multi   Word    Name", "multi-word-name"),
            ("Special@#$%Characters", "specialcharacters"),
            ("Hyphen-Already-Present", "hyphen-already-present"),
            ("A", "example"),  # Short name falls back to URL
        ]

        for name, expected in test_cases:
            with self.subTest(name=name):
                result = self.writer.slugify_company_name("https://example.com", name)
                assert result == expected

    def test_slugify_company_name_from_url(self) -> None:
        """Test company name slugification from URL when no name provided."""
        test_cases = [
            ("https://example.com", "example"),
            ("http://company.co.uk", "company"),
            ("https://www.startup.io", "startup"),
            ("test-site.org", "test-site"),
        ]

        for url, expected in test_cases:
            with self.subTest(url=url):
                result = self.writer.slugify_company_name(url)
                assert result == expected

    def test_slugify_company_name_fallback(self) -> None:
        """Test slugification fallback for edge cases."""
        # Very short result should use URL fallback
        result = self.writer.slugify_company_name("https://ab.com", "A")
        assert result == "ab"

        # Empty name should use URL
        result = self.writer.slugify_company_name("https://example.com", "")
        assert result == "example"

        # Invalid URL should still try to extract from the string
        result = self.writer.slugify_company_name("not-a-url", "")
        assert result == "not-a-url"

    def test_extract_company_name_from_factsheet(self) -> None:
        """Test company name extraction from factsheet content."""
        # Test with typical factsheet format
        factsheet1 = """# TechCorp Solutions - Technology Company Factsheet

## Company Overview
TechCorp is a leading technology company...
"""
        result = self.writer._extract_company_name_from_factsheet(factsheet1)
        assert result == "TechCorp Solutions"

        # Test with different format
        factsheet2 = """# Amazing Startup Inc.

## About the Company
Amazing Startup is...
"""
        result = self.writer._extract_company_name_from_factsheet(factsheet2)
        assert result == "Amazing Startup"

        # Test with no clear heading
        factsheet3 = """This is not a proper factsheet format."""
        result = self.writer._extract_company_name_from_factsheet(factsheet3)
        assert result is None

    def test_validate_word_count(self) -> None:
        """Test word count validation."""
        # Valid word count (800 words)
        valid_text = " ".join(["word"] * 800)
        is_valid, count = self.writer.validate_word_count(valid_text)
        assert is_valid is True
        assert count == 800

        # Too short (500 words)
        short_text = " ".join(["word"] * 500)
        is_valid, count = self.writer.validate_word_count(short_text)
        assert is_valid is False
        assert count == 500

        # Too long (1200 words)
        long_text = " ".join(["word"] * 1200)
        is_valid, count = self.writer.validate_word_count(long_text)
        assert is_valid is False
        assert count == 1200

        # Boundary cases
        min_valid = " ".join(["word"] * 600)
        is_valid, count = self.writer.validate_word_count(min_valid)
        assert is_valid is True
        assert count == 600

        max_valid = " ".join(["word"] * 1000)
        is_valid, count = self.writer.validate_word_count(max_valid)
        assert is_valid is True
        assert count == 1000

    def test_write_factsheet_success(self) -> None:
        """Test successful factsheet writing."""
        company_url = "https://example.com"
        factsheet_content = """# Example Corp - Technology Company

## Company Overview
""" + " ".join(
            ["word"] * 800
        )  # Valid word count

        result = self.writer.write_factsheet(company_url, factsheet_content)

        assert result["status"] == "success"
        assert result["company_url"] == company_url
        assert result["slug"] == "example"
        assert result["filename"] == "example.md"
        assert result["word_count"] >= 800  # Should be around 800 + heading words
        assert result["word_count_valid"] is True
        assert "timestamp" in result
        assert "file_size_bytes" in result

        # Check file was actually created
        filepath = Path(result["filepath"])
        assert filepath.exists()

        # Check file content
        with open(filepath, "r", encoding="utf-8") as f:
            written_content = f.read()
        assert written_content == factsheet_content

    def test_write_factsheet_invalid_word_count(self) -> None:
        """Test factsheet writing with invalid word count."""
        company_url = "https://example.com"
        factsheet_content = """# Example Corp

## Short Content
""" + " ".join(
            ["word"] * 100
        )  # Too short

        result = self.writer.write_factsheet(company_url, factsheet_content)

        # Should still write the file but mark as invalid word count
        assert result["status"] == "success"
        assert result["word_count_valid"] is False
        assert result["word_count"] >= 100  # Should be around 100 + heading words

    def test_write_factsheet_file_exists(self) -> None:
        """Test factsheet writing when file already exists."""
        company_url = "https://example.com"
        factsheet_content = "# Example Corp\n\nContent here."

        # Write first time
        result1 = self.writer.write_factsheet(company_url, factsheet_content)
        assert result1["status"] == "success"

        # Write second time without overwrite
        result2 = self.writer.write_factsheet(
            company_url, factsheet_content, overwrite=False
        )
        assert result2["status"] == "skipped"
        assert result2["reason"] == "file_exists"

        # Write second time with overwrite
        result3 = self.writer.write_factsheet(
            company_url, factsheet_content, overwrite=True
        )
        assert result3["status"] == "success"

    def test_write_factsheet_with_metadata(self) -> None:
        """Test factsheet writing with generation metadata."""
        company_url = "https://example.com"
        factsheet_content = "# Example Corp\n\n" + " ".join(["word"] * 700)
        metadata = {"model": "gpt-4", "cost": 0.05, "generation_time": 10.5}

        result = self.writer.write_factsheet(company_url, factsheet_content, metadata)

        assert result["status"] == "success"
        assert "generation_metadata" in result
        assert result["generation_metadata"] == metadata

    def test_write_accuracy_report_success(self) -> None:
        """Test successful accuracy report writing."""
        company_url = "https://example.com"
        accuracy_content = """# Example Corp - Accuracy Report

## Validation Results
Accuracy score: 0.85
"""

        result = self.writer.write_accuracy_report(company_url, accuracy_content)

        assert result["status"] == "success"
        assert result["company_url"] == company_url
        assert "example-corp" in result["slug"]  # Should contain company name
        assert result["filename"].endswith("_accuracy.md")
        assert "timestamp" in result

        # Check file was actually created
        filepath = Path(result["filepath"])
        assert filepath.exists()

        # Check file content
        with open(filepath, "r", encoding="utf-8") as f:
            written_content = f.read()
        assert written_content == accuracy_content

    def test_write_company_files_complete(self) -> None:
        """Test writing both factsheet and accuracy report."""
        company_url = "https://example.com"
        factsheet_content = "# Example Corp\n\n" + " ".join(["word"] * 700)
        accuracy_content = "# Example Corp - Accuracy Report\n\nAccuracy: 0.9"

        factsheet_metadata = {"cost": 0.05}
        accuracy_metadata = {"qa_pairs": 50}

        result = self.writer.write_company_files(
            company_url,
            factsheet_content,
            accuracy_content,
            factsheet_metadata,
            accuracy_metadata,
        )

        assert result["overall_status"] == "success"
        assert result["company_url"] == company_url
        assert result["factsheet"]["status"] == "success"
        assert result["accuracy_report"]["status"] == "success"

        # Check both files exist
        factsheet_path = Path(result["factsheet"]["filepath"])
        accuracy_path = Path(result["accuracy_report"]["filepath"])
        assert factsheet_path.exists()
        assert accuracy_path.exists()

    def test_write_company_files_factsheet_only(self) -> None:
        """Test writing only factsheet (no accuracy report)."""
        company_url = "https://example.com"
        factsheet_content = "# Example Corp\n\n" + " ".join(["word"] * 700)

        result = self.writer.write_company_files(company_url, factsheet_content)

        assert result["overall_status"] == "success"
        assert result["factsheet"]["status"] == "success"
        assert result["accuracy_report"] is None

    def test_write_error_handling(self) -> None:
        """Test error handling in file writing."""
        # Test with invalid directory permissions (mock)
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = self.writer.write_factsheet("https://example.com", "Content")

            assert result["status"] == "error"
            assert "Access denied" in result["error"]

    def test_tracking_and_summary(self) -> None:
        """Test file tracking and summary generation."""
        # Write some files
        company_urls = ["https://example1.com", "https://example2.com"]

        for i, url in enumerate(company_urls):
            factsheet = f"# Company {i+1}\n\n" + " ".join(["word"] * 700)
            accuracy = f"# Company {i+1} - Accuracy\n\nScore: 0.8"

            self.writer.write_company_files(url, factsheet, accuracy)

        # Test tracking
        written_files = self.writer.get_written_files()
        assert len(written_files) == 4  # 2 factsheets + 2 accuracy reports

        failed_writes = self.writer.get_failed_writes()
        assert len(failed_writes) == 0

        # Test summary
        summary = self.writer.get_summary()
        assert summary["total_files_written"] == 4
        assert summary["factsheets_written"] == 2
        assert summary["accuracy_reports_written"] == 2
        assert summary["failed_writes"] == 0
        assert "word_count_stats" in summary

    def test_cleanup_files(self) -> None:
        """Test file cleanup functionality."""
        # Write some files
        company_url = "https://example.com"
        factsheet = "# Example Corp\n\n" + " ".join(["word"] * 700)

        result = self.writer.write_factsheet(company_url, factsheet)
        filepath = Path(result["filepath"])

        # Verify file exists
        assert filepath.exists()

        # Cleanup
        cleanup_result = self.writer.cleanup_files([company_url])

        assert cleanup_result["cleaned_files"] == 1
        assert cleanup_result["failed_cleanups"] == 0
        assert not filepath.exists()

    def test_cleanup_all_files(self) -> None:
        """Test cleanup of all files."""
        # Write multiple files
        for i in range(3):
            url = f"https://example{i}.com"
            content = f"# Company {i}\n\nContent here."
            self.writer.write_factsheet(url, content)

        assert len(self.writer.get_written_files()) == 3

        # Cleanup all
        cleanup_result = self.writer.cleanup_files()

        assert cleanup_result["cleaned_files"] == 3
        assert len(self.writer.get_written_files()) == 0


class TestFactsheetWriterIntegration(unittest.TestCase):
    """Integration tests for FactsheetWriter with real file system."""

    def setUp(self) -> None:
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.writer = FactsheetWriter(output_dir=self.temp_dir)

    def tearDown(self) -> None:
        """Clean up integration test fixtures."""
        # Clean up files
        try:
            self.writer.cleanup_files()
        except Exception:
            pass

        # Remove temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_real_file_operations(self) -> None:
        """Test real file system operations."""
        company_url = "https://stripe.com"

        # Create realistic factsheet content
        factsheet_content = """# Stripe - Fintech Company Factsheet

## Company Overview

Stripe is a leading financial technology company that provides payment processing solutions for businesses of all sizes. Founded in 2010 by brothers Patrick and John Collison, Stripe has grown to become one of the most valuable private companies in the world, with a mission to increase the GDP of the internet.

## Core Products & Services

Stripe offers a comprehensive suite of financial infrastructure tools:

### Payment Processing
- Accept payments online and in-person
- Support for 135+ currencies
- Multiple payment methods including cards, digital wallets, and bank transfers

### Business Tools
- Subscription billing and revenue recognition
- Marketplace and platform payments
- Financial reporting and analytics

## Market Position

Stripe serves millions of businesses worldwide, from startups to Fortune 500 companies. The company processes hundreds of billions of dollars in payments annually and continues to expand globally with local payment method support and regulatory compliance.

## Technology Innovation

Stripe is known for its developer-friendly APIs and robust technical infrastructure. The company invests heavily in machine learning for fraud detection and prevention, making payments safer for both businesses and consumers.

## Financial Performance

As a private company, Stripe's exact financial metrics are not publicly disclosed. However, the company was last valued at $95 billion in 2021, making it one of the most valuable fintech companies globally.

## Recent Developments

- Expansion into new markets including Latin America and Southeast Asia
- Launch of Stripe Climate for carbon removal
- Introduction of embedded finance solutions
- Strategic partnerships with major financial institutions

## Future Outlook

Stripe continues to focus on enabling more businesses to participate in the digital economy through innovative financial infrastructure and global expansion."""

        # Create accuracy report
        accuracy_content = """# Stripe - Accuracy Report

## Validation Summary

**Overall Accuracy Score: 0.92**

## Methodology

This accuracy assessment was conducted using a two-way Q&A validation procedure comparing generated factsheet content against source material.

## Question-Answer Analysis

### Questions Generated: 52
### Successful Matches: 48
### Accuracy Rate: 92.3%

## Detailed Results

### High Confidence Sections (95-100% accuracy):
- Company Overview
- Core Products & Services
- Technology Innovation

### Medium Confidence Sections (85-94% accuracy):
- Market Position
- Financial Performance

### Lower Confidence Sections (75-84% accuracy):
- Recent Developments
- Future Outlook

## Recommendations

The factsheet demonstrates high accuracy in core business information. Some forward-looking statements and recent developments may benefit from additional verification against the latest company announcements.

## Validation Metadata

- Source URLs processed: 15
- Content chunks analyzed: 6
- Generation model: GPT-4
- Validation timestamp: 2024-01-15T10:30:00Z"""

        # Write both files
        result = self.writer.write_company_files(
            company_url,
            factsheet_content,
            accuracy_content,
            factsheet_metadata={"model": "gpt-4", "cost": 0.034},
            accuracy_metadata={"qa_pairs": 52, "accuracy_score": 0.92},
        )

        # Verify results
        assert result["overall_status"] == "success"

        # Check factsheet
        factsheet_result = result["factsheet"]
        assert factsheet_result["status"] == "success"
        assert factsheet_result["slug"] == "stripe"
        assert factsheet_result["filename"] == "stripe.md"
        # The test factsheet content is shorter than 600 words, so it will be invalid
        # This is actually correct behavior - we're testing file operations, not word count compliance
        assert factsheet_result["word_count_valid"] is False

        # Check accuracy report
        accuracy_result = result["accuracy_report"]
        assert accuracy_result["status"] == "success"
        assert accuracy_result["filename"].endswith("_accuracy.md")

        # Verify files exist and have correct content
        factsheet_path = Path(factsheet_result["filepath"])
        accuracy_path = Path(accuracy_result["filepath"])

        assert factsheet_path.exists()
        assert accuracy_path.exists()

        # Check file sizes are reasonable
        assert factsheet_path.stat().st_size > 1000  # Should be substantial
        assert accuracy_path.stat().st_size > 500

        # Verify content preservation
        with open(factsheet_path, "r", encoding="utf-8") as f:
            written_factsheet = f.read()
        assert "Stripe is a leading financial technology company" in written_factsheet

        with open(accuracy_path, "r", encoding="utf-8") as f:
            written_accuracy = f.read()
        assert "Overall Accuracy Score: 0.92" in written_accuracy

    def test_directory_creation(self) -> None:
        """Test automatic directory creation."""
        # Create writer with non-existent directory
        nested_dir = Path(self.temp_dir) / "nested" / "subdirectory"
        writer = FactsheetWriter(output_dir=str(nested_dir))

        # Directory should be created automatically
        assert nested_dir.exists()
        assert nested_dir.is_dir()

        # Should be able to write files
        result = writer.write_factsheet(
            "https://test.com", "# Test Company\n\n" + " ".join(["word"] * 700)
        )

        assert result["status"] == "success"
        assert Path(result["filepath"]).exists()


if __name__ == "__main__":
    unittest.main()
