"""
Web scraping functionality for the Sales Factsheet Generation System.
"""

import asyncio
import logging
import os
import ssl
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from firecrawl import FirecrawlApp


class WebScraper:
    """Web scraper with Firecrawl API and fallback methods."""

    def __init__(
        self, firecrawl_api_key: Optional[str] = None, max_concurrent: int = 5
    ):
        """Initialize the web scraper.

        Args:
            firecrawl_api_key: Firecrawl API key (optional)
            max_concurrent: Maximum concurrent requests
        """
        # Get API key from environment if not provided
        self.firecrawl_api_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.logger = logging.getLogger(__name__)

    async def scrape_company(self, url: str) -> Dict[str, Any]:
        """Scrape a company website for content.

        Args:
            url: Company website URL

        Returns:
            Dict containing scraped content and metadata
        """
        async with self.semaphore:
            try:
                # Try Firecrawl API first if available
                if self.firecrawl_api_key:
                    content = await self._scrape_with_firecrawl(url)
                    if content:
                        return content

                # Fallback to manual scraping
                return await self._scrape_with_httpx(url)

            except Exception as e:
                self.logger.error(f"Failed to scrape {url}: {e}")
                return {"url": url, "content": "", "error": str(e), "method": "failed"}

    async def _scrape_with_firecrawl(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape using Firecrawl API with crawling for comprehensive data.

        Args:
            url: URL to crawl

        Returns:
            Scraped content or None if failed
        """
        try:
            self.logger.info(f"Attempting Firecrawl crawl for {url} with depth=20")

            # Initialize Firecrawl client
            firecrawl_client = FirecrawlApp(api_key=self.firecrawl_api_key)

            # Use crawl_url to get all pages (more comprehensive)
            # According to Firecrawl API, use params dictionary
            crawl_params = {
                "limit": 50,  # Increase limit to accommodate deeper crawling
                "maxDepth": 20,  # Crawl to depth of 20 levels
                "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True},
            }

            crawl_result = firecrawl_client.crawl_url(url, params=crawl_params)

            # Check if crawl_result is a list (direct data) or dict (wrapped response)
            if isinstance(crawl_result, list):
                data = crawl_result
            elif crawl_result and isinstance(crawl_result, dict):
                if crawl_result.get("success"):
                    data = crawl_result.get("data", [])
                else:
                    self.logger.warning(
                        f"Firecrawl crawl failed for {url}: {crawl_result}"
                    )
                    return None
            else:
                self.logger.warning(
                    f"Firecrawl crawl returned unexpected format for {url}"
                )
                return None

            if not data:
                self.logger.warning(f"Firecrawl crawl returned no data for {url}")
                return None

            self.logger.info(
                f"Firecrawl crawl successful for {url}, got {len(data)} pages"
            )

            # Combine content from all pages
            combined_content = ""
            homepage_content = ""
            about_content = ""
            about_url = None

            for page in data:
                page_url = page.get("metadata", {}).get("sourceURL", "")
                page_content = page.get("markdown", "")

                if page_content:
                    combined_content += f"\n\n--- Page: {page_url} ---\n{page_content}"

                    # Check if this is the homepage (first page or matches base URL)
                    if (
                        not homepage_content
                        or page_url == url
                        or page_url == url.rstrip("/")
                    ):
                        homepage_content = page_content

                    # Check if this looks like an About page
                    if any(
                        keyword in page_url.lower()
                        for keyword in ["about", "who", "company", "mission"]
                    ):
                        about_content = page_content
                        about_url = page_url

            return {
                "url": url,
                "homepage_content": homepage_content or combined_content,
                "homepage_text": homepage_content or combined_content,
                "about_url": about_url,
                "about_text": about_content,
                "combined_content": combined_content.strip(),
                "pages_crawled": len(data),
                "method": "firecrawl-crawl",
                "status": "success",
                "metadata": {},
            }

        except Exception as e:
            self.logger.warning(f"Firecrawl crawl failed for {url}: {e}")
            # Fallback to single page scrape if crawl fails
            try:
                self.logger.info(f"Trying Firecrawl single page scrape for {url}")
                scrape_params = {"formats": ["markdown"], "onlyMainContent": True}
                response = firecrawl_client.scrape_url(url, params=scrape_params)

                if response and response.get("success"):
                    data = response.get("data", {})
                    content = data.get("markdown", "")

                    if content:
                        return {
                            "url": url,
                            "homepage_content": content,
                            "homepage_text": content,
                            "about_url": None,
                            "about_text": "",
                            "method": "firecrawl-scrape",
                            "status": "success",
                            "metadata": data.get("metadata", {}),
                        }

            except Exception as fallback_error:
                self.logger.warning(
                    f"Firecrawl fallback scrape also failed for {url}: {fallback_error}"
                )

            return None

    async def _scrape_with_httpx(self, url: str) -> Dict[str, Any]:
        """Scrape using httpx and BeautifulSoup.

        Args:
            url: URL to scrape

        Returns:
            Scraped content and metadata
        """
        try:
            # Normalize URL
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            # Create SSL context that's more permissive
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            # Set minimum TLS version to avoid DH key issues
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                verify=ssl_context,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; ThinkbridgeBot/1.0; "
                        "+https://thinkbridge.com/bot)"
                    )
                },
            ) as client:
                # Get homepage
                homepage_response = await client.get(url)
                homepage_response.raise_for_status()

                homepage_content = homepage_response.text
                homepage_soup = BeautifulSoup(homepage_content, "html.parser")

                # Extract text content
                homepage_text = self._extract_text(homepage_soup)

                # Try to find and scrape About page
                about_url = self._find_about_page(url, homepage_soup)
                about_text = ""

                if about_url:
                    try:
                        about_response = await client.get(about_url)
                        about_response.raise_for_status()
                        about_soup = BeautifulSoup(about_response.text, "html.parser")
                        about_text = self._extract_text(about_soup)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to scrape About page {about_url}: {e}"
                        )

                return {
                    "url": url,
                    "homepage_content": homepage_content,
                    "homepage_text": homepage_text,
                    "about_url": about_url,
                    "about_text": about_text,
                    "method": "httpx",
                    "status": "success",
                }

        except Exception as e:
            self.logger.error(f"HTTPX scraping failed for {url}: {e}")
            return {
                "url": url,
                "content": "",
                "error": str(e),
                "method": "httpx",
                "status": "failed",
            }

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text content from BeautifulSoup object.

        Args:
            soup: BeautifulSoup object

        Returns:
            Clean text content
        """
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Get text and clean it
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        return text

    def _find_about_page(self, base_url: str, soup: BeautifulSoup) -> Optional[str]:
        """Find About page URL from homepage.

        Args:
            base_url: Base URL of the website
            soup: BeautifulSoup object of homepage

        Returns:
            About page URL or None if not found
        """
        about_keywords = [
            "about",
            "about-us",
            "aboutus",
            "company",
            "our-story",
            "who-we-are",
            "whoweare",
            "about-company",
        ]

        # Look for links containing about keywords
        for link in soup.find_all("a", href=True):
            href = link.get("href", "").lower()
            text = link.get_text().lower()

            # Check if link text or href contains about keywords
            for keyword in about_keywords:
                if keyword in href or keyword in text:
                    about_url = link["href"]

                    # Make relative URLs absolute
                    if about_url.startswith("/"):
                        about_url = urljoin(base_url, about_url)
                    elif not about_url.startswith(("http://", "https://")):
                        about_url = urljoin(base_url, about_url)

                    return about_url

        return None

    async def scrape_multiple_companies(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape multiple company websites concurrently.

        Args:
            urls: List of URLs to scrape

        Returns:
            List of scraped content dictionaries
        """
        tasks = [self.scrape_company(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_results: List[Dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "url": urls[i],
                        "content": "",
                        "error": str(result),
                        "method": "failed",
                        "status": "failed",
                    }
                )
            else:
                processed_results.append(result)  # type: ignore

        return processed_results


# Convenience function for synchronous usage
def scrape_company_sync(
    url: str, firecrawl_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Synchronous wrapper for scraping a single company.

    Args:
        url: Company website URL
        firecrawl_api_key: Firecrawl API key (optional)

    Returns:
        Scraped content dictionary
    """
    scraper = WebScraper(firecrawl_api_key)
    return asyncio.run(scraper.scrape_company(url))
