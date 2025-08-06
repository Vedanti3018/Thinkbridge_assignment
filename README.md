# Sales Factsheet Generation System

A modular, AI-powered pipeline that automatically generates comprehensive sales factsheets for prospect companies using public web data.

## Problem Statement

Sales teams need **600-1000 word factsheets** for any prospect company, but manually creating these documents is time-consuming and inconsistent. This system addresses the challenge by:

- **Input**: CSV containing `url, industry` rows
- **Output**: `<company>.md` factsheet + `<company>_accuracy.md` QA report
- **Budget**: ≤ $50 OpenAI credits per batch
- **Quality**: Evidence-based summaries with minimal hallucination

## Purpose & Solution

This system automates the creation of professional sales factsheets by leveraging:

1. **Web Scraping**: Intelligent content extraction from company websites
2. **RAG (Retrieval-Augmented Generation)**: Vector-based information retrieval
3. **Industry Templates**: Structured, industry-specific factsheet formats
4. **Quality Validation**: Automated accuracy scoring with LLM-based Q&A

### Key Benefits
- ✅ **Scalable**: Process multiple companies automatically
- ✅ **Accurate**: Evidence-based content with validation scoring
- ✅ **Consistent**: Industry-specific templates ensure uniform quality
- ✅ **Cost-effective**: Smart caching and budget management
- ✅ **Resumable**: Checkpoint system for interrupted runs

## Solution Workflow

```
CSV Input → Ingest CLI → Web Scraper → Content Cleaner → Vector Store ↘
                                                           ↙
    Template Manager → Generation Engine (RAG) → Factsheet.md
                                         ↘
                           Validation Engine → Accuracy.md
```

### Detailed Pipeline Steps

1. **Ingestion** (`src/ingest.py`)
   - Parse CSV with company URLs and industries
   - Maintain processing checkpoints for resumability
   - Smart caching to avoid redundant API calls

2. **Web Scraping** (`src/scraper.py`)
   - Primary: Firecrawl API for comprehensive crawling
   - Fallback: httpx + BeautifulSoup for basic scraping
   - Respects robots.txt and rate limits

3. **Content Cleaning** (`src/cleaner.py`)
   - Remove boilerplate, navigation, and ads using trafilatura
   - Intelligent text chunking with 1000-token segments
   - 200-token overlap for context preservation

4. **Vector Storage** (`src/store.py`)
   - OpenAI FileStore for embeddings and similarity search
   - Chunk indexing with cosine similarity ≤ 0.25
   - Cost tracking and metadata management

5. **Template Management** (`src/templates/`)
   - Industry-specific Markdown templates
   - Automatic template selection with generic fallback
   - Support for construction, technology, healthcare, fintech industries

6. **Content Generation** (`src/generate.py`)
   - RAG-based factsheet generation using GPT-4
   - Top-k (k=6) relevant chunk retrieval
   - Word count enforcement (600-1000 words)

7. **Quality Validation** (*Future Implementation*)
   - Planned: Two-way LLM Q&A accuracy assessment
   - Will generate 50+ question-answer pairs for validation
   - Semantic similarity scoring for accuracy measurement

8. **File Output** (`src/output.py`)
   - Clean filename generation (`<company>.md`)
   - Word count validation and metadata tracking
   - Organized factsheet and accuracy report generation

## Architecture Components

### Core Modules

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| `ingest.py` | CSV processing and orchestration | Checkpoint system, async processing |
| `scraper.py` | Web content extraction | Firecrawl API + fallback, rate limiting |
| `cleaner.py` | Content preprocessing | Boilerplate removal, smart chunking |
| `store.py` | Vector storage and retrieval | OpenAI FileStore, similarity search |
| `template_manager.py` | Industry template selection | Dynamic template matching |
| `generate.py` | RAG-based factsheet generation | GPT-4 integration, evidence-based generation |
| `validate.py` | Quality assurance (*Future*) | Planned LLM-based accuracy scoring |
| `output.py` | File management | Clean naming, validation, metadata |

### Templates Available

- **Construction**: Project portfolios, certifications, safety records
- **Technology**: Tech stack, innovation metrics, development practices
- **Healthcare**: Compliance, certifications, clinical focus areas
- **Fintech**: Regulatory status, security measures, financial metrics
- **Generic**: Universal template for any industry

## Quick Start

### Prerequisites

- Python 3.9+
- Poetry (for dependency management)
- OpenAI API key
- Firecrawl API key (optional, recommended)

### Installation

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd thinkbridge
   poetry install
   ```

2. **Configure environment**:
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=your_openai_key_here" > .env
   echo "FIRECRAWL_API_KEY=your_firecrawl_key_here" >> .env
   ```

3. **Prepare input data**:
   ```bash
   # Create companies.csv
   echo "url,industry" > companies.csv
   echo "https://example-company.com,Construction" >> companies.csv
   ```

