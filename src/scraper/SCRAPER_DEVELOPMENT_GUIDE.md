# Scraper Development Guide for GovBR News

## Overview

This document provides a comprehensive technical guide for developing new news scrapers for the GovBR News pipeline. It follows the patterns established by the EBC scraper implementation and is designed as context for AI-assisted development.

## Architecture Pattern

The GovBR News scraper architecture follows a consistent pattern:

```
WebScraper (Core Logic) → ScrapeManager (Integration) → main.py (CLI) → GitHub Workflow
```

### Core Components Required

1. **`{source}_webscraper.py`** - Core scraping logic
2. **`{source}_scrape_manager.py`** - Integration with dataset infrastructure
3. **Update `main.py`** - Add CLI subcommand
4. **Update GitHub Workflow** - Add to daily pipeline

## Step-by-Step Implementation Guide

### Phase 1: Core WebScraper Class

Create `src/scraper/{source}_webscraper.py` with the following structure:

```python
import logging
import random
import re
import time
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from retry import retry

class {Source}WebScraper:
    def __init__(self, min_date: str, max_date: Optional[str] = None):
        """
        Initialize the scraper with date filters.
        
        :param min_date: Minimum date for scraping (YYYY-MM-DD)
        :param max_date: Maximum date for scraping (YYYY-MM-DD)
        """
        self.base_url = "TARGET_SITE_URL"
        self.min_date = datetime.strptime(min_date, "%Y-%m-%d").date()
        self.max_date = datetime.strptime(max_date, "%Y-%m-%d").date() if max_date else None
        self.news_data = []
        self.agency = "source_name"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def scrape_news(self) -> List[Dict[str, str]]:
        """Main scraping entry point with pagination logic"""
        
    def scrape_index_page(self, url: str) -> List[str]:
        """Extract news URLs from index/listing pages"""
        
    def scrape_news_page(self, url: str) -> Dict[str, str]:
        """Extract article content from individual news pages"""
        
    @retry(exceptions=requests.exceptions.RequestException, tries=5, delay=2, backoff=3)
    def fetch_page(self, url: str) -> Optional[requests.Response]:
        """Robust page fetching with retry logic"""
        
    def parse_date(self, date_str: str) -> Optional[date]:
        """Parse date strings from target site format"""
```

#### Key Implementation Requirements:

1. **Date Filtering**: Must support `min_date` and `max_date` filtering
2. **Rate Limiting**: Implement respectful delays between requests
3. **Error Handling**: Use retry decorators for network requests
4. **Content Extraction**: Handle various HTML structures with fallbacks
5. **Data Format**: Return structured data compatible with govbrnews schema

#### Required Data Fields:

```python
{
    'title': str,           # Article headline
    'url': str,             # Source URL
    'source': str,          # Author/source information
    'date': str,            # Publication date
    'content': str,         # Full article content
    'image': str,           # Main image URL (optional)
    'error': str,           # Error message if scraping failed
}
```

### Phase 2: Integration Manager

Create `src/scraper/{source}_scrape_manager.py`:

```python
import hashlib
import logging
from collections import OrderedDict
from datetime import date, datetime
from typing import Dict, List

from dataset_manager import DatasetManager
from scraper.{source}_webscraper import {Source}WebScraper

class {Source}ScrapeManager:
    def __init__(self, dataset_manager: DatasetManager):
        self.dataset_manager = dataset_manager

    def run_scraper(self, min_date: str, max_date: str, sequential: bool, allow_update: bool = False):
        """Execute scraping and upload to dataset"""
        
    def _convert_to_govbr_format(self, source_data: List[Dict]) -> List[Dict]:
        """Convert source data format to govbrnews schema"""
        
    def _preprocess_data(self, data: List[Dict]) -> OrderedDict:
        """Add unique IDs and reorder columns"""
        
    def _generate_unique_id(self, agency: str, published_at, title: str) -> str:
        """Generate MD5 hash for deduplication"""
```

