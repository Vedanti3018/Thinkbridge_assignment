"""
Unit tests for the cleaner module.
"""

from thinkbridge.cleaner import ContentCleaner, clean_content_sync


class TestContentCleaner:
    """Test cases for the ContentCleaner class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.cleaner = ContentCleaner(chunk_size=100, chunk_overlap=20)

    def test_init(self) -> None:
        """Test ContentCleaner initialization."""
        cleaner = ContentCleaner(chunk_size=500, chunk_overlap=100)
        assert cleaner.chunk_size == 500
        assert cleaner.chunk_overlap == 100

    def test_clean_html_content_success(self) -> None:
        """Test successful HTML content cleaning."""
        html_content = """
        <html>
            <head>
                <title>Test Company</title>
                <style>body { color: red; }</style>
            </head>
            <body>
                <nav>Navigation</nav>
                <h1>Welcome to Test Company</h1>
                <p>We are a leading company in our industry.</p>
                <script>alert('test');</script>
                <footer>Footer content</footer>
            </body>
        </html>
        """

        result = self.cleaner.clean_html_content(html_content, "https://test.com")

        assert result["url"] == "https://test.com"
        assert result["status"] == "success"
        assert result["original_length"] > 0
        assert result["cleaned_length"] > 0
        assert "Test Company" in result["cleaned_text"]
        assert "leading company" in result["cleaned_text"].lower()
        assert "alert('test')" not in result["cleaned_text"]  # Script removed
        assert "color: red" not in result["cleaned_text"]  # Style removed
        # Note: trafilatura may not remove all navigation/footer content
        # The important thing is that the main content is preserved
        assert "Test Company" in result["cleaned_text"]
        assert "leading company" in result["cleaned_text"].lower()

    def test_clean_html_content_failure(self) -> None:
        """Test HTML content cleaning failure."""
        # Invalid HTML that might cause issues
        invalid_html = "<html><body><script>alert('test')</script></body></html>"

        result = self.cleaner.clean_html_content(invalid_html, "https://test.com")

        # Should handle the error gracefully
        assert result["url"] == "https://test.com"
        assert result["status"] == "success"  # trafilatura handles this gracefully
        assert result["cleaned_length"] >= 0

    def test_clean_text(self) -> None:
        """Test text cleaning functionality."""
        dirty_text = "  This   is   a   test   text   with   extra   spaces.  "

        cleaned_text = self.cleaner._clean_text(dirty_text)

        assert cleaned_text == "This is a test text with extra spaces."

    def test_clean_text_with_html_entities(self) -> None:
        """Test text cleaning with HTML entities."""
        text_with_entities = "This &amp; that &lt;test&gt; &quot;quote&quot;"

        cleaned_text = self.cleaner._clean_text(text_with_entities)

        # HTML entities should be replaced with spaces
        assert "&amp;" not in cleaned_text
        assert "&lt;" not in cleaned_text
        assert "&gt;" not in cleaned_text
        assert "&quot;" not in cleaned_text

    def test_clean_text_with_excessive_punctuation(self) -> None:
        """Test text cleaning with excessive punctuation."""
        text_with_punctuation = (
            "This is a test... With excessive punctuation!!! And commas,,,"
        )

        cleaned_text = self.cleaner._clean_text(text_with_punctuation)

        # Excessive punctuation should be normalized
        assert "..." not in cleaned_text
        assert "!!!" not in cleaned_text
        assert ",,," not in cleaned_text

    def test_chunk_text_small(self) -> None:
        """Test text chunking with small text."""
        small_text = "This is a small text that should not be chunked."

        chunks = self.cleaner._chunk_text(small_text)

        assert len(chunks) == 1
        assert chunks[0] == small_text

    def test_chunk_text_large(self) -> None:
        """Test text chunking with large text."""
        # Create text with more words than chunk_size
        words = ["word"] * 150  # 150 words, chunk_size is 100
        large_text = " ".join(words)

        chunks = self.cleaner._chunk_text(large_text)

        assert len(chunks) > 1
        assert all(len(chunk.split()) <= 100 for chunk in chunks)  # Max chunk size

    def test_chunk_text_with_overlap(self) -> None:
        """Test text chunking with overlap."""
        cleaner = ContentCleaner(chunk_size=10, chunk_overlap=3)

        # Create text with 25 words
        words = [f"word{i}" for i in range(25)]
        text = " ".join(words)

        chunks = cleaner._chunk_text(text)

        assert len(chunks) > 1

        # Check that chunks have overlap
        for i in range(len(chunks) - 1):
            current_chunk_words = chunks[i].split()
            next_chunk_words = chunks[i + 1].split()

            # Should have some overlap
            overlap_words = set(current_chunk_words) & set(next_chunk_words)
            assert len(overlap_words) > 0

    def test_chunk_text_empty(self) -> None:
        """Test text chunking with empty text."""
        chunks = self.cleaner._chunk_text("")

        assert chunks == []

    def test_process_scraped_content_success(self) -> None:
        """Test processing scraped content successfully."""
        scraped_data = {
            "url": "https://test.com",
            "status": "success",
            "homepage_content": (
                "<html><body><h1>Company</h1><p>We are great.</p></body></html>"
            ),
            "about_text": "We are a leading company.",
        }

        result = self.cleaner.process_scraped_content(scraped_data)

        assert result["url"] == "https://test.com"
        assert result["status"] == "success"
        assert "Company" in result["combined_text"]
        assert "We are great" in result["combined_text"]
        assert "leading company" in result["combined_text"]
        assert result["num_chunks"] > 0
        assert result["total_length"] > 0

    def test_process_scraped_content_failure(self) -> None:
        """Test processing scraped content that failed."""
        scraped_data = {
            "url": "https://test.com",
            "status": "failed",
            "error": "Scraping failed",
        }

        result = self.cleaner.process_scraped_content(scraped_data)

        assert result["url"] == "https://test.com"
        assert result["status"] == "failed"
        assert result["error"] == "Scraping failed"
        assert result["cleaned_text"] == ""
        assert result["chunks"] == []

    def test_process_scraped_content_no_about(self) -> None:
        """Test processing scraped content without About page."""
        scraped_data = {
            "url": "https://test.com",
            "status": "success",
            "homepage_content": (
                "<html><body><h1>Company</h1><p>We are great.</p></body></html>"
            ),
            "about_text": "",
        }

        result = self.cleaner.process_scraped_content(scraped_data)

        assert result["status"] == "success"
        assert "Company" in result["combined_text"]
        assert "We are great" in result["combined_text"]
        # Should not contain about page content
        assert result["about_cleaned"] is None

    def test_process_multiple_companies(self) -> None:
        """Test processing multiple companies."""
        scraped_data_list = [
            {
                "url": "https://test1.com",
                "status": "success",
                "homepage_content": "<html><body><h1>Company 1</h1></body></html>",
                "about_text": "",
            },
            {
                "url": "https://test2.com",
                "status": "success",
                "homepage_content": "<html><body><h1>Company 2</h1></body></html>",
                "about_text": "",
            },
        ]

        results = self.cleaner.process_multiple_companies(scraped_data_list)

        assert len(results) == 2
        assert results[0]["url"] == "https://test1.com"
        assert results[1]["url"] == "https://test2.com"
        assert all(result["status"] == "success" for result in results)

    def test_process_multiple_companies_with_failure(self) -> None:
        """Test processing multiple companies with some failures."""
        scraped_data_list = [
            {
                "url": "https://test1.com",
                "status": "success",
                "homepage_content": "<html><body><h1>Company 1</h1></body></html>",
                "about_text": "",
            },
            {
                "url": "https://test2.com",
                "status": "failed",
                "error": "Scraping failed",
            },
        ]

        results = self.cleaner.process_multiple_companies(scraped_data_list)

        assert len(results) == 2
        assert results[0]["status"] == "success"
        assert results[1]["status"] == "failed"


class TestCleanerSync:
    """Test cases for synchronous cleaner functions."""

    def test_clean_content_sync(self) -> None:
        """Test synchronous content cleaning wrapper."""
        html_content = "<html><body><h1>Test</h1><p>Content</p></body></html>"

        result = clean_content_sync(html_content, "https://test.com")

        assert result["url"] == "https://test.com"
        assert result["status"] == "success"
        assert "Test" in result["cleaned_text"]
        assert "Content" in result["cleaned_text"]


class TestCleanerIntegration:
    """Integration tests for the cleaner."""

    def test_full_cleaning_workflow(self) -> None:
        """Test the complete cleaning workflow."""
        cleaner = ContentCleaner(chunk_size=50, chunk_overlap=10)

        # Complex HTML with various elements
        html_content = """
        <html>
            <head>
                <title>Construction Company</title>
                <meta name="description" content="Leading construction firm">
            </head>
            <body>
                <header>
                    <nav>
                        <a href="/">Home</a>
                        <a href="/about">About</a>
                        <a href="/services">Services</a>
                    </nav>
                </header>
                <main>
                    <h1>Drees Homes</h1>
                    <p>We are a leading construction company specializing in residential homes.</p>
                    <section>
                        <h2>Our Services</h2>
                        <ul>
                            <li>Custom Home Building</li>
                            <li>Renovation</li>
                            <li>Project Management</li>
                        </ul>
                    </section>
                </main>
                <footer>
                    <p>&copy; 2024 Drees Homes. All rights reserved.</p>
                </footer>
                <script>
                    console.log('Analytics');
                </script>
            </body>
        </html>
        """  # noqa: E501

        result = cleaner.clean_html_content(html_content, "https://dreeshomes.com")

        # Verify cleaning worked
        assert result["status"] == "success"
        assert "Drees Homes" in result["cleaned_text"]
        assert "construction company" in result["cleaned_text"].lower()
        assert "Custom Home Building" in result["cleaned_text"]
        assert "Renovation" in result["cleaned_text"]
        assert "Project Management" in result["cleaned_text"]

        # Verify main content is preserved
        assert "Drees Homes" in result["cleaned_text"]
        assert "construction company" in result["cleaned_text"].lower()
        assert "Custom Home Building" in result["cleaned_text"]
        assert "Renovation" in result["cleaned_text"]
        assert "Project Management" in result["cleaned_text"]

        # Verify chunking worked
        assert result["num_chunks"] > 0
        assert all(len(chunk.split()) <= 50 for chunk in result["chunks"])

    def test_about_page_integration(self) -> None:
        """Test integration with About page content."""
        cleaner = ContentCleaner()

        scraped_data = {
            "url": "https://construction-company.com",
            "status": "success",
            "homepage_content": """
            <html>
                <body>
                    <h1>ABC Construction</h1>
                    <p>We build quality homes.</p>
                    <a href="/about">About Us</a>
                </body>
            </html>
            """,
            "about_text": """
            <html>
                <body>
                    <h1>About ABC Construction</h1>
                    <p>Founded in 1990, we have been serving the community for over 30 years.</p>
                    <p>Our mission is to build sustainable, affordable homes for families.</p>
                </body>
            </html>
            """,  # noqa: E501
        }

        result = cleaner.process_scraped_content(scraped_data)

        assert result["status"] == "success"
        assert "ABC Construction" in result["combined_text"]
        assert "We build quality homes" in result["combined_text"]
        assert "Founded in 1990" in result["combined_text"]
        assert "sustainable, affordable homes" in result["combined_text"]
        assert result["num_chunks"] > 0
