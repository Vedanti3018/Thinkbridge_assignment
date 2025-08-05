"""
Unit tests for the scraper module.
"""

from unittest.mock import Mock, patch

import httpx
import pytest
from bs4 import BeautifulSoup

from thinkbridge.scraper import WebScraper, scrape_company_sync


class TestWebScraper:
    """Test cases for the WebScraper class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.scraper = WebScraper(max_concurrent=2)

    def test_init(self) -> None:
        """Test WebScraper initialization."""
        scraper = WebScraper(firecrawl_api_key="test_key", max_concurrent=5)
        assert scraper.firecrawl_api_key == "test_key"
        assert scraper.max_concurrent == 5

    @pytest.mark.asyncio
    async def test_scrape_company_success(self) -> None:
        """Test successful company scraping."""
        # Mock httpx.AsyncClient
        mock_response = Mock()
        mock_response.text = """
        <html>
            <body>
                <h1>Test Company</h1>
                <p>This is a test company website.</p>
                <a href="/about">About Us</a>
            </body>
        </html>
        """
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await self.scraper.scrape_company("https://test.com")

            assert result["url"] == "https://test.com"
            assert result["status"] == "success"
            assert result["method"] == "httpx"
            assert "Test Company" in result["homepage_text"]
            assert result["about_url"] == "https://test.com/about"

    @pytest.mark.asyncio
    async def test_scrape_company_failure(self) -> None:
        """Test company scraping failure."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.HTTPError("Connection failed")
            )

            result = await self.scraper.scrape_company("https://invalid.com")

            assert result["url"] == "https://invalid.com"
            assert result["status"] == "failed"
            assert "error" in result

    def test_extract_text(self) -> None:
        """Test text extraction from BeautifulSoup."""
        html = """
        <html>
            <body>
                <h1>Title</h1>
                <p>Paragraph with <strong>bold</strong> text.</p>
                <script>alert('test');</script>
                <style>body { color: red; }</style>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        extracted_text = self.scraper._extract_text(soup)

        assert "Title" in extracted_text
        assert "Paragraph with bold text" in extracted_text
        assert "alert('test')" not in extracted_text  # Script removed
        assert "color: red" not in extracted_text  # Style removed

    def test_find_about_page(self) -> None:
        """Test finding About page URL."""
        html = """
        <html>
            <body>
                <nav>
                    <a href="/about">About Us</a>
                    <a href="/contact">Contact</a>
                </nav>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        about_url = self.scraper._find_about_page("https://test.com", soup)

        assert about_url == "https://test.com/about"

    def test_find_about_page_not_found(self) -> None:
        """Test when About page is not found."""
        html = """
        <html>
            <body>
                <nav>
                    <a href="/contact">Contact</a>
                    <a href="/services">Services</a>
                </nav>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        about_url = self.scraper._find_about_page("https://test.com", soup)

        assert about_url is None

    def test_find_about_page_relative_url(self) -> None:
        """Test finding About page with relative URL."""
        html = """
        <html>
            <body>
                <a href="about-us">About</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        about_url = self.scraper._find_about_page("https://test.com", soup)

        assert about_url == "https://test.com/about-us"

    @pytest.mark.asyncio
    async def test_scrape_multiple_companies(self) -> None:
        """Test scraping multiple companies concurrently."""
        urls = ["https://test1.com", "https://test2.com"]

        # Mock responses
        mock_response1 = Mock()
        mock_response1.text = "<html><body><h1>Company 1</h1></body></html>"
        mock_response1.raise_for_status.return_value = None

        mock_response2 = Mock()
        mock_response2.text = "<html><body><h1>Company 2</h1></body></html>"
        mock_response2.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = [
                mock_response1,
                mock_response2,
            ]

            results = await self.scraper.scrape_multiple_companies(urls)

            assert len(results) == 2
            assert results[0]["url"] == "https://test1.com"
            assert results[1]["url"] == "https://test2.com"
            assert all(result["status"] == "success" for result in results)

    @pytest.mark.asyncio
    async def test_scrape_with_firecrawl(self) -> None:
        """Test Firecrawl API scraping (placeholder)."""
        scraper = WebScraper(firecrawl_api_key="test_key")

        result = await scraper._scrape_with_firecrawl("https://test.com")

        # Currently returns None to trigger fallback
        assert result is None


class TestScraperSync:
    """Test cases for synchronous scraper functions."""

    def test_scrape_company_sync(self) -> None:
        """Test synchronous scraping wrapper."""
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = {
                "url": "https://test.com",
                "status": "success",
                "method": "httpx",
            }

            result = scrape_company_sync("https://test.com")

            assert result["url"] == "https://test.com"
            assert result["status"] == "success"
            mock_run.assert_called_once()


class TestScraperIntegration:
    """Integration tests for the scraper."""

    @pytest.mark.asyncio
    async def test_full_scraping_workflow(self) -> None:
        """Test the complete scraping workflow."""
        scraper = WebScraper(max_concurrent=1)

        # Mock a simple HTML response
        mock_response = Mock()
        mock_response.text = """
        <html>
            <body>
                <h1>Test Company</h1>
                <p>We are a construction company.</p>
                <a href="/about">About Us</a>
            </body>
        </html>
        """
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await scraper.scrape_company("https://construction-company.com")

            # Verify the result structure
            assert result["url"] == "https://construction-company.com"
            assert result["status"] == "success"
            assert result["method"] == "httpx"
            assert "Test Company" in result["homepage_text"]
            assert "construction company" in result["homepage_text"].lower()
            assert result["about_url"] == "https://construction-company.com/about"

    @pytest.mark.asyncio
    async def test_scraping_with_about_page(self) -> None:
        """Test scraping with About page discovery."""
        scraper = WebScraper(max_concurrent=1)

        # Mock homepage response
        homepage_response = Mock()
        homepage_response.text = """
        <html>
            <body>
                <h1>Company</h1>
                <a href="/about-us">About Us</a>
            </body>
        </html>
        """
        homepage_response.raise_for_status.return_value = None

        # Mock about page response
        about_response = Mock()
        about_response.text = """
        <html>
            <body>
                <h1>About Us</h1>
                <p>We are a leading company in our industry.</p>
            </body>
        </html>
        """
        about_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = [
                homepage_response,
                about_response,
            ]

            result = await scraper.scrape_company("https://test.com")

            assert result["about_url"] == "https://test.com/about-us"
            assert "About Us" in result["about_text"]
            assert "leading company" in result["about_text"]