#### Data Format Conversion:

The manager must convert source-specific data to the govbrnews schema:

```python
converted_item = {
    "title": item.get("title", "").strip(),
    "url": item.get("url", "").strip(),
    "published_at": self._parse_date(item.get("date", "")),
    "category": self._extract_category(item),  # Map to govbr categories
    "tags": self._extract_tags(item),          # Extract or generate tags
    "content": item.get("content", "").strip(),
    "image": item.get("image", "").strip(),
    "agency": "source_name",                   # Consistent agency identifier
    "extracted_at": datetime.now(),
}
```

### Phase 3: CLI Integration

Update `src/main.py` to add the new scraper:

1. **Add import**:
```python
from scraper.{source}_scrape_manager import {Source}ScrapeManager
```

2. **Add function**:
```python
def run_{source}_scraper(args):
    """Execute {source} scraper logic"""
    dataset_manager = DatasetManager()
    scrape_manager = {Source}ScrapeManager(dataset_manager)
    scrape_manager.run_scraper(
        args.start_date, args.end_date, args.sequential, args.allow_update
    )
```

3. **Add subparser**:
```python
{source}_parser = subparsers.add_parser(
    "scrape-{source}", help="Scrape {source} news data"
)
{source}_parser.add_argument("--start-date", required=True)
{source}_parser.add_argument("--end-date")
{source}_parser.add_argument("--sequential", action="store_true")
{source}_parser.add_argument("--allow-update", action="store_true")
```

4. **Add dispatch logic**:
```python
elif args.command == "scrape-{source}":
    run_{source}_scraper(args)
```

### Phase 4: GitHub Workflow Integration

Update `.github/workflows/main-workflow.yaml`:

1. **Add scraper job**:
```yaml
{source}-scraper:
  name: {Source} News Scraper
  runs-on: ubuntu-latest
  needs: [setup-dates, scraper]  # Run after gov.br scraper
  container:
    image: ghcr.io/nitaibezerra/govbrnews-scraper:latest
    options: --workdir /app
  steps:
    - name: Run {source} news scraper
      env:
        HF_TOKEN: ${{ secrets.HF_TOKEN }}
      run: |
        echo "Starting {source} scraper for ${{ needs.setup-dates.outputs.start_date }} to ${{ needs.setup-dates.outputs.end_date }}"
        cd /app
        python src/main.py scrape-{source} \
          --start-date ${{ needs.setup-dates.outputs.start_date }} \
          --end-date ${{ needs.setup-dates.outputs.end_date }} \
          --allow-update
        echo "{Source} scraper completed successfully"
```

2. **Update dependencies**:
```yaml
upload-to-cogfy:
  needs: [setup-dates, scraper, ebc-scraper, {source}-scraper]

pipeline-summary:
  needs: [setup-dates, scraper, ebc-scraper, {source}-scraper, upload-to-cogfy, group-news, enrich-themes]
```

3. **Update status reporting**:
```yaml
echo "{Source} Scraper status: ${{ needs.{source}-scraper.result }}"

if [ "${{ needs.scraper.result }}" = "success" ] && \
   [ "${{ needs.ebc-scraper.result }}" = "success" ] && \
   [ "${{ needs.{source}-scraper.result }}" = "success" ] && \
   ...
```

## Technical Implementation Notes

### HTML Parsing Strategies

Most Brazilian news sites follow common patterns. Implement multiple fallback strategies:

```python
def extract_title(self, soup: BeautifulSoup) -> str:
    """Extract title with multiple fallbacks"""
    # Primary strategy
    title = soup.find('h1', class_='title')
    if title:
        return title.get_text(strip=True)
    
    # Fallback strategies
    title = soup.find('h1')
    if title:
        return title.get_text(strip=True)
    
    # Meta tag fallback
    meta_title = soup.find('meta', property='og:title')
    if meta_title:
        return meta_title.get('content', '').strip()
    
    return "No Title"
```

