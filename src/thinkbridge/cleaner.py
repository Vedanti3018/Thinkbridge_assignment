"""
HTML cleaning and text chunking functionality for the Sales Factsheet Generation System.
"""

import logging
import re
from typing import Any, Dict, List

import trafilatura


class ContentCleaner:
    """Clean and chunk HTML content for processing."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """Initialize the content cleaner.

        Args:
            chunk_size: Size of text chunks in tokens (approximate)
            chunk_overlap: Overlap between chunks in tokens
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.logger = logging.getLogger(__name__)

    def clean_html_content(self, html_content: str, url: str) -> Dict[str, Any]:
        """Clean HTML content and extract meaningful text.

        Args:
            html_content: Raw HTML content
            url: Source URL for context

        Returns:
            Dict containing cleaned content and metadata
        """
        try:
            # Use trafilatura to extract main content
            extracted_text = trafilatura.extract(
                html_content,
                include_formatting=True,
                include_links=True,
                include_images=True,
                include_tables=True,
            )

            if not extracted_text:
                # Fallback: use trafilatura with different settings
                extracted_text = trafilatura.extract(
                    html_content,
                    include_formatting=False,
                    include_links=False,
                    include_images=False,
                    include_tables=False,
                )

            if not extracted_text:
                # Last resort: extract all text
                try:
                    extracted_text = trafilatura.extract_text(html_content)
                except AttributeError:
                    # Fallback to basic text extraction
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(html_content, "html.parser")
                    extracted_text = soup.get_text()

            # Clean the extracted text
            cleaned_text = self._clean_text(extracted_text)

            # Chunk the text
            chunks = self._chunk_text(cleaned_text)

            return {
                "url": url,
                "original_length": len(html_content),
                "cleaned_length": len(cleaned_text),
                "cleaned_text": cleaned_text,
                "chunks": chunks,
                "num_chunks": len(chunks),
                "status": "success",
            }

        except Exception as e:
            self.logger.error(f"Failed to clean content from {url}: {e}")
            return {
                "url": url,
                "original_length": len(html_content),
                "cleaned_length": 0,
                "cleaned_text": "",
                "chunks": [],
                "num_chunks": 0,
                "error": str(e),
                "status": "failed",
            }

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content.

        Args:
            text: Raw text content

        Returns:
            Cleaned text content
        """
        if not text:
            return ""

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove common HTML artifacts
        text = re.sub(r"&[a-zA-Z]+;", " ", text)  # HTML entities
        text = re.sub(r"<[^>]+>", " ", text)  # Any remaining HTML tags

        # Remove excessive punctuation
        text = re.sub(r"[.!?]{2,}", ".", text)
        text = re.sub(r"[,;]{2,}", ",", text)

        # Remove excessive spaces
        text = re.sub(r" +", " ", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # Simple tokenization (split by words)
        words = text.split()

        if len(words) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(words):
            # Calculate end position
            end = start + self.chunk_size

            # Extract chunk
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            chunks.append(chunk_text)

            # Move start position with overlap
            start = end - self.chunk_overlap

            # Ensure we don't go backwards
            if start >= len(words):
                break

        return chunks

    def process_scraped_content(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process scraped content through the cleaner.

        Args:
            scraped_data: Data from the scraper

        Returns:
            Processed content with cleaned text and chunks
        """
        url = scraped_data.get("url", "")

        if scraped_data.get("status") != "success":
            return {
                "url": url,
                "cleaned_text": "",
                "chunks": [],
                "error": scraped_data.get("error", "Scraping failed"),
                "status": "failed",
            }

        # Combine homepage and about page content
        homepage_content = scraped_data.get("homepage_content", "")
        about_text = scraped_data.get("about_text", "")

        # Clean homepage content
        homepage_cleaned = self.clean_html_content(homepage_content, url)

        # Process about page if available
        about_cleaned = None
        if about_text:
            # Create a simple HTML wrapper for about text
            about_html = f"<html><body><div>{about_text}</div></body></html>"
            about_cleaned = self.clean_html_content(about_html, url)

        # Combine results
        combined_text = homepage_cleaned.get("cleaned_text", "")
        if about_cleaned and about_cleaned.get("cleaned_text"):
            combined_text += "\n\n" + about_cleaned.get("cleaned_text", "")

        # Re-chunk the combined text
        combined_chunks = self._chunk_text(combined_text)

        return {
            "url": url,
            "homepage_cleaned": homepage_cleaned,
            "about_cleaned": about_cleaned,
            "combined_text": combined_text,
            "combined_chunks": combined_chunks,
            "num_chunks": len(combined_chunks),
            "total_length": len(combined_text),
            "status": "success",
        }

    def process_multiple_companies(
        self, scraped_data_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process multiple companies' scraped content.

        Args:
            scraped_data_list: List of scraped data dictionaries

        Returns:
            List of processed content dictionaries
        """
        processed_results = []

        for scraped_data in scraped_data_list:
            try:
                processed = self.process_scraped_content(scraped_data)
                processed_results.append(processed)
            except Exception as e:
                self.logger.error(
                    f"Failed to process content for "
                    f"{scraped_data.get('url', 'unknown')}: {e}"
                )
                processed_results.append(
                    {
                        "url": scraped_data.get("url", ""),
                        "cleaned_text": "",
                        "chunks": [],
                        "error": str(e),
                        "status": "failed",
                    }
                )

        return processed_results


# Convenience function for synchronous usage
def clean_content_sync(
    html_content: str,
    url: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Dict[str, Any]:
    """Synchronous wrapper for cleaning content.

    Args:
        html_content: Raw HTML content
        url: Source URL
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks

    Returns:
        Cleaned content dictionary
    """
    cleaner = ContentCleaner(chunk_size, chunk_overlap)
    return cleaner.clean_html_content(html_content, url)
