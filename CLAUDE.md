# GovBR News Scraper - Claude Code Guide

## Project Overview

The **GovBR News Scraper** is an experimental tool developed by the Ministry of Management and Innovation in Public Services (MGI) to collect and organize news from government agency websites in the gov.br domain. The tool performs daily scraping, extracting relevant metadata (title, date, category, content, etc.) and publishing it to Hugging Face Hub.

**Key Features:**
- Daily automated scraping of Brazilian government news
- AI-powered content enrichment and classification
- Dataset publishing to Hugging Face Hub
- Docker-based deployment with Typesense search integration
- CSV exports by agency and year

## Architecture

### Core Components

1. **Scraping System** ([src/scraper/](src/scraper/))
   - [webscraper.py](src/scraper/webscraper.py) - Main scraper for gov.br sites
   - [ebc_webscraper.py](src/scraper/ebc_webscraper.py) - Specialized scraper for EBC (Empresa Brasil de Comunicação)
   - [scrape_manager.py](src/scraper/scrape_manager.py) - Orchestrates scraping operations
   - [ebc_scrape_manager.py](src/scraper/ebc_scrape_manager.py) - EBC-specific orchestration

2. **Data Management** ([src/](src/))
   - [dataset_manager.py](src/dataset_manager.py) - Handles Hugging Face dataset operations (insert, update, merge)
   - [cogfy_manager.py](src/cogfy_manager.py) - Manages Cogfy collection API interactions

3. **Content Enrichment** ([src/enrichment/](src/enrichment/))
   - [augmentation_manager.py](src/enrichment/augmentation_manager.py) - Manages AI-powered enrichment
   - [classifier_summarizer.py](src/enrichment/classifier_summarizer.py) - LLM-based classification and summarization

4. **Search Infrastructure** ([docker-typesense/](docker-typesense/))
   - [init-typesense.py](docker-typesense/init-typesense.py) - Initializes Typesense collections and schemas
   - [run-typesense-server.sh](docker-typesense/run-typesense-server.sh) - Server launch script
   - [web-ui/](docker-typesense/web-ui/) - Search interface

5. **Pipeline Scripts** (used by GitHub Actions)
   - [upload_to_cogfy_manager.py](src/upload_to_cogfy_manager.py) - Uploads scraped news to Cogfy collection
   - [theme_enrichment_manager.py](src/theme_enrichment_manager.py) - Enriches dataset with theme data from Cogfy

6. **Main Entry Point**
   - [main.py](src/main.py) - CLI interface with subcommands for scraping and augmentation

## Technology Stack

### Core Dependencies (from [pyproject.toml](pyproject.toml))

**Data Processing:**
- `pandas` - Data manipulation
- `datasets` - Hugging Face datasets library
- `beautifulsoup4` - HTML parsing

**AI/ML:**
- `langchain` + `langchain-community` + `langchain-openai` - LLM framework
- `openai` - OpenAI API client

**Web & APIs:**
- `requests` - HTTP client
- `retry` - Retry logic for API calls
- `algoliasearch` - Search integration

**Content Processing:**
- `markdown` + `markdownify` - Markdown conversion
- `reportlab` - PDF generation
- `scipy` - Scientific computing

**Development:**
- `pytest` - Testing framework
- `ipdb` - Debugging
- `notebook` + `ipykernel` - Jupyter notebooks
- `matplotlib` - Data visualization

## Data Schema

### Dataset Fields (from [dataset_manager.py](src/dataset_manager.py))

| Field | Type | Description |
|-------|------|-------------|
| `unique_id` | string | MD5 hash of agency + published_at + title |
| `agency` | string | Government agency that published the news |
| `published_at` | datetime | Publication date |
| `title` | string | News title |
| `url` | string | Original URL |
| `image` | string | Main image URL |
| `category` | string | News category (if available) |
| `tags` | list | Associated tags (if available) |
| `content` | string | Full content in Markdown |
| `extracted_at` | datetime | Extraction timestamp |
| `theme_1_level_1` | string | Full level 1 theme (e.g., "01 - Economia e Finanças") |
| `theme_1_level_1_code` | string | Level 1 theme code (e.g., "01") |
| `theme_1_level_1_label` | string | Level 1 theme label (e.g., "Economia e Finanças") |
| `theme_1_level_2_code` | string | Level 2 theme code (e.g., "01.01") derived from themes_tree.yaml |
| `theme_1_level_2_label` | string | Level 2 theme label (e.g., "Política Econômica") |
| `theme_1_level_3_code` | string | Level 3 theme code (e.g., "01.01.01") from Cogfy |
| `theme_1_level_3_label` | string | Level 3 theme label (e.g., "Política Fiscal") |
| `most_specific_theme_code` | string | Most specific theme code available (level 3 if exists, otherwise level 1) |
| `most_specific_theme_label` | string | Most specific theme label available |

