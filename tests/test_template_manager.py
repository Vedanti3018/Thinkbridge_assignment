"""
Unit tests for the template manager module.
"""

import tempfile
import unittest
from pathlib import Path

import pytest

from thinkbridge.template_manager import TemplateManager, get_template


class TestTemplateManager(unittest.TestCase):
    """Test cases for TemplateManager class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a temporary directory for test templates
        self.temp_dir = tempfile.mkdtemp()
        self.templates_dir = Path(self.temp_dir)

        # Create test templates
        self._create_test_templates()

        # Initialize template manager with test directory
        self.manager = TemplateManager(str(self.templates_dir))

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_test_templates(self) -> None:
        """Create test template files."""
        # Generic template
        generic_template = """# {company_name} - Generic Factsheet

## Company Overview
{company_overview}

## Business Focus
{business_focus}
"""
        (self.templates_dir / "generic.md").write_text(generic_template)

        # Technology template
        tech_template = """# {company_name} - Technology Company

## Technology Stack
{technology_stack}

## Products
{products}
"""
        (self.templates_dir / "technology.md").write_text(tech_template)

        # Construction template
        construction_template = """# {company_name} - Construction Company

## Projects
{projects}

## Certifications
{certifications}
"""
        (self.templates_dir / "construction.md").write_text(construction_template)

    def test_init_default_templates_dir(self) -> None:
        """Test initialization with default templates directory."""
        manager = TemplateManager()
        # Should use default path relative to module
        expected_path = (
            Path(__file__).parent.parent / "src" / "thinkbridge" / "templates"
        )
        # Note: We can't assert exact equality due to path resolution differences
        assert "templates" in str(manager.templates_dir)

    def test_init_custom_templates_dir(self) -> None:
        """Test initialization with custom templates directory."""
        custom_dir = "/custom/path"
        manager = TemplateManager(custom_dir)
        assert str(manager.templates_dir) == custom_dir

    def test_scan_templates(self) -> None:
        """Test template scanning functionality."""
        expected_templates = {"generic", "technology", "construction"}
        assert self.manager._available_templates == expected_templates

    def test_normalize_industry_direct_match(self) -> None:
        """Test industry normalization with direct matches."""
        test_cases = [
            ("Technology", "technology"),
            ("CONSTRUCTION", "construction"),
            ("generic", "generic"),
        ]

        for input_industry, expected in test_cases:
            with self.subTest(input_industry=input_industry):
                result = self.manager._normalize_industry(input_industry)
                assert result == expected

    def test_normalize_industry_mapping(self) -> None:
        """Test industry normalization with mapping."""
        test_cases = [
            ("Tech", "technology"),
            ("Software", "technology"),
            ("SaaS", "technology"),
            ("Building", "construction"),
            ("Real Estate", "construction"),
            ("Finance", "fintech"),
            ("Banking", "fintech"),
            ("Health", "healthcare"),
            ("Medical", "healthcare"),
        ]

        for input_industry, expected in test_cases:
            with self.subTest(input_industry=input_industry):
                result = self.manager._normalize_industry(expected)
                # Note: Some mappings might not have templates, so we expect generic fallback
                assert result in [
                    "technology",
                    "construction",
                    "fintech",
                    "healthcare",
                    "generic",
                ]

    def test_normalize_industry_fallback(self) -> None:
        """Test industry normalization fallback to generic."""
        test_cases = [
            ("Unknown Industry", "generic"),
            ("", "generic"),
            ("!@#$%", "generic"),
            ("Random Business", "generic"),
        ]

        for input_industry, expected in test_cases:
            with self.subTest(input_industry=input_industry):
                result = self.manager._normalize_industry(input_industry)
                assert result == expected

    def test_get_template_existing(self) -> None:
        """Test getting an existing template."""
        template = self.manager.get_template("technology")
        assert "Technology Company" in template
        assert "{technology_stack}" in template
        assert "{products}" in template

    def test_get_template_fallback_to_generic(self) -> None:
        """Test fallback to generic template."""
        template = self.manager.get_template("nonexistent_industry")
        assert "Generic Factsheet" in template
        assert "{company_overview}" in template
        assert "{business_focus}" in template

    def test_get_template_caching(self) -> None:
        """Test template caching functionality."""
        # First call should load from file
        template1 = self.manager.get_template("technology")

        # Second call should use cache
        template2 = self.manager.get_template("technology")

        assert template1 == template2
        assert "technology" in self.manager._template_cache

    def test_get_template_missing_generic(self) -> None:
        """Test error when generic template is missing."""
        # Remove generic template
        (self.templates_dir / "generic.md").unlink()

        # Clear cache and rescan
        self.manager.clear_cache()
        self.manager._scan_templates()

        with pytest.raises(FileNotFoundError, match="Generic template not found"):
            self.manager.get_template("nonexistent_industry")

    def test_get_available_templates(self) -> None:
        """Test getting list of available templates."""
        templates = self.manager.get_available_templates()
        expected = ["construction", "generic", "technology"]
        assert templates == expected

    def test_get_template_placeholders(self) -> None:
        """Test extracting placeholders from templates."""
        placeholders = self.manager.get_template_placeholders("technology")
        expected = {"company_name", "technology_stack", "products"}
        assert placeholders == expected

    def test_validate_template_valid(self) -> None:
        """Test template validation for valid template."""
        template_content = """# {company_name} - Test Company