### Usage

#### Basic Factsheet Generation

```bash
# Activate Poetry environment
poetry shell

# Run the complete pipeline
poetry run python -m thinkbridge.ingest companies.csv --enable-vector-store
```

#### Advanced Options

```bash
# Force re-scraping (ignore cache)
poetry run python -m thinkbridge.ingest companies.csv --force-rescrape --enable-vector-store

# Generate with specific concurrency
poetry run python -m thinkbridge.ingest companies.csv --workers 3 --enable-vector-store
```

### Output Structure

After successful execution:

```
factsheets/
├── company-name.md              # Main factsheet (600-1000 words)
└── company-name_accuracy.md     # Quality validation report (Future Implementation)

extracted_data/                  # Cached scraped content
├── company_processed_*.json
└── ...

vector_stores_metadata.json     # Vector store tracking
```

## Sample Output

### Factsheet Example (`company.md`)
```markdown
# Company Name • Industry Factsheet

> Elevator pitch and key value proposition

| HQ | Founded | Employees | Annual Revenue | Operating Regions |
|----|---------|-----------|----------------|-------------------|
| Location | Year | Count | Amount | Geographic Coverage |

## Core Services
| Service | Description |
|---------|-------------|
| Primary Service | Detailed description |
| Secondary Service | Detailed description |

## Technology & Innovation
| Area | Current Adoption |
|------|------------------|
| BIM | Implementation level |
| Field Tech | Technologies used |

## Recent Milestones
1. **Date** – Achievement description
2. **Date** – Achievement description

## Why This Matters to Your Company
Strategic value proposition for technology partnerships...
```

### Accuracy Report (`company_accuracy.md`) - *Future Implementation*
```markdown
# Accuracy Assessment Report

**Overall Accuracy Score**: 0.85/1.00

## Validation Summary
- Questions Generated: 52
- Correct Answers: 44
- Accuracy Rate: 84.6%

## Key Findings
- High accuracy in factual information
- Strong performance on company overview
- Minor discrepancies in financial data

*Note: This validation system is planned for future implementation*
```

## Development

### Project Structure
```
src/thinkbridge/
├── ingest.py              # Main CLI and orchestration
├── scraper.py             # Web scraping functionality
├── cleaner.py             # Content preprocessing
├── store.py               # Vector storage operations
├── template_manager.py    # Template selection logic
├── templates/             # Industry-specific templates
│   ├── construction.md
│   ├── technology.md
│   ├── healthcare.md
│   ├── fintech.md
│   └── generic.md
├── generate.py           # RAG-based generation
├── validate.py           # Quality validation (Future Implementation)
└── output.py            # File output management

tests/                   # Comprehensive test suite
├── test_ingest.py
├── test_scraper.py
├── test_cleaner.py
├── test_store.py
├── test_template_manager.py
├── test_generate.py
├── test_validate.py      # (Future Implementation)
└── test_output.py
```

### Development Setup

1. **Install development dependencies**:
   ```bash
   poetry install --with dev
   ```

2. **Setup pre-commit hooks**:
   ```bash
   poetry run pre-commit install
   ```

3. **Run tests**:
   ```bash
   poetry run pytest
   ```

4. **Code quality checks**:
   ```bash
   # Format code
   poetry run black src/ tests/

   # Check linting
   poetry run flake8 src/ tests/

   # Type checking
   poetry run mypy src/

   # Sort imports
   poetry run isort src/ tests/
   ```

### Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src/thinkbridge

# Run specific test modules
poetry run pytest tests/test_ingest.py -v

# Integration tests
poetry run pytest tests/test_integration.py
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4 and embeddings |
| `FIRECRAWL_API_KEY` | No | Firecrawl API key (recommended for better scraping) |

### Budget Management

The system includes automatic budget tracking:
- Monitors OpenAI API costs in real-time
- Aborts execution if projected costs exceed $50
- Detailed cost breakdown in logs

### Smart Caching Features

- **Data Persistence**: Scraped content cached in `extracted_data/`
- **Vector Store Reuse**: Embeddings stored for future runs
- **Checkpoint Recovery**: Resume interrupted processing
- **Force Refresh**: `--force-rescrape` flag bypasses cache

## Cost Optimization

- **Efficient Chunking**: Optimal token usage with 1000-token chunks
- **Vector Store Reuse**: Avoid re-embedding existing content
- **Template Selection**: Industry-specific templates reduce generation costs
- **Batch Processing**: Concurrent processing with rate limit respect
- **Budget Guards**: Automatic cost monitoring and limits

## Troubleshooting

### Common Issues

1. **API Rate Limits**:
   ```bash
   # Reduce concurrency
   --workers 1
   ```

2. **SSL Certificate Errors**:
   ```bash
   # Check your network connection and try again
   # The system has built-in SSL error handling
   ```