### Theme Hierarchy

The dataset uses a 3-level theme taxonomy defined in [themes_tree.yaml](src/enrichment/themes_tree.yaml):

- **Level 1**: Broad categories (e.g., "01 - Economia e Finanças")
- **Level 2**: Subcategories (e.g., "01.01 - Política Econômica")
- **Level 3**: Specific topics (e.g., "01.01.01 - Política Fiscal")

**How themes are assigned:**

1. **theme_1_level_1** and **theme_1_level_3** are fetched from Cogfy (AI-classified)
2. **theme_1_level_2** is derived from themes_tree.yaml **only when level 3 exists**:
   - Extract first 5 characters from level 3 code (e.g., "01.01.01" → "01.01")
   - Lookup full label in themes_tree.yaml
   - If level 3 doesn't exist, level 2 remains None
3. **most_specific_theme** contains the most granular theme available:
   - If level 3 exists, use level 3
   - Otherwise, use level 1

**Example:**
- News with level 3: `most_specific_theme_code = "01.01.01"` (Política Fiscal)
- News without level 3: `most_specific_theme_code = "01"` (Economia e Finanças)

## CLI Commands

### Scraping Commands

#### Scrape Gov.BR Sites
```bash
poetry run python src/main.py scrape \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  [--agencies gestao,saude] \
  [--sequential] \
  [--allow-update]
```

**Arguments:**
- `--start-date` (required) - Start date (YYYY-MM-DD)
- `--end-date` (optional) - End date (YYYY-MM-DD)
- `--agencies` (optional) - Comma-separated agency list (e.g., 'gestao,saude')
- `--sequential` - Process agencies one at a time (default: parallel)
- `--allow-update` - Overwrite existing entries instead of skipping

#### Scrape EBC News
```bash
poetry run python src/main.py scrape-ebc \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  [--sequential] \
  [--allow-update]
```

### Content Enrichment

```bash
poetry run python src/main.py augment \
  [--start-date 2024-01-01] \
  [--end-date 2024-12-31] \
  [--agencies gestao,saude] \
  [--openai_api_key YOUR_KEY]
```

**What it does:**
- Classifies news articles using LLMs
- Adds semantic enrichment to content
- Updates existing dataset with new fields

## Development Workflow

### Setup

1. **Install Dependencies:**
```bash
poetry install
```

2. **Authenticate with Hugging Face:**
```bash
huggingface-cli login
```

3. **Configure Environment Variables:**
Create a `.env` file:
```
OPENAI_API_KEY=your_key_here
HF_TOKEN=your_hf_token
```

### Running Tests

```bash
poetry run pytest
```

### Docker Deployment

```bash
docker build -t govbrnews .
docker run govbrnews poetry run python src/main.py --help
```

### Typesense Search Server

```bash
cd docker-typesense
./run-typesense-server.sh
```

Then initialize collections:
```bash
python init-typesense.py
```

## Key Workflows

### 1. Scraping Workflow ([scrape_manager.py:59-121](src/scraper/scrape_manager.py#L59-L121))

```
Load URLs from YAML → Initialize WebScrapers →
Scrape News (parallel/sequential) → Preprocess Data →
Generate unique_id → Upload to Hugging Face
```

