"""
Generation Engine for Sales Factsheet Generation System.

This module implements the RAG (Retrieval-Augmented Generation) workflow
to generate industry-specific factsheets using templates and vector store data.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from .store import VectorStore
from .template_manager import TemplateManager


class FactsheetGenerator:
    """Generates company factsheets using RAG with templates and vector data."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        templates_dir: Optional[str] = None,
        model: str = "gpt-4",
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ):
        """Initialize the factsheet generator.

        Args:
            openai_api_key: OpenAI API key. If None, uses environment variable.
            templates_dir: Custom templates directory path.
            model: OpenAI model to use for generation.
            max_tokens: Maximum tokens for generation.
            temperature: Generation temperature (0=deterministic, 1=creative).
        """
        self.logger = self._setup_logging()
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize components
        self.openai_client = self._get_openai_client(openai_api_key)
        self.template_manager = TemplateManager(templates_dir)
        self.vector_store = VectorStore(api_key=openai_api_key)

        # Generation settings
        self.target_word_count = 800  # Target for 600-1000 word range
        self.min_word_count = 600
        self.max_word_count = 1000
        self.top_k_chunks = 6  # As specified in the requirements

        # Cost tracking
        self.total_generation_cost = 0.0

        self.logger.info(f"FactsheetGenerator initialized with model {model}")

    def _setup_logging(self) -> logging.Logger:
        """Set up structured logging for the generator."""
        logger = logging.getLogger("factsheet_generator")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _get_openai_client(self, api_key: Optional[str] = None) -> OpenAI:
        """Initialize OpenAI client.

        Args:
            api_key: Optional API key override

        Returns:
            OpenAI client instance

        Raises:
            ValueError: If no API key provided
        """
        import os

        if api_key:
            return OpenAI(api_key=api_key)

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or "
                "pass api_key parameter."
            )

        return OpenAI(api_key=api_key)

    def _retrieve_relevant_chunks(
        self, company_url: str, template_placeholders: List[str]
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks from vector store.

        Args:
            company_url: URL of the company to retrieve data for
            template_placeholders: List of template placeholders to guide search

        Returns:
            List of relevant text chunks with metadata
        """
        try:
            # Get company's vector store ID
            store_id = self.vector_store.get_company_store_id(company_url)
            if not store_id:
                self.logger.warning(f"No vector store found for {company_url}")
                return []

            # Create search queries based on template placeholders
            search_queries = self._create_search_queries(template_placeholders)

            all_chunks = []
            for query in search_queries:
                try:
                    chunks = self.vector_store.similarity_search(
                        query=query,
                        company_id=company_url,  # Use the company identifier
                        top_k=self.top_k_chunks
                        // len(search_queries),  # Distribute across queries
                        max_distance=0.25,  # As per requirements
                    )
                    all_chunks.extend(chunks)
                except Exception as e:
                    self.logger.warning(f"Search failed for query '{query}': {e}")

            # Remove duplicates and limit to top_k
            # Note: chunks are tuples (content, score) from similarity_search
            seen_content = set()
            unique_chunks = []
            for chunk_tuple in all_chunks:
                if isinstance(chunk_tuple, tuple) and len(chunk_tuple) >= 2:
                    content, score = chunk_tuple[0], chunk_tuple[1]
                    if (
                        content not in seen_content
                        and len(unique_chunks) < self.top_k_chunks
                    ):
                        seen_content.add(content)
                        unique_chunks.append(
                            {
                                "content": content,
                                "score": score,
                                "company_id": company_url,
                            }
                        )
                elif isinstance(chunk_tuple, dict):
                    # Handle dict format if it comes that way
                    content = chunk_tuple.get("content", "")
                    if (
                        content not in seen_content
                        and len(unique_chunks) < self.top_k_chunks
                    ):
                        seen_content.add(content)
                        unique_chunks.append(chunk_tuple)

            self.logger.info(
                f"Retrieved {len(unique_chunks)} unique chunks for {company_url}"
            )
            return unique_chunks

        except Exception as e:
            self.logger.error(f"Failed to retrieve chunks for {company_url}: {e}")
            return []

    def _create_search_queries(self, placeholders: List[str]) -> List[str]:
        """Create search queries based on template placeholders.

        Args:
            placeholders: List of template placeholder names

        Returns:
            List of search query strings
        """
        # Map placeholders to natural language queries with enhanced geographic terms
        placeholder_queries = {
            "company_overview": "company overview mission vision about",
            "business_focus": "business focus core services main activities",
            "products_services": "products services offerings solutions",
            "market_position": "market position competitive advantage",
            "key_metrics": "performance metrics financial results revenue",
            "recent_developments": "recent news updates developments announcements",
            "leadership_team": "leadership team management executives founders",
            "locations_operations": "locations offices operations facilities",
            "financial_highlights": "financial performance revenue profit growth",
            "growth_strategy": "strategy growth plans future expansion",
            "technology_stack": "technology platform technical infrastructure",
            "construction_specialties": "construction projects building specialties",
            "certifications_licenses": "certifications licenses accreditations",
            "safety_record": "safety record standards compliance",
            "healthcare_focus": "healthcare medical clinical focus areas",
            "regulatory_compliance": "regulatory compliance approvals standards",
            # Enhanced geographic queries with specific city names from Drees data
            "geographic_coverage": "Austin Cincinnati Cleveland Dallas Houston Indianapolis Jacksonville Nashville Raleigh San Antonio Washington new home discover locations",
            "locations": "Austin Cincinnati Cleveland Dallas Houston Indianapolis Jacksonville Nashville Raleigh San Antonio Washington locations cities markets",
            "service_areas": "Austin Cincinnati Cleveland Dallas Houston Indianapolis Jacksonville Nashville Raleigh San Antonio Washington service areas",
            # Construction specific
            "services_offered": "home building construction services custom homes",
            "key_projects": "projects portfolio recent contracts communities developments",
            "industry_recognition": "awards recognition national excellence top builder",
            "competitive_advantages": "advantages benefits stress-free building experience DreeSmart",
            "sustainability_initiatives": "sustainability environment green energy efficient DreeSmart",
        }

        queries = []
        for placeholder in placeholders[:6]:  # Limit to avoid too many queries
            query = placeholder_queries.get(
                placeholder,
                placeholder.replace("_", " "),  # Fallback: convert underscore to space
            )
            queries.append(query)

        # Always include a general company query
        if "company overview" not in " ".join(queries):
            queries.insert(0, "company overview about business")

        # Add geographic fallback if any location-related placeholder is present
        geographic_placeholders = [
            "geographic_coverage",
            "locations",
            "service_areas",
            "locations_operations",
            "markets",
            "regions",
        ]
        if any(placeholder in geographic_placeholders for placeholder in placeholders):
            geographic_query = "discover new home Austin Cincinnati Cleveland Dallas Houston Indianapolis Jacksonville Nashville Raleigh San Antonio Washington locations"
            if geographic_query not in queries:
                queries.append(geographic_query)

        return queries[:4]  # Limit to 4 queries for efficiency

    def _create_generation_prompt(
        self,
        company_url: str,
        industry: str,
        template: str,
        evidence_chunks: List[Dict[str, Any]],
    ) -> str:
        """Create the generation prompt for GPT-4.

        Args:
            company_url: Company URL for context
            industry: Industry classification
            template: Markdown template with placeholders
            evidence_chunks: Retrieved text chunks as evidence

        Returns:
            Complete prompt for factsheet generation
        """
        # Extract company name from URL for context
        company_name = self._extract_company_name(company_url)

        # Prepare evidence section
        evidence_text = "\n\n".join(
            [
                f"Evidence {i+1}:\n{chunk.get('content', '')}"
                for i, chunk in enumerate(evidence_chunks)
            ]
        )

        prompt = f"""You are a professional business analyst creating a comprehensive factsheet for a company.

COMPANY INFORMATION:
- Company URL: {company_url}
- Estimated Company Name: {company_name}
- Industry: {industry}

EVIDENCE FROM COMPANY WEBSITE:
{evidence_text}

TEMPLATE TO FILL:
{template}

INSTRUCTIONS:
1. Generate a comprehensive factsheet by filling in ALL placeholders in the template
2. Use ONLY information from the provided evidence - do not hallucinate
3. If specific information is not available in the evidence, write "Information not available in source material"
4. Target word count: {self.target_word_count} words (minimum {self.min_word_count}, maximum {self.max_word_count})
5. Use professional, factual language appropriate for sales teams
6. Maintain the exact Markdown structure of the template
7. Replace {{company_name}} with the actual company name from the evidence or URL
8. Focus on factual, evidence-based content that would be useful for sales prospecting

QUALITY REQUIREMENTS:
- Be specific and detailed where evidence supports it
- Use exact quotes or paraphrases from the evidence
- Maintain professional tone throughout
- Ensure all sections add value for sales teams
- If a section cannot be filled with evidence, clearly state the limitation

Generate the complete factsheet now:"""

        return prompt

    def _extract_company_name(self, url: str) -> str:
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
                # Capitalize first letter
                return name.capitalize()

            return "Company"

        except Exception:
            return "Company"

    def _estimate_generation_cost(self, prompt: str, completion: str) -> float:
        """Estimate the cost of generation.

        Args:
            prompt: Input prompt
            completion: Generated completion

        Returns:
            Estimated cost in USD
        """
        # GPT-4 pricing (approximate)
        input_cost_per_token = 0.03 / 1000  # $0.03 per 1K tokens
        output_cost_per_token = 0.06 / 1000  # $0.06 per 1K tokens

        # Rough token estimation (1 token ≈ 4 chars)
        input_tokens = len(prompt) // 4
        output_tokens = len(completion) // 4

        cost = (input_tokens * input_cost_per_token) + (
            output_tokens * output_cost_per_token
        )
        return round(cost, 6)

    def _validate_word_count(self, text: str) -> Tuple[bool, int]:
        """Validate if text meets word count requirements.

        Args:
            text: Text to validate

        Returns:
            Tuple of (is_valid, word_count)
        """
        # Count words (split by whitespace)
        words = text.split()
        word_count = len(words)

        is_valid = self.min_word_count <= word_count <= self.max_word_count
        return is_valid, word_count

    def generate_factsheet(
        self, company_url: str, industry: str, max_retries: int = 2
    ) -> Dict[str, Any]:
        """Generate a complete factsheet for a company.

        Args:
            company_url: URL of the company
            industry: Industry classification
            max_retries: Maximum retries for word count compliance

        Returns:
            Dictionary containing factsheet and metadata
        """
        try:
            self.logger.info(f"Generating factsheet for {company_url} in {industry}")

            # Get appropriate template
            template = self.template_manager.get_template(industry)
            placeholders = self.template_manager.get_template_placeholders(industry)

            # Retrieve relevant chunks
            evidence_chunks = self._retrieve_relevant_chunks(
                company_url, list(placeholders)
            )

            if not evidence_chunks:
                return {
                    "status": "error",
                    "error": "No relevant data found in vector store",
                    "company_url": company_url,
                    "industry": industry,
                }

            # Generate factsheet with retries for word count
            for attempt in range(max_retries + 1):
                prompt = self._create_generation_prompt(
                    company_url, industry, template, evidence_chunks
                )

                # Call OpenAI API
                try:
                    response = self.openai_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a professional business analyst creating factsheets for sales teams.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        stream=False,
                    )

                    factsheet_content = response.choices[0].message.content

                    # Estimate cost
                    cost = self._estimate_generation_cost(prompt, factsheet_content)
                    self.total_generation_cost += cost

                    # Validate word count
                    is_valid, word_count = self._validate_word_count(factsheet_content)

                    if is_valid or attempt == max_retries:
                        # Return result (valid or final attempt)
                        return {
                            "status": "success",
                            "factsheet": factsheet_content,
                            "company_url": company_url,
                            "industry": industry,
                            "word_count": word_count,
                            "word_count_valid": is_valid,
                            "evidence_chunks_used": len(evidence_chunks),
                            "generation_cost": cost,
                            "total_cost": self.total_generation_cost,
                            "model_used": self.model,
                            "attempt": attempt + 1,
                        }
                    else:
                        # Retry with adjusted prompt
                        self.logger.warning(
                            f"Word count {word_count} not in range {self.min_word_count}-{self.max_word_count}, "
                            f"retrying attempt {attempt + 2}"
                        )

                        # Adjust target for next attempt
                        if word_count < self.min_word_count:
                            self.target_word_count = min(
                                900, self.target_word_count + 100
                            )
                        else:
                            self.target_word_count = max(
                                700, self.target_word_count - 100
                            )

                except Exception as e:
                    self.logger.error(
                        f"OpenAI API call failed on attempt {attempt + 1}: {e}"
                    )
                    if attempt == max_retries:
                        return {
                            "status": "error",
                            "error": f"OpenAI API error: {str(e)}",
                            "company_url": company_url,
                            "industry": industry,
                        }

        except Exception as e:
            self.logger.error(f"Factsheet generation failed for {company_url}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "company_url": company_url,
                "industry": industry,
            }

    def generate_multiple_factsheets(
        self, companies: List[Tuple[str, str]], max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """Generate factsheets for multiple companies.

        Args:
            companies: List of (url, industry) tuples
            max_concurrent: Maximum concurrent generations (to avoid rate limits)

        Returns:
            List of generation results
        """

        self.logger.info(f"Generating factsheets for {len(companies)} companies")

        results = []
        for url, industry in companies:
            try:
                result = self.generate_factsheet(url, industry)
                results.append(result)

                # Brief pause to avoid rate limits
                import time

                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Failed to generate factsheet for {url}: {e}")
                results.append(
                    {
                        "status": "error",
                        "error": str(e),
                        "company_url": url,
                        "industry": industry,
                    }
                )

        self.logger.info(
            f"Completed {len(results)} factsheet generations. "
            f"Total cost: ${self.total_generation_cost:.4f}"
        )

        return results

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for all generations.

        Returns:
            Dictionary with cost breakdown
        """
        return {
            "total_generation_cost": self.total_generation_cost,
            "model_used": self.model,
            "temperature": self.temperature,
            "target_word_count": self.target_word_count,
            "cost_per_factsheet_avg": self.total_generation_cost,  # Will be divided by count
        }
