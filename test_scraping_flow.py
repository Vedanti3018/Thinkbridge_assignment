#!/usr/bin/env python3
"""
Test script for the scraping flow using companies.csv
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path before importing our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import our modules after path setup
from thinkbridge.cleaner import ContentCleaner  # noqa: E402
from thinkbridge.scraper import WebScraper  # noqa: E402


def load_env() -> None:
    """Load environment variables from .env file."""
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value


def setup_logging() -> None:
    """Set up logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def test_scraping_flow() -> None:
    """Test the complete scraping flow."""
    print("🚀 Testing Scraping Flow with companies.csv")
    print("=" * 50)

    # Check if companies.csv exists
    csv_path = Path("companies.csv")
    if not csv_path.exists():
        print("❌ companies.csv not found!")
        return

    # Load environment
    load_env()

    # Check for Firecrawl API key
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if api_key:
        print(f"🔑 Firecrawl API key found: {api_key[:10]}...")
    else:
        print("❌ Missing FIRECRAWL_API_KEY environment variable")

    # Read companies from CSV
    import pandas as pd

    df = pd.read_csv(csv_path)
    print(f"📄 Found companies.csv with {len(df)} companies")

    print("\n🔍 Companies to process:")
    for _, row in df.iterrows():
        print(f"  - {row['url']} ({row['industry']})")

    print("\n🌐 Starting web scraping...")

    # Initialize scraper and cleaner
    scraper = WebScraper(max_concurrent=2)
    cleaner = ContentCleaner()

    # Test scraping for each company
    for _, row in df.iterrows():
        url = row["url"]

        print(f"\n📡 Scraping: {url}")
        try:
            # Scrape the website
            scraped_data = await scraper.scrape_company(url)

            if scraped_data.get("status") == "success":
                print("  ✅ Scraping successful")
                method = scraped_data.get("method", "unknown")
                print(f"  📊 Method: {method}")

                # Show crawling details if available
                if "crawl" in scraped_data.get("method", ""):
                    pages_crawled = scraped_data.get("pages_crawled", 0)
                    print(f"  🌐 Pages crawled: {pages_crawled} (depth=20)")

                homepage_len = len(scraped_data.get("homepage_text", ""))
                print(f"  📄 Homepage text length: {homepage_len}")
                about_found = scraped_data.get("about_url") is not None
                print(f"  🔗 About page found: {about_found}")

                # Show combined content info if available
                if scraped_data.get("combined_content"):
                    combined_len = len(scraped_data.get("combined_content", ""))
                    print(f"  📚 Combined content length: {combined_len}")

                # Clean the content
                print("  🧹 Cleaning content...")
                processed_data = cleaner.process_scraped_content(scraped_data)

                if processed_data.get("status") == "success":
                    print("  ✅ Cleaning successful")
                    total_len = processed_data.get("total_length", 0)
                    print(f"  📊 Combined text length: {total_len}")
                    num_chunks = processed_data.get("num_chunks", 0)
                    print(f"  📦 Number of chunks: {num_chunks}")

                    # Show a preview of the cleaned text
                    combined_text = processed_data.get("combined_text", "")
                    if combined_text:
                        preview = (
                            combined_text[:300] + "..."
                            if len(combined_text) > 300
                            else combined_text
                        )
                        print(f"  📝 Preview: {preview}")
                else:
                    error_msg = processed_data.get("error", "Unknown error")
                    print(f"  ❌ Cleaning failed: {error_msg}")
            else:
                error_msg = scraped_data.get("error", "Unknown error")
                print(f"  ❌ Scraping failed: {error_msg}")

        except Exception as e:
            print(f"  ❌ Error processing {url}: {e}")

    print("\n🎉 Scraping flow test completed!")


def main() -> None:
    """Main function."""
    # Setup
    setup_logging()

    # Run the test
    asyncio.run(test_scraping_flow())


if __name__ == "__main__":
    main()