**Unique ID Generation** ([scrape_manager.py:166-183](src/scraper/scrape_manager.py#L166-L183)):
```python
MD5(f"{agency}_{published_at}_{title}")
```

### 2. Dataset Management Workflow ([dataset_manager.py:38-63](src/dataset_manager.py#L38-L63))

```
Load Existing Dataset → Merge New Data →
Handle Duplicates (skip or update) → Sort by Agency/Date →
Push to Hub → Generate CSVs
```

**Duplicate Handling:**
- Default: Skip duplicates based on `unique_id`
- With `--allow-update`: Overwrite existing entries

### 3. Content Enrichment Workflow ([augmentation_manager.py](src/enrichment/augmentation_manager.py))

```
Fetch Dataset → Filter by Date/Agency →
Classify with LLM → Update Dataset
```

## Important Code Patterns

### 1. Retry Logic for API Calls

From [dataset_manager.py:317-334](src/dataset_manager.py#L317-L334):
```python
@retry(
    exceptions=requests.exceptions.RequestException,
    tries=5,
    delay=2,
    backoff=3,
    jitter=(1, 3),
)
def _upload_file(self, path_or_fileobj, path_in_repo, repo_id):
    self.api.upload_file(...)
```

### 2. DataFrame/Dataset Conversion Pattern

The codebase uses a consistent pattern of converting between Hugging Face Datasets and pandas DataFrames:

```python
# HF Dataset → pandas DataFrame
df = dataset.to_pandas()

# pandas DataFrame → HF Dataset
dataset = Dataset.from_pandas(df, preserve_index=False)
```

### 3. Duplicate Detection

From [scrape_manager.py:166-183](src/scraper/scrape_manager.py#L166-L183):
```python
def _generate_unique_id(self, agency: str, published_at_value: str, title: str) -> str:
    date_str = (
        published_at_value.isoformat()
        if isinstance(published_at_value, date)
        else str(published_at_value)
    )
    hash_input = f"{agency}_{date_str}_{title}".encode("utf-8")
    return hashlib.md5(hash_input).hexdigest()
```

## Configuration Files

### Agency URLs Configuration
URLs are stored in [src/scraper/site_urls.yaml](src/scraper/site_urls.yaml):
```yaml
agencies:
  gestao: "https://www.gov.br/gestao/pt-br/assuntos/noticias"
  saude: "https://www.gov.br/saude/pt-br/assuntos/noticias"
  # ... more agencies
```

## Data Publishing

### Hugging Face Hub
- Main dataset: `nitaibezerra/govbrnews`
- Reduced dataset: `nitaibezerra/govbrnews-reduced` (only: published_at, agency, title, url)

### CSV Exports
Generated automatically on dataset push:
- Global CSV: `govbr_news_dataset.csv`
- By agency: `agencies/{agency}_news_dataset.csv`
- By year: `years/{year}_news_dataset.csv`

## Troubleshooting

### Common Issues

1. **Hugging Face Authentication Error:**
   - Run `huggingface-cli login`
   - Verify token in `~/.huggingface/token`

2. **Duplicate Detection Issues:**
   - Check if `unique_id` is properly generated
   - Verify agency name consistency
   - Check date format consistency

3. **Scraping Failures:**
   - Verify site URL is still valid
   - Check if site structure has changed
   - Review HTML parsing logic in [webscraper.py](src/scraper/webscraper.py)

## Git Commit Guidelines

**IMPORTANT:** When working with this project, do NOT add Claude Code attribution in commit messages. The standard Claude Code co-authorship footer should be omitted:

**Do NOT use:**
```
Commit message here.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Use instead:**
```
Commit message here.
```

This applies to all commits in the govbrnews repository, whether made directly or through automation.

## Best Practices

### When Modifying Scraping Logic

1. **Test with small date ranges first:**
```bash
poetry run python src/main.py scrape \
  --start-date 2024-01-01 \
  --end-date 2024-01-02 \
  --agencies gestao
```

2. **Use sequential mode for debugging:**
```bash
--sequential
```

3. **Preserve existing data:**
```bash
# Don't use --allow-update unless intentional
```

### When Adding New Features

1. **Check existing dataset structure:**
```python
from dataset_manager import DatasetManager
dm = DatasetManager()
dataset = dm._load_existing_dataset()
print(dataset.column_names)
```

2. **Add new columns via enrichment:**
   - New columns can be added through the `update()` method
   - See [dataset_manager.py:65-85](src/dataset_manager.py#L65-L85)

3. **Maintain backward compatibility:**
   - New columns should have default values (None)
   - Don't remove or rename existing columns

## Testing

### Unit Tests Location
[tests/](tests/)

### Integration Tests
Test scraping with real data:
```bash
poetry run python src/main.py scrape \
  --start-date $(date -d "yesterday" +%Y-%m-%d) \
  --end-date $(date -d "yesterday" +%Y-%m-%d) \
  --agencies gestao
```

### Typesense Tests
```bash
cd docker-typesense
python -m pytest test_init_typesense.py -v
```

## Monitoring and Logs

### Logging Configuration
From [main.py:14-16](src/main.py#L14-L16):
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
```

### Key Log Messages to Monitor
- "Existing dataset loaded" - Dataset fetch successful
- "Adding X new items" - New items being inserted
- "Skipping X duplicates" - Duplicate detection working
- "Dataset pushed to Hugging Face Hub" - Upload successful

## GitHub Actions

The project uses GitHub Actions for automated daily news processing ([.github/workflows/main-workflow.yaml](.github/workflows/main-workflow.yaml)). The complete pipeline runs daily at 4AM UTC (midnight Brasília) and consists of:

### Pipeline Stages

1. **setup-dates** - Determines date range to process
   - Automatic mode: Yesterday's news (1 day ago)
   - Manual dispatch: Custom date range via workflow inputs

2. **scraper** - Main gov.br news scraper
   - Container: `ghcr.io/nitaibezerra/govbrnews-scraper:latest`
   - Command: `python src/main.py scrape --start-date X --end-date Y`
   - Publishes to Hugging Face dataset

3. **ebc-scraper** - EBC news scraper
   - Runs after main scraper completes
   - Command: `python src/main.py scrape-ebc --start-date X --end-date Y --allow-update`
   - Updates dataset with EBC content

4. **upload-to-cogfy** - Upload to Cogfy knowledge system
   - Runs after both scrapers complete
   - Script: [upload_to_cogfy_manager.py](src/upload_to_cogfy_manager.py)
   - Requires: `COGFY_API_KEY` secret

5. **enrich-themes** - Enrich dataset with theme information
   - Waits 20 minutes after Cogfy upload (allows processing time for vector embeddings and indexing)
   - Script: [theme_enrichment_manager.py](src/theme_enrichment_manager.py)
   - Fetches theme_1_level_1 and theme_1_level_3 from Cogfy
   - Derives theme_1_level_2 from [themes_tree.yaml](src/enrichment/themes_tree.yaml)
   - Determines most specific theme (level 3 if available, otherwise level 1)
   - Writes all theme data back to Hugging Face dataset

6. **pipeline-summary** - Summary and status check
   - Runs always (even if previous steps fail)
   - Reports status of all pipeline stages
   - Exits with error if any stage failed

### Workflow Visualization

```
setup-dates
    ↓
scraper ──────────────┐
    ↓                 │
ebc-scraper          │
    ↓                 │
upload-to-cogfy      │
    ↓                 │
enrich-themes        │
    ↓                 │
pipeline-summary ←────┘
```

### Required Secrets

- `HF_TOKEN` - Hugging Face authentication token
- `COGFY_API_KEY` - Cogfy API key for uploads and grouping

### Manual Workflow Dispatch

You can trigger the workflow manually with custom dates:
```yaml
inputs:
  start_date: "2024-01-01"  # Optional, defaults to yesterday
  end_date: "2024-01-31"     # Optional, defaults to start_date
```

## Related Projects

### Cogfy Integration
The [cogfy_manager.py](src/cogfy_manager.py) module provides integration with Cogfy (internal knowledge management system):
- `CogfyClient` - API client for Cogfy
- `CollectionManager` - High-level collection operations

## Additional Resources

- **Dataset Dashboard:** https://huggingface.co/spaces/nitaibezerra/govbrnews
- **Dataset Repository:** https://huggingface.co/datasets/nitaibezerra/govbrnews
- **Main README:** [README.md](README.md)

## Quick Reference

### File Size
- Use `govbrnews-reduced` for faster downloads (4 columns only)
- Use `govbrnews` for full dataset

### Date Format
Always use ISO format: `YYYY-MM-DD`

### Agency Names
Match exactly with keys in `site_urls.yaml`

### Environment Variables
```bash
OPENAI_API_KEY       # For LLM enrichment
HF_TOKEN            # Hugging Face authentication (or use huggingface-cli login)
COGFY_API_KEY       # For Cogfy integration (optional)
COGFY_BASE_URL      # Cogfy server URL (optional)
```

## Contact & Support

For issues, contributions, or questions:
- Open an issue on GitHub
- Contact: Ministério da Gestão e Inovação (MGI)

---

**Last Updated:** October 2024
**Python Version:** 3.12+
**License:** See repository for licensing information
