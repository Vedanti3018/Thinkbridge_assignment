"""
CSV ingestion and job orchestration for the Sales Factsheet Generation System.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import click
import pandas as pd


class IngestCLI:
    """CLI for ingesting company data from CSV and orchestrating jobs."""

    def __init__(
        self,
        csv_path: str,
        checkpoint_file: str = "checkpoint.json",
        enable_vector_store: bool = True,
        force_rescrape: bool = False,
    ):
        """Initialize the ingest CLI.

        Args:
            csv_path: Path to the CSV file containing company data
            checkpoint_file: Path to the checkpoint file for resumability
            enable_vector_store: Whether to store data in vector store
            force_rescrape: Whether to force re-scraping even if data exists
        """
        self.csv_path = Path(csv_path)
        self.checkpoint_file = Path(checkpoint_file)
        self.enable_vector_store = enable_vector_store
        self.force_rescrape = force_rescrape
        self.processed_companies: List[str] = []
        self.failed_companies: List[Dict[str, Any]] = []
        self.companies_from_existing_data: List[str] = []
        self.companies_freshly_scraped: List[str] = []
        self.vector_store = None
        self.total_vector_cost = 0.0
        self.logger = self._setup_logging()

        # Initialize vector store if enabled
        if self.enable_vector_store:
            self._init_vector_store()

    def _setup_logging(self) -> logging.Logger:
        """Set up structured logging."""
        logging.basicConfig(
            level=logging.INFO,
            format=(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"message": "%(message)s"}'
            ),
            handlers=[logging.StreamHandler()],
        )
        return logging.getLogger(__name__)

    def _init_vector_store(self) -> None:
        """Initialize the vector store for storing company data."""
        try:
            from .store import VectorStore

            self.vector_store = VectorStore()
            self.logger.info("Vector store initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize vector store: {e}")
            self.logger.warning("Continuing without vector store functionality")
            self.enable_vector_store = False

    def load_checkpoint(self) -> None:
        """Load checkpoint data if it exists."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r") as f:
                    checkpoint_data = json.load(f)
                    self.processed_companies = checkpoint_data.get("processed", [])
                    self.failed_companies = checkpoint_data.get("failed", [])
                processed_count = len(self.processed_companies)
                failed_count = len(self.failed_companies)
                self.logger.info(
                    f"Loaded checkpoint: {processed_count} processed, "
                    f"{failed_count} failed"
                )
            except Exception as e:
                self.logger.warning(f"Failed to load checkpoint: {e}")

    def save_checkpoint(self) -> None:
        """Save current state to checkpoint file."""
        checkpoint_data = {
            "processed": self.processed_companies,
            "failed": self.failed_companies,
        }
        try:
            with open(self.checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)
            self.logger.info("Checkpoint saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")

    def validate_csv(self) -> pd.DataFrame:
        """Validate and load the CSV file.

        Returns:
            DataFrame: Validated company data

        Raises:
            click.BadParameter: If CSV is invalid or missing required columns
        """
        if not self.csv_path.exists():
            raise click.BadParameter(f"CSV file not found: {self.csv_path}")

        try:
            df = pd.read_csv(self.csv_path)
        except Exception as e:
            raise click.BadParameter(f"Failed to read CSV: {e}")

        # Validate required columns
        required_columns = ["url", "industry"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise click.BadParameter(f"Missing required columns: {missing_columns}")

        # Remove rows with missing data
        initial_count = len(df)
        df = df.dropna(subset=required_columns)
        if len(df) < initial_count:
            self.logger.warning(
                f"Removed {initial_count - len(df)} rows with missing data"
            )

        # Validate URLs
        valid_urls = df["url"].str.startswith(("http://", "https://"), na=False)
        df = df[valid_urls]
        if len(df) == 0:
            raise click.BadParameter("No valid URLs found in CSV")

        self.logger.info(f"Loaded {len(df)} valid companies from CSV")
        return df

    async def _store_in_vector_store(
        self, url: str, industry: str, processed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store processed company data in vector store.

        Args:
            url: Company website URL
            industry: Industry classification
            processed_data: Processed content data

        Returns:
            Dict containing vector store result
        """
        if not self.enable_vector_store or not self.vector_store:
            return {"status": "skipped", "reason": "Vector store disabled"}

        try:
            # Create company ID from URL
            company_id = url.replace("https://", "").replace("http://", "")
            company_id = company_id.replace("/", "_").replace(".", "_")

            # Get text chunks from processed data
            chunks = processed_data.get("combined_chunks", [])
            if not chunks:
                return {
                    "status": "skipped",
                    "reason": "No chunks available for storage",
                }

            # Prepare chunk metadata
            chunk_metadata = []
            for i, chunk in enumerate(chunks):
                metadata = {
                    "chunk_id": i,
                    "source_url": url,
                    "industry": industry,
                    "chunk_length": len(chunk),
                    "company_id": company_id,
                    "total_chunks": len(chunks),
                }
                chunk_metadata.append(metadata)

            # Upload to vector store
            self.logger.info(f"Storing {len(chunks)} chunks for {url} in vector store")
            store_id, cost = self.vector_store.upload_chunks_to_store(
                company_id, chunks, chunk_metadata
            )

            self.total_vector_cost += cost

            self.logger.info(
                f"Successfully stored {len(chunks)} chunks for {url}. "
                f"Store ID: {store_id}, Cost: ${cost:.4f}"
            )

            return {
                "status": "success",
                "store_id": store_id,
                "chunks_stored": len(chunks),
                "cost": cost,
                "company_id": company_id,
            }

        except Exception as e:
            self.logger.error(f"Failed to store {url} in vector store: {e}")
            return {"status": "error", "error": str(e)}

    def _check_existing_data(self, url: str) -> Dict[str, Any]:
        """Check if extracted data already exists for the URL.

        Args:
            url: Company website URL

        Returns:
            Dict containing existing data or None if not found
        """
        try:
            # Create safe filename from URL
            safe_url = url.replace("https://", "").replace("http://", "")
            safe_url = safe_url.replace("/", "_").replace(".", "_")

            # Check extracted_data directory
            extracted_dir = Path("extracted_data")
            if not extracted_dir.exists():
                return None

            # Look for processed files matching this URL
            processed_files = list(extracted_dir.glob(f"{safe_url}_processed_*.json"))
            if not processed_files:
                return None

            # Get the most recent file
            latest_file = max(processed_files, key=lambda p: p.stat().st_mtime)

            with open(latest_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

            self.logger.info(f"Found existing data for {url}: {latest_file.name}")
            return existing_data

        except Exception as e:
            self.logger.warning(f"Failed to check existing data for {url}: {e}")
            return None

    async def process_company(self, url: str, industry: str) -> Dict[str, Any]:
        """Process a single company with web scraping and content cleaning.

        Args:
            url: Company website URL
            industry: Industry classification

        Returns:
            Dict containing processing result
        """
        try:
            # Check if we already have extracted data (unless forced to rescrape)
            existing_data = (
                None if self.force_rescrape else self._check_existing_data(url)
            )
            if existing_data:
                self.logger.info(f"Using existing extracted data for {url}")
                self.companies_from_existing_data.append(url)

                # Convert existing data to expected format
                processed_data = {
                    "url": url,
                    "combined_text": existing_data.get("combined_text", ""),
                    "combined_chunks": existing_data.get("combined_chunks", []),
                    "total_length": existing_data.get("total_length", 0),
                    "num_chunks": existing_data.get("num_chunks", 0),
                    "status": "success",
                }

                # Create scraped_data structure for consistency
                scraped_data = {
                    "url": url,
                    "homepage_content": existing_data.get("homepage_cleaned", {}).get(
                        "cleaned_text", ""
                    ),
                    "homepage_text": existing_data.get("homepage_cleaned", {}).get(
                        "cleaned_text", ""
                    ),
                    "about_url": None,
                    "about_text": (
                        existing_data.get("about_cleaned", {}).get("cleaned_text", "")
                        if existing_data.get("about_cleaned")
                        else ""
                    ),
                    "method": "existing_data",
                    "status": "success",
                }

            else:
                # No existing data, proceed with scraping
                self.logger.info(
                    f"No existing data found for {url}, starting fresh scraping"
                )
                self.companies_freshly_scraped.append(url)

                # Import scraper and cleaner
                from .cleaner import ContentCleaner
                from .scraper import WebScraper

                # Initialize scraper and cleaner
                scraper = WebScraper(max_concurrent=5)
                cleaner = ContentCleaner(chunk_size=1000, chunk_overlap=200)

                # Scrape the website
                scraped_data = await scraper.scrape_company(url)

                if scraped_data.get("status") != "success":
                    raise Exception(
                        f"Scraping failed: {scraped_data.get('error', 'Unknown error')}"
                    )

                # Clean and process the content
                processed_data = cleaner.process_scraped_content(scraped_data)

                if processed_data.get("status") != "success":
                    raise Exception(
                        f"Content processing failed: "
                        f"{processed_data.get('error', 'Unknown error')}"
                    )

            # Store in vector store
            vector_result = await self._store_in_vector_store(
                url, industry, processed_data
            )

            return {
                "url": url,
                "industry": industry,
                "status": "success",
                "timestamp": pd.Timestamp.now().isoformat(),
                "scraped_data": scraped_data,
                "processed_data": processed_data,
                "content_length": processed_data.get("total_length", 0),
                "num_chunks": processed_data.get("num_chunks", 0),
                "vector_store_result": vector_result,
            }

        except Exception as e:
            self.logger.error(f"Failed to process {url}: {e}")
            raise e

    async def process_companies_async(
        self, companies_df: pd.DataFrame, max_concurrent: int = 8
    ) -> None:
        """Process companies asynchronously with concurrency control.

        Args:
            companies_df: DataFrame containing company data
            max_concurrent: Maximum number of concurrent jobs
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(url: str, industry: str) -> None:
            async with semaphore:
                try:
                    result = await self.process_company(url, industry)
                    self.processed_companies.append(result["url"])
                    self.logger.info(f"Processed: {url}")
                except Exception as e:
                    self.failed_companies.append(
                        {
                            "url": url,
                            "industry": industry,
                            "error": str(e),
                            "timestamp": pd.Timestamp.now().isoformat(),
                        }
                    )
                    self.logger.error(f"Failed to process {url}: {e}")

        # Create tasks for all companies
        tasks = []
        for _, row in companies_df.iterrows():
            url = str(row["url"])
            industry = str(row["industry"])

            # Skip already processed companies
            if url in self.processed_companies:
                self.logger.info(f"Skipping already processed: {url}")
                continue

            task = process_with_semaphore(url, industry)
            tasks.append(task)

        # Run all tasks concurrently
        if tasks:
            task_count = len(tasks)
            self.logger.info(
                f"Starting processing of {task_count} companies with max "
                f"{max_concurrent} concurrent jobs"
            )
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            self.logger.info("No new companies to process")

    def run(self, max_concurrent: int = 8) -> None:
        """Run the ingestion process.

        Args:
            max_concurrent: Maximum number of concurrent jobs
        """
        try:
            # Load checkpoint
            self.load_checkpoint()

            # Validate and load CSV
            companies_df = self.validate_csv()

            # Process companies
            asyncio.run(self.process_companies_async(companies_df, max_concurrent))

            # Save checkpoint
            self.save_checkpoint()

            # Print summary
            self._print_summary()

        except Exception as e:
            self.logger.error(f"Ingestion failed: {e}")
            raise click.ClickException(str(e))

    def _print_summary(self) -> None:
        """Print processing summary."""
        total_processed = len(self.processed_companies)
        total_failed = len(self.failed_companies)

        self.logger.info("=" * 50)
        self.logger.info("PROCESSING SUMMARY")
        self.logger.info("=" * 50)
        self.logger.info(f"Successfully processed: {total_processed}")
        self.logger.info(f"Failed: {total_failed}")
        self.logger.info(f"Total: {total_processed + total_failed}")

        # Data source breakdown
        existing_count = len(self.companies_from_existing_data)
        fresh_count = len(self.companies_freshly_scraped)
        if existing_count > 0 or fresh_count > 0:
            self.logger.info("\nDATA SOURCE BREAKDOWN")
            self.logger.info("-" * 30)
            self.logger.info(f"Used existing data: {existing_count}")
            self.logger.info(f"Freshly scraped: {fresh_count}")
            if existing_count > 0:
                self.logger.info("💰 Cost savings from using existing data!")

        # Vector store summary
        if self.enable_vector_store and self.vector_store:
            cost_summary = self.vector_store.get_cost_summary()
            self.logger.info("\nVECTOR STORE SUMMARY")
            self.logger.info("-" * 30)
            self.logger.info(
                f"Total vector store cost: ${cost_summary['total_cost']:.4f}"
            )
            self.logger.info(
                f"Companies in vector store: {cost_summary['companies_processed']}"
            )
            self.logger.info(
                f"Average cost per company: ${cost_summary['cost_per_company']:.4f}"
            )
            self.logger.info(f"Embedding model: {cost_summary['embedding_model']}")

            # Budget analysis
            budget_limit = 50.0
            remaining_budget = budget_limit - cost_summary["total_cost"]
            self.logger.info(
                f"Budget remaining: ${remaining_budget:.2f} / ${budget_limit:.2f}"
            )

            if remaining_budget < 0:
                self.logger.warning("⚠️  WARNING: Budget limit exceeded!")
            elif remaining_budget < 5.0:
                self.logger.warning("⚠️  WARNING: Low budget remaining!")

        if self.failed_companies:
            self.logger.info("\nFailed companies:")
            for failed in self.failed_companies:
                self.logger.info(f"  - {failed['url']}: {failed['error']}")


@click.command()
@click.argument("csv_file", type=click.Path(exists=True))
@click.option("--max-concurrent", "-c", default=8, help="Maximum concurrent jobs")
@click.option(
    "--checkpoint", "-cp", default="checkpoint.json", help="Checkpoint file path"
)
@click.option(
    "--enable-vector-store/--disable-vector-store",
    default=True,
    help="Enable/disable vector store integration",
)
@click.option(
    "--force-rescrape",
    is_flag=True,
    default=False,
    help="Force re-scraping even if extracted data exists",
)
def main(
    csv_file: str,
    max_concurrent: int,
    checkpoint: str,
    enable_vector_store: bool,
    force_rescrape: bool,
) -> None:
    """Ingest company data from CSV and orchestrate processing jobs.

    CSV_FILE: Path to CSV file with 'url' and 'industry' columns

    This command will:
    1. Scrape company websites using Firecrawl + httpx fallback
    2. Clean and chunk the content using trafilatura
    3. Store text chunks in OpenAI FileStore for RAG retrieval
    4. Track costs and maintain budget constraints
    """
    try:
        ingest = IngestCLI(csv_file, checkpoint, enable_vector_store, force_rescrape)
        ingest.run(max_concurrent)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()
