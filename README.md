# Sitemap Page-Weight Auditor

A CLI tool that parses an XML sitemap, groups URLs into page templates, crawls sample pages, and reports the heaviest inline HTML elements. This tool is designed to help you identify heavy fragments of code, large embedded data (like base64 images or inline JSON), and excessive DOM elements that are bloating your HTML payload size.

## Features

- **Sitemap Parsing**: Automatically fetches and extracts URLs from a standard XML sitemap (supports sitemap indexes).
- **Smart Path-Shape Grouping**: Intelligently groups similar URLs into templates based on path shape (e.g., `/{slug}`) instead of flat folders, ensuring a representative sample of complex or completely flat architectures.
- **Concurrent Crawling**: Multi-threaded fetching drastically reduces processing time for large sitemaps.
- **Deep HTML Analysis**: Scans pages for large, non-visible inline elements (like scripts, styles, SVG, hidden inputs, massive `<noscript>` blocks, and excessive inline `style="..."` attributes).
- **Comprehensive Reporting**: Generates both JSON and Excel (.xlsx) reports with rich formatting.
- **Rich Terminal UI**: Provides real-time progress bars, loading spinners, and beautifully formatted finding summaries right in your terminal.
- **Local Caching**: Saves crawled pages locally to avoid hitting the server repeatedly during testing.

## Prerequisites

- Python 3.9+
- The dependencies listed in `requirements.txt`.

## Getting Started

1. **Clone the repository** (if you haven't already) and navigate to the project directory:
   ```bash
   cd html_size_reviewer
   ```

2. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the auditor**:
   The simplest way to use the tool is to provide a sitemap URL:
   ```bash
   python main.py https://example.com/sitemap.xml
   ```

## Usage

```bash
python main.py <sitemap-url> [OPTIONS]
```

### Options

| Argument | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `sitemap_url` | | URL of the XML sitemap to analyze. | **Required** |
| `--output` | `-o` | Path for the JSON report output. | `report.json` |
| `--excel` | `-e` | Path for the Excel report output. | `<output_name>.xlsx` |
| `--samples` | `-s` | Number of sample URLs per template (range: 1-10). | `3` |
| `--workers` | `-w` | Number of concurrent workers for faster crawling. | `3` |
| `--cache-dir` | | Directory to cache crawled HTML files. | `crawled_pages` |
| `--delay` | | Delay in seconds between HTTP requests (per worker) to avoid rate-limiting. | `1.0` |
| `--no-secondary` | | Hide secondary findings (external resources) from output. | `False` |

### Examples

**Basic run with default settings:**
```bash
python main.py https://example.com/sitemap.xml
```

**Fast concurrent run with custom sampling and JSON output path:**
```bash
python main.py https://example.com/sitemap.xml --workers 5 --samples 2 --output audit_v1.json
```

**Generate reports while suppressing secondary (external) findings:**
```bash
python main.py https://example.com/sitemap.xml --no-secondary
```

## Running Tests

This project uses `pytest` for unit testing. To run the tests, simply execute:

```bash
pytest
```
