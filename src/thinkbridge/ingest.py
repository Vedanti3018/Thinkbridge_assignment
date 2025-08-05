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

    def __init__(self, csv_path: str, checkpoint_file: str = "checkpoint.json"):
        """Initialize the ingest CLI.

        Args:
            csv_path: Path to the CSV file containing company data
            checkpoint_file: Path to the checkpoint file for resumability
        """
        self.csv_path = Path(csv_path)
        self.checkpoint_file = Path(checkpoint_file)
        self.processed_companies: List[str] = []
        self.failed_companies: List[Dict[str, Any]] = []
        self.logger = self._setup_logging()

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

    async def process_company(self, url: str, industry: str) -> Dict[str, Any]:
        """Process a single company with web scraping and content cleaning.

        Args:
            url: Company website URL
            industry: Industry classification

        Returns:
            Dict containing processing result
        """
        try:
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

            return {
                "url": url,
                "industry": industry,
                "status": "success",
                "timestamp": pd.Timestamp.now().isoformat(),
                "scraped_data": scraped_data,
                "processed_data": processed_data,
                "content_length": processed_data.get("total_length", 0),
                "num_chunks": processed_data.get("num_chunks", 0),
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
def main(csv_file: str, max_concurrent: int, checkpoint: str) -> None:
    """Ingest company data from CSV and orchestrate processing jobs.

    CSV_FILE: Path to CSV file with 'url' and 'industry' columns
    """
    try:
        ingest = IngestCLI(csv_file, checkpoint)
        ingest.run(max_concurrent)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()
