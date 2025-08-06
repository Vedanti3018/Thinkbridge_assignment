"""
Template Manager for Sales Factsheet Generation System.

This module manages industry-specific Markdown templates for generating
factsheets. It provides template selection logic and template validation.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set


class TemplateManager:
    """Manages industry-specific Markdown templates for factsheet generation."""

    def __init__(self, templates_dir: Optional[str] = None):
        """Initialize the template manager.

        Args:
            templates_dir: Path to templates directory. If None, uses default location.
        """
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            # Default to templates directory relative to this module
            self.templates_dir = Path(__file__).parent / "templates"

        self.logger = self._setup_logging()
        self._template_cache: Dict[str, str] = {}
        self._available_templates: Set[str] = set()

        # Industry mapping for flexible matching
        self._industry_mappings = {
            # Technology variations
            "tech": "technology",
            "software": "technology",
            "saas": "technology",
            "it": "technology",
            "ai": "technology",
            "ml": "technology",
            "data": "technology",
            # Construction variations
            "building": "construction",
            "real estate": "construction",
            "realestate": "construction",
            "property": "construction",
            "development": "construction",
            "contractor": "construction",
            # Finance variations
            "finance": "fintech",
            "financial": "fintech",
            "banking": "fintech",
            "payments": "fintech",
            "crypto": "fintech",
            "blockchain": "fintech",
            # Healthcare variations
            "health": "healthcare",
            "medical": "healthcare",
            "pharma": "healthcare",
            "biotech": "healthcare",
            "clinical": "healthcare",
        }

        # Load available templates
        self._scan_templates()

    def _setup_logging(self) -> logging.Logger:
        """Set up structured logging for the template manager."""
        logger = logging.getLogger("template_manager")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _scan_templates(self) -> None:
        """Scan the templates directory for available templates."""
        if not self.templates_dir.exists():
            self.logger.warning(f"Templates directory not found: {self.templates_dir}")
            return

        for template_file in self.templates_dir.glob("*.md"):
            template_name = template_file.stem
            self._available_templates.add(template_name)

        self.logger.info(
            f"Found {len(self._available_templates)} templates: "
            f"{sorted(self._available_templates)}"
        )

    def _normalize_industry(self, industry: str) -> str:
        """Normalize industry string to match available templates.

        Args:
            industry: Raw industry string

        Returns:
            Normalized industry slug
        """
        if not industry:
            return "generic"

        # Convert to lowercase and remove special characters
        normalized = re.sub(r"[^a-zA-Z0-9\s]", "", industry.lower()).strip()
        normalized = re.sub(r"\s+", " ", normalized)  # Normalize whitespace

        # Check direct mapping
        if normalized in self._industry_mappings:
            return self._industry_mappings[normalized]

        # Check if any mapping key is contained in the industry string
        for key, value in self._industry_mappings.items():
            if key in normalized:
                return value

        # Check if normalized industry directly matches available template
        if normalized in self._available_templates:
            return normalized

        # Default fallback
        return "generic"

    def get_template(self, industry: str) -> str:
        """Get the appropriate template for the given industry.

        Args:
            industry: Industry classification string

        Returns:
            Template content as string

        Raises:
            FileNotFoundError: If template file is not found
            IOError: If template file cannot be read
        """
        # Normalize industry to template name
        template_name = self._normalize_industry(industry)

        # Check cache first
        if template_name in self._template_cache:
            self.logger.debug(
                f"Using cached template for {industry} -> {template_name}"
            )
            return self._template_cache[template_name]

        # Try to load the specific template
        template_path = self.templates_dir / f"{template_name}.md"

        if not template_path.exists():
            # Fallback to generic template
            self.logger.warning(
                f"Template not found for {template_name}, falling back to generic"
            )
            template_name = "generic"
            template_path = self.templates_dir / "generic.md"

        if not template_path.exists():
            raise FileNotFoundError(
                f"Generic template not found at {template_path}. "
                "Please ensure templates directory is properly set up."
            )

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            # Cache the template
            self._template_cache[template_name] = template_content

            self.logger.info(
                f"Loaded template for industry '{industry}' -> {template_name}"
            )

            return template_content

        except IOError as e:
            self.logger.error(f"Failed to read template {template_path}: {e}")
            raise

    def get_available_templates(self) -> List[str]:
        """Get list of available template names.

        Returns:
            List of available template names
        """
        return sorted(self._available_templates)

    def get_template_placeholders(self, industry: str) -> Set[str]:
        """Extract placeholders from a template.

        Args:
            industry: Industry classification string

        Returns:
            Set of placeholder names (without braces)
        """
        template_content = self.get_template(industry)

        # Find all placeholders in {placeholder_name} format
        placeholders = re.findall(r"\{([^}]+)\}", template_content)

        return set(placeholders)

    def validate_template(self, template_content: str) -> Dict[str, any]:
        """Validate a template for required structure and placeholders.

        Args:
            template_content: Template content to validate

        Returns:
            Dictionary with validation results
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "placeholders": set(),
            "sections": [],
        }

        # Extract placeholders
        placeholders = re.findall(r"\{([^}]+)\}", template_content)
        results["placeholders"] = set(placeholders)

        # Extract sections (lines starting with #)
        sections = re.findall(r"^#+\s+(.+)$", template_content, re.MULTILINE)
        results["sections"] = sections

        # Validation rules
        if not template_content.strip():
            results["valid"] = False
            results["errors"].append("Template is empty")

        if "company_name" not in placeholders:
            results["errors"].append("Missing required placeholder: {company_name}")
            results["valid"] = False

        if "company_overview" not in placeholders:
            results["warnings"].append(
                "Missing recommended placeholder: {company_overview}"
            )

        if len(sections) < 3:
            results["warnings"].append("Template has fewer than 3 sections")

        return results

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._template_cache.clear()
        self.logger.debug("Template cache cleared")


# Module-level convenience function
def get_template(industry: str, templates_dir: Optional[str] = None) -> str:
    """Convenience function to get a template for an industry.

    Args:
        industry: Industry classification string
        templates_dir: Optional custom templates directory

    Returns:
        Template content as string
    """
    manager = TemplateManager(templates_dir)
    return manager.get_template(industry)
