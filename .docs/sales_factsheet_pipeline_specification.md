# Sales Factsheet Generation System — Technical Spec

## 1. Problem Statement

Sales teams need a **600‑1000‑word factsheet** for any prospect company, pulled from public web data. The brief requires:

- Input: a CSV containing `url, industry` rows.
- Output: `<company>.md` factsheet + `<company>_accuracy.md` QA report.
- Budget: ≤ US \$50 OpenAI credits.
- Evidence‑based summaries (minimal hallucination).

## 2. Solution Overview

A modular pipeline that:

1. **Ingests** each URL.
2. **Scrapes & cleans** HTML into plain text.
3. **Embeds & indexes** chunks in a vector store (OpenAI FileStore / FAISS).
4. **Retrieves** relevant facts and **fills an industry‑specific Markdown template** via GPT‑4o.
5. **Validates** the generated factsheet using a two‑way LLM Q‑&‑A procedure to compute an **accuracy score**.
6. Writes two files per company: `factsheets/<slug>.md` and `factsheets/<slug>_accuracy.md`.

## 3. Functional Requirements

| ID  | Requirement          | Acceptance Criteria                                                       |
| --- | -------------------- | ------------------------------------------------------------------------- |
| F‑1 | CSV ingestion        | Each row processed exactly once; resumable on crash.                      |
| F‑2 | Scraping             | Must respect robots.txt and capture at least Homepage + About page.       |
| F‑3 | Cleaning             | Strip boiler‑plate, nav, ads; output ≤ 5 MB per company.                  |
| F‑4 | Vector indexing      | Store all text chunks with embeddings; similarity ≤ 0.25 cosine distance. |
| F‑5 | Template selection   | Choose correct industry template or fall back to generic.                 |
| F‑6 | Factsheet generation | Markdown length 600‑1000 words; all mandatory sections present.           |
| F‑7 | Accuracy scoring     | Generate ≥ 50 Q‑&‑A pairs each way and compute score (≥ 0 ≤ 1 range).     |
| F‑8 | Budget guard         | Abort run if projected cost for remaining rows > budget‑left.             |

## 4. Non‑Functional Requirements

- **Reproducibility** – deterministic outputs given fixed OpenAI temperature.
- **Observability** – structured logs (JSON) + token/cost counters.
- **Extensibility** – easy to add new industry templates.
- **Performance** – end‑to‑end throughput ≥ 3 companies/min on 8 concurrent workers.
- **Compliance** – no storage of personal data; respect rate limits.

## 5. High‑Level Architecture

```
CSV → Ingest CLI → Scraper → Cleaner → Vector Store ↘
                                        ↙
Template Manager → Generation Engine (RAG) → Factsheet .md
                                      ↘
                        Validation Engine → Accuracy .md
```

(See user‑supplied sketch for visual.)

## 6. Component Breakdown & Tasks

### 6.1 Ingest CLI (`src/ingest.py`)

- Parse CSV row‑by‑row.
- Spawn async job per company.
- Maintain run‑state checkpoint.

### 6.2 Scraper (`src/scraper.py`)

- Use **Firecrawl API** first; fall back to `httpx + BeautifulSoup`.
- Respect concurrency = 5.

### 6.3 Cleaner (`src/cleaner.py`)

- `trafilatura` for boiler‑plate removal.
- Chunk at 1 000 tokens with 200‑token overlap.

### 6.4 Vector Store (`src/store.py`)

- API wrapper for OpenAI FileStore embeddings.
- Local FAISS fallback.

### 6.5 Template Manager (`src/templates/`)

- `.md` files keyed by industry slug.
- Function `get_template(industry: str) -> str`.

### 6.6 Generation Engine (`src/generate.py`)

- Retrieve top‑k (k = 6) chunks.
- Prompt GPT‑4o with template + evidence.
- Enforce word‑count gate.

### 6.7 Validation Engine (`src/validate.py`)

- **Question creator** LLM: produce 50 questions from raw text.
- **Answerer** LLM: answer from (a) raw text, (b) factsheet.
- Compare answers via semantic similarity; average = accuracy score.

### 6.8 Writer (`src/output.py`)

- Slugify company name.
- Save Markdown files in `factsheets/`.

### 6.9 Orchestrator (`run.py`)

- Glue everything; maintain cost budget.

## 7. Development Road‑Map (Cursor Tasks)

1. **Repo bootstrap** – `git init`, add `pyproject.toml`, pre‑commit hooks.
2. **Ingest CLI** – parse CSV + unit test.
3. **Scraper & Cleaner** – implement with mocks; integration test with example.com.
4. **Vector Store wrapper** – write embedding cache layer; unit test similarity search.
5. **Template Manager** – add generic + construction templates; unit test selection.
6. **Generation Engine** – implement RAG workflow; smoke test token cost.
7. **Writer** – ensure file naming & word‑count validation.
8. **Validation Engine** – build two‑way Q&A; test scoring on toy data.
9. **Budget guard & logging** – integrate cost counters.
10. **CI pipeline** – GitHub Actions for lint + pytest.

## 8. Testing & QA

- **Unit tests** for every module (pytest).
- **Integration test**: run pipeline on 2 sample companies; assert output files & accuracy ≥ 0.7.
- **Load test**: 100 dummy URLs with stubbed scraper.

## 9. Deliverables

- Source code under `src/`.
- `README.md` with setup & usage.
- `requirements.txt`.
- Sample `companies.csv`.
- Two sample output pairs (`.md` + `_accuracy.md`).
- UML/architecture diagram PNG.

## 10. Future Improvements

- Add news‑feed scraping for “Recent Milestones.”
- Support multilingual sites.
- Replace accuracy heuristic with factuality LlamaGuard fine‑tuned model.