3. **Memory Issues with Large Sites**:
   ```bash
   # Content is automatically chunked and limited to 5MB per company
   ```

4. **Template Not Found**:
   ```bash
   # System automatically falls back to generic template
   # Check available templates in src/thinkbridge/templates/
   ```

### Debug Mode

```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
poetry run python -m thinkbridge.ingest companies.csv --enable-vector-store
```

## Future Scope & Planned Enhancements

### 🔮 Validation Engine (`src/validate.py`)

**Status**: Planned for next release
**Priority**: High

#### How the Validation Engine Will Work

The validation engine will implement a sophisticated **two-way LLM Q&A accuracy assessment** system to ensure factsheet quality and minimize hallucination.

##### **Architecture Overview**

```
Raw Company Data → Question Generator → Ground Truth Answers ↘
                                                              ↘
Generated Factsheet → Question Generator → Factsheet Answers → Similarity Scorer → Accuracy Score
```

##### **Detailed Implementation Plan**

**1. Question Generation Phase**
```python
class QuestionGenerator:
    def generate_questions(self, source_text: str, num_questions: int = 50) -> List[str]:
        """
        Generate diverse, fact-checking questions from source material.

        Question Types:
        - Factual: "What year was the company founded?"
        - Quantitative: "How many employees does the company have?"
        - Categorical: "What industry does the company operate in?"
        - Relational: "Who are the company's key partners?"
        """
```

**2. Dual Answer Generation**
```python
class AnswerGenerator:
    def answer_from_source(self, questions: List[str], raw_data: str) -> List[str]:
        """Generate answers using original scraped content as truth source."""

    def answer_from_factsheet(self, questions: List[str], factsheet: str) -> List[str]:
        """Generate answers using generated factsheet content."""
```

**3. Semantic Similarity Scoring**
```python
class AccuracyScorer:
    def calculate_accuracy(self,
                          ground_truth_answers: List[str],
                          factsheet_answers: List[str]) -> float:
        """
        Compare answer pairs using:
        - Semantic similarity (OpenAI embeddings)
        - Named entity matching
        - Numerical value comparison
        - Factual consistency checking

        Returns: Accuracy score between 0.0 and 1.0
        """
```

##### **Validation Process Flow**

1. **Input Processing**
   - Raw scraped company data (source of truth)
   - Generated factsheet content
   - Industry context for question relevance

2. **Question Generation** (GPT-4)
   ```
   Prompt: "Generate 50 specific, fact-checkable questions about this company
   based on the scraped content. Focus on verifiable information like dates,
   numbers, locations, and business relationships."
   ```

3. **Ground Truth Answers** (GPT-4 + Raw Data)
   ```
   Prompt: "Answer these questions using ONLY the provided scraped content.
   If information is not available, respond with 'Not found in source material'."
   ```

4. **Factsheet Answers** (GPT-4 + Generated Factsheet)
   ```
   Prompt: "Answer these questions using ONLY the provided factsheet content.
   If information is not available, respond with 'Not found in factsheet'."
   ```

5. **Similarity Assessment**
   - Embed both answer sets using `text-embedding-3-small`
   - Calculate cosine similarity for each question pair
   - Apply weighted scoring based on question importance
   - Generate overall accuracy score

##### **Quality Metrics**

The validation engine will track:

| Metric | Description | Target |
|--------|-------------|---------|
| **Overall Accuracy** | Average similarity across all Q&A pairs | ≥ 0.80 |
| **Factual Consistency** | Exact matches for dates, numbers, names | ≥ 0.95 |
| **Coverage Score** | % of source facts included in factsheet | ≥ 0.70 |
| **Hallucination Rate** | Facts in factsheet not found in source | ≤ 0.05 |

##### **Output Report Structure**

```markdown
# Accuracy Assessment Report for [Company Name]

## Executive Summary
- **Overall Accuracy Score**: 0.847/1.000
- **Validation Status**: ✅ PASSED (≥0.80 threshold)
- **Total Questions**: 52
- **High Confidence Answers**: 44 (84.6%)

## Detailed Analysis

### By Information Category
| Category | Questions | Accuracy | Notes |
|----------|-----------|----------|--------|
| Company Overview | 8 | 0.92 | Excellent coverage |
| Financial Data | 6 | 0.78 | Minor revenue discrepancies |
| Geographic Coverage | 10 | 0.89 | All markets correctly identified |
| Leadership Team | 4 | 0.71 | Some titles unclear |

### Failed Validations
1. **Question**: "What was the 2023 revenue?"
   - **Source Answer**: "$847M (estimated from press release)"
   - **Factsheet Answer**: "$850M+"
   - **Issue**: Slight numerical discrepancy
   - **Severity**: Low

### Recommendations
- ✅ Factsheet ready for sales use
- ⚠️ Review financial figures for precision
- 📊 Strong performance on core business information
```


## License

This project is licensed under the MIT License - see the LICENSE file for details.

---