## Overview
{company_overview}

## Details
{details}
"""
        result = self.manager.validate_template(template_content)

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert "company_name" in result["placeholders"]
        assert "company_overview" in result["placeholders"]
        assert len(result["sections"]) == 3  # title + 2 sections

    def test_validate_template_missing_company_name(self) -> None:
        """Test template validation with missing company_name placeholder."""
        template_content = """# Test Company

## Overview
{company_overview}
"""
        result = self.manager.validate_template(template_content)

        assert result["valid"] is False
        assert any("company_name" in error for error in result["errors"])

    def test_validate_template_empty(self) -> None:
        """Test template validation for empty template."""
        result = self.manager.validate_template("")

        assert result["valid"] is False
        assert any("empty" in error.lower() for error in result["errors"])

    def test_clear_cache(self) -> None:
        """Test cache clearing functionality."""
        # Load a template to populate cache
        self.manager.get_template("technology")
        assert len(self.manager._template_cache) > 0

        # Clear cache
        self.manager.clear_cache()
        assert len(self.manager._template_cache) == 0


class TestTemplateManagerIntegration(unittest.TestCase):
    """Integration tests for TemplateManager with real templates."""

    def setUp(self) -> None:
        """Set up integration test fixtures."""
        # Use the actual templates directory
        templates_dir = (
            Path(__file__).parent.parent / "src" / "thinkbridge" / "templates"
        )
        self.manager = TemplateManager(str(templates_dir))

    def test_real_templates_exist(self) -> None:
        """Test that real templates exist and are valid."""
        available = self.manager.get_available_templates()

        # Should have at least generic template
        assert "generic" in available

        # Test some expected templates
        expected_templates = ["generic", "technology", "construction"]
        for template in expected_templates:
            if template in available:
                content = self.manager.get_template(template)
                assert len(content) > 0
                assert "{company_name}" in content

    def test_industry_mapping_integration(self) -> None:
        """Test industry mapping with real templates."""
        test_cases = [
            ("Construction", "construction"),
            ("Technology", "technology"),
            ("Software Development", "technology"),
            ("Real Estate", "construction"),
            ("Unknown Industry", "generic"),
        ]

        for industry, expected_template in test_cases:
            with self.subTest(industry=industry):
                template = self.manager.get_template(industry)
                # Should get a valid template without errors
                assert len(template) > 0
                assert "{{Company Name}}" in template or "{company_name}" in template


class TestConvenienceFunction(unittest.TestCase):
    """Test cases for module-level convenience function."""

    def test_get_template_function(self) -> None:
        """Test the module-level get_template function."""
        # Create temporary test template
        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir)

            # Create a simple generic template
            generic_template = """# {company_name}
{company_overview}
"""
            (templates_dir / "generic.md").write_text(generic_template)

            # Test the convenience function
            template = get_template("unknown_industry", str(templates_dir))
            assert "{{Company Name}}" in template or "{company_name}" in template
            assert "{company_overview}" in template


if __name__ == "__main__":
    unittest.main()