### Date Parsing

Brazilian sites commonly use DD/MM/YYYY format:

```python
def parse_date(self, date_str: str) -> Optional[date]:
    """Parse Brazilian date formats"""
    formats = [
        "%d/%m/%Y",
        "%d/%m/%Y - %H:%M",
        "%d de %B de %Y",  # "16 de setembro de 2025"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None
```

### Rate Limiting

Implement respectful rate limiting:

```python
import time
import random

def smart_sleep(self, min_val=1.0, max_val=2.0):
    """Random sleep between requests"""
    sleep_time = random.uniform(min_val, max_val)
    time.sleep(sleep_time)
```

### Content Cleaning

Clean extracted content for better quality:

```python
def clean_content(self, content: str) -> str:
    """Clean and normalize content"""
    # Remove excessive whitespace
    content = re.sub(r'\n\s*\n', '\n\n', content)
    
    # Remove tracking pixels and ads
    content = re.sub(r'\*Com informações.*', '', content)
    content = re.sub(r'Tags:.*', '', content)
    
    return content.strip()
```

## Testing Strategy

### Local Testing

```bash
# Test with single day
poetry run python src/main.py scrape-{source} --start-date 2025-09-16

# Test with date range
poetry run python src/main.py scrape-{source} --start-date 2025-09-15 --end-date 2025-09-16 --allow-update
```

### Expected Test Results

- **Articles Found**: 20-100+ articles per day (varies by source)
- **Success Rate**: >95% successful content extraction
- **Data Quality**: All required fields populated
- **Upload Success**: Successful HuggingFace dataset integration

## Dependencies

Add any required dependencies to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
# Common scraping dependencies are already included:
# requests, beautifulsoup4, retry, markdownify, pandas
# Add source-specific dependencies as needed
```

## Quality Checklist

Before considering implementation complete:

- [ ] **Scraper Class**: Core scraping logic implemented with error handling
- [ ] **Manager Class**: Data conversion and dataset integration
- [ ] **CLI Integration**: Subcommand added to main.py
- [ ] **Workflow Integration**: Added to GitHub Actions pipeline
- [ ] **Testing**: Successfully tested with real data
- [ ] **Documentation**: Code properly documented
- [ ] **Linting**: No linting errors
- [ ] **Rate Limiting**: Respectful request timing implemented
- [ ] **Error Handling**: Robust retry logic and graceful failures

## Common Pitfalls to Avoid

1. **Insufficient Error Handling**: Always use retry decorators and handle network failures gracefully
2. **Aggressive Rate Limiting**: Respect target site servers with appropriate delays
3. **Hardcoded Selectors**: Use multiple fallback strategies for HTML parsing
4. **Date Format Assumptions**: Brazilian sites use various date formats
5. **Missing Content Cleaning**: Remove ads, tracking pixels, and irrelevant content
6. **Incomplete Testing**: Test with various date ranges and edge cases
7. **Workflow Dependencies**: Ensure proper job dependencies in GitHub Actions

## Example Implementation Reference

See the EBC scraper implementation for a complete working example:

- `src/scraper/ebc_webscraper.py` - Core scraping logic
- `src/scraper/ebc_scrape_manager.py` - Integration manager
- Commits `235a2d7` and `5e6e0fd` for implementation details

## AI Development Context

When using this guide for AI-assisted development:

1. **Understand the target site structure** by analyzing HTML and network requests
2. **Follow the established patterns** for consistency with existing codebase
3. **Test incrementally** - implement core scraper first, then integration layers
4. **Use existing utilities** like retry decorators and date parsing functions
5. **Validate data quality** by checking extracted content matches expectations
6. **Consider edge cases** like missing images, malformed dates, or network failures

This guide ensures consistent, maintainable, and robust scraper implementations that integrate seamlessly with the existing GovBR News infrastructure.
