"""
Writer module for Sales Factsheet Generation System.

This module handles file output, including slugification of company names,
directory management, and saving factsheets and accuracy reports.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class FactsheetWriter:
    """Handles writing factsheets and accuracy reports to files."""

    def __init__(self, output_dir: str = "factsheets"):
        """Initialize the factsheet writer.

        Args:
            output_dir: Directory to save factsheets (default: "factsheets")
        """
        self.output_dir = Path(output_dir)
        self.logger = self._setup_logging()

        # Word count requirements (from spec)
        self.min_word_count = 600
        self.max_word_count = 1000

        # Tracking
        self.written_files: List[Dict[str, Any]] = []
        self.failed_writes: List[Dict[str, Any]] = []

        # Ensure output directory exists
        self._ensure_output_dir()

        self.logger.info(
            f"FactsheetWriter initialized with output directory: {self.output_dir}"
        )

    def _setup_logging(self) -> logging.Logger:
        """Set up structured logging for the writer."""
        logger = logging.getLogger("factsheet_writer")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _ensure_output_dir(self) -> None:
        """Ensure the output directory exists."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Output directory ensured: {self.output_dir}")
        except Exception as e:
            self.logger.error(
                f"Failed to create output directory {self.output_dir}: {e}"
            )
            raise

    def slugify_company_name(
        self, company_url: str, company_name: Optional[str] = None
    ) -> str:
        """Create a simple, clean filename slug from company name or URL.

        Args:
            company_url: Company website URL
            company_name: Optional company name (extracted from factsheet if available)

        Returns:
            Simple filename slug (e.g., 'drees-homes', 'tesla', 'microsoft')
        """
        # Use provided company name, or extract from URL
        if company_name:
            base_name = company_name
        else:
            base_name = self._extract_company_name_from_url(company_url)

        # Clean the name - remove common suffixes but keep essential business words like "homes"
        base_name = re.sub(
            r"\s+(inc|corp|corporation|company|llc|ltd|construction|industry|factsheet)\.?\s*$",
            "",
            base_name.lower(),
        )

        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r"[^\w\s-]", "", base_name.lower())
        slug = re.sub(r"[-\s]+", "-", slug)

        # Remove leading/trailing hyphens
        slug = slug.strip("-")

        # Ensure minimum length
        if len(slug) < 3:
            # Fallback to URL-based slug
            domain = (
                company_url.replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
            )
            domain = domain.split("/")[0].split(".")[0]
            slug = re.sub(r"[^\w]", "-", domain.lower()).strip("-")

        # Ensure not empty
        if not slug:
            slug = "company"

        return slug

    def _extract_company_name_from_url(self, url: str) -> str:
        """Extract probable company name from URL.

        Args:
            url: Company URL

        Returns:
            Probable company name
        """
        try:
            # Remove protocol and www
            domain = (
                url.replace("https://", "").replace("http://", "").replace("www.", "")
            )

            # Extract domain name before first dot
            domain_parts = domain.split(".")
            if domain_parts:
                name = domain_parts[0]
                return name.capitalize()

            return "Company"

        except Exception:
            return "Company"

    def _extract_company_name_from_factsheet(
        self, factsheet_content: str
    ) -> Optional[str]:
        """Try to extract company name from factsheet content.

        Args:
            factsheet_content: The generated factsheet content

        Returns:
            Extracted company name or None
        """
        try:
            # Look for the first heading which should be the company name
            lines = factsheet_content.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("# ") and len(line) > 2:
                    # Extract company name from heading
                    heading = line[2:].strip()
                    # Remove common suffixes and separators like "• Construction Industry Factsheet" or "- Company Factsheet"
                    name = re.sub(
                        r"\s*[•\-–—]\s*.*(?:industry|company|factsheet|construction).*$",
                        "",
                        heading,
                        flags=re.IGNORECASE,
                    )
                    # Also remove standalone suffixes but keep business-specific words like "homes"
                    name = re.sub(
                        r"\s+(inc|corp|corporation|company|llc|ltd|factsheet)\.?\s*$",
                        "",
                        name,
                        flags=re.IGNORECASE,
                    )
                    return name.strip()

            return None

        except Exception:
            return None

    def validate_word_count(self, content: str) -> Tuple[bool, int]:
        """Validate if content meets word count requirements.

        Args:
            content: Content to validate

        Returns:
            Tuple of (is_valid, word_count)
        """
        # Count words (split by whitespace)
        words = content.split()
        word_count = len(words)

        is_valid = self.min_word_count <= word_count <= self.max_word_count
        return is_valid, word_count

    def write_factsheet(
        self,
        company_url: str,
        factsheet_content: str,
        metadata: Optional[Dict[str, Any]] = None,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Write a factsheet to a file.

        Args:
            company_url: Company website URL
            factsheet_content: Generated factsheet content
            metadata: Optional metadata about the generation
            overwrite: Whether to overwrite existing files

        Returns:
            Dictionary with write result and file information
        """
        try:
            # Validate word count
            is_valid_count, word_count = self.validate_word_count(factsheet_content)
            if not is_valid_count:
                self.logger.warning(
                    f"Factsheet word count {word_count} not in range "
                    f"{self.min_word_count}-{self.max_word_count} for {company_url}"
                )

            # Extract company name from factsheet content
            extracted_name = self._extract_company_name_from_factsheet(
                factsheet_content
            )

            # Create filename slug
            slug = self.slugify_company_name(company_url, extracted_name)

            # Create filename
            filename = f"{slug}.md"
            filepath = self.output_dir / filename

            # Check if file exists and handle overwrite
            if filepath.exists() and not overwrite:
                self.logger.warning(f"Factsheet file already exists: {filepath}")
                return {
                    "status": "skipped",
                    "reason": "file_exists",
                    "filepath": str(filepath),
                    "company_url": company_url,
                    "slug": slug,
                    "word_count": word_count,
                    "word_count_valid": is_valid_count,
                }

            # Write factsheet to file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(factsheet_content)

            # Create result metadata
            result = {
                "status": "success",
                "filepath": str(filepath),
                "filename": filename,
                "company_url": company_url,
                "slug": slug,
                "word_count": word_count,
                "word_count_valid": is_valid_count,
                "timestamp": datetime.now().isoformat(),
                "file_size_bytes": filepath.stat().st_size,
                "extracted_company_name": extracted_name,
            }

            # Add generation metadata if provided
            if metadata:
                result["generation_metadata"] = metadata

            # Track written file
            self.written_files.append(result)

            self.logger.info(
                f"Written factsheet for {company_url} to {filepath} "
                f"({word_count} words, {result['file_size_bytes']} bytes)"
            )

            return result

        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "company_url": company_url,
                "timestamp": datetime.now().isoformat(),
            }

            self.failed_writes.append(error_result)
            self.logger.error(f"Failed to write factsheet for {company_url}: {e}")

            return error_result

    def write_accuracy_report(
        self,
        company_url: str,
        accuracy_report: str,
        metadata: Optional[Dict[str, Any]] = None,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Write an accuracy report to a file.

        Args:
            company_url: Company website URL
            accuracy_report: Generated accuracy report content
            metadata: Optional metadata about the validation
            overwrite: Whether to overwrite existing files

        Returns:
            Dictionary with write result and file information
        """
        try:
            # Extract company name for consistent slugification
            extracted_name = self._extract_company_name_from_factsheet(accuracy_report)

            # Create filename slug (same as factsheet)
            slug = self.slugify_company_name(company_url, extracted_name)

            # Create accuracy report filename
            filename = f"{slug}_accuracy.md"
            filepath = self.output_dir / filename

            # Check if file exists and handle overwrite
            if filepath.exists() and not overwrite:
                self.logger.warning(f"Accuracy report file already exists: {filepath}")
                return {
                    "status": "skipped",
                    "reason": "file_exists",
                    "filepath": str(filepath),
                    "company_url": company_url,
                    "slug": slug,
                }

            # Write accuracy report to file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(accuracy_report)

            # Create result metadata
            result = {
                "status": "success",
                "filepath": str(filepath),
                "filename": filename,
                "company_url": company_url,
                "slug": slug,
                "timestamp": datetime.now().isoformat(),
                "file_size_bytes": filepath.stat().st_size,
                "extracted_company_name": extracted_name,
            }

            # Add validation metadata if provided
            if metadata:
                result["validation_metadata"] = metadata

            # Track written file
            self.written_files.append(result)

            self.logger.info(
                f"Written accuracy report for {company_url} to {filepath} "
                f"({result['file_size_bytes']} bytes)"
            )

            return result

        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "company_url": company_url,
                "timestamp": datetime.now().isoformat(),
            }

            self.failed_writes.append(error_result)
            self.logger.error(f"Failed to write accuracy report for {company_url}: {e}")

            return error_result

    def write_company_files(
        self,
        company_url: str,
        factsheet_content: str,
        accuracy_report: Optional[str] = None,
        factsheet_metadata: Optional[Dict[str, Any]] = None,
        accuracy_metadata: Optional[Dict[str, Any]] = None,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Write both factsheet and accuracy report for a company.

        Args:
            company_url: Company website URL
            factsheet_content: Generated factsheet content
            accuracy_report: Generated accuracy report (optional)
            factsheet_metadata: Optional factsheet generation metadata
            accuracy_metadata: Optional accuracy validation metadata
            overwrite: Whether to overwrite existing files

        Returns:
            Dictionary with results for both files
        """
        results = {
            "company_url": company_url,
            "factsheet": None,
            "accuracy_report": None,
            "overall_status": "success",
        }

        # Write factsheet
        factsheet_result = self.write_factsheet(
            company_url, factsheet_content, factsheet_metadata, overwrite
        )
        results["factsheet"] = factsheet_result

        if factsheet_result["status"] == "error":
            results["overall_status"] = "partial_failure"

        # Write accuracy report if provided
        if accuracy_report:
            accuracy_result = self.write_accuracy_report(
                company_url, accuracy_report, accuracy_metadata, overwrite
            )
            results["accuracy_report"] = accuracy_result

            if accuracy_result["status"] == "error":
                results["overall_status"] = (
                    "partial_failure"
                    if results["overall_status"] == "success"
                    else "failure"
                )

        return results

    def get_written_files(self) -> List[Dict[str, Any]]:
        """Get list of successfully written files.

        Returns:
            List of file metadata for written files
        """
        return self.written_files.copy()

    def get_failed_writes(self) -> List[Dict[str, Any]]:
        """Get list of failed write attempts.

        Returns:
            List of error metadata for failed writes
        """
        return self.failed_writes.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of writer operations.

        Returns:
            Dictionary with operation summary
        """
        successful_files = len(self.written_files)
        failed_writes = len(self.failed_writes)

        # Count file types
        factsheets = sum(
            1 for f in self.written_files if not f["filename"].endswith("_accuracy.md")
        )
        accuracy_reports = sum(
            1 for f in self.written_files if f["filename"].endswith("_accuracy.md")
        )

        # Calculate word count stats for factsheets
        factsheet_word_counts = [
            f["word_count"]
            for f in self.written_files
            if "word_count" in f and not f["filename"].endswith("_accuracy.md")
        ]

        word_count_stats = {}
        if factsheet_word_counts:
            word_count_stats = {
                "min_words": min(factsheet_word_counts),
                "max_words": max(factsheet_word_counts),
                "avg_words": sum(factsheet_word_counts) / len(factsheet_word_counts),
                "valid_word_count": sum(
                    1
                    for f in self.written_files
                    if "word_count_valid" in f and f["word_count_valid"]
                ),
            }

        return {
            "total_files_written": successful_files,
            "failed_writes": failed_writes,
            "factsheets_written": factsheets,
            "accuracy_reports_written": accuracy_reports,
            "output_directory": str(self.output_dir),
            "word_count_requirements": {
                "min_words": self.min_word_count,
                "max_words": self.max_word_count,
            },
            "word_count_stats": word_count_stats,
        }

    def cleanup_files(self, company_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """Clean up written files (for testing or reset).

        Args:
            company_urls: Optional list of specific company URLs to clean up.
                         If None, cleans up all tracked files.

        Returns:
            Dictionary with cleanup results
        """
        cleaned_files = []
        failed_cleanups = []

        files_to_clean = self.written_files.copy()

        # Filter by company URLs if specified
        if company_urls:
            files_to_clean = [
                f for f in files_to_clean if f.get("company_url") in company_urls
            ]

        for file_info in files_to_clean:
            try:
                filepath = Path(file_info["filepath"])
                if filepath.exists():
                    filepath.unlink()
                    cleaned_files.append(file_info)
                    self.logger.debug(f"Cleaned up file: {filepath}")

            except Exception as e:
                failed_cleanups.append({"file_info": file_info, "error": str(e)})
                self.logger.error(
                    f"Failed to cleanup file {file_info.get('filepath')}: {e}"
                )

        # Remove cleaned files from tracking
        for cleaned in cleaned_files:
            if cleaned in self.written_files:
                self.written_files.remove(cleaned)

        return {
            "cleaned_files": len(cleaned_files),
            "failed_cleanups": len(failed_cleanups),
            "cleanup_errors": failed_cleanups,
        }
