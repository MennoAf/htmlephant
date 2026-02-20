"""HTML page crawler.

Fetches raw HTML for selected URLs and optionally caches them
to a local directory for inspection.
"""

import concurrent.futures
import os
import re
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

# Default HTTP headers mimicking a real browser.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 "
        "HTMLephant/1.0"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Delay between requests in seconds (be polite).
DEFAULT_DELAY = 1.0


def _sanitize_filename(url: str) -> str:
    """Convert a URL into a safe filename for caching.

    Args:
        url: The full URL string.

    Returns:
        A filesystem-safe filename derived from the URL.
    """
    parsed = urlparse(url)
    path_part = parsed.path.strip("/").replace("/", "_") or "index"
    # Remove non-alphanumeric characters except underscores and hyphens
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", path_part)
    return f"{safe_name}.html"


def fetch_page_html(
    url: str,
    timeout: int = 30,
    headers: Optional[dict] = None,
) -> str:
    """Fetch the raw HTML content of a single page.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.
        headers: Optional custom HTTP headers.

    Returns:
        The raw HTML string.

    Raises:
        requests.HTTPError: If the response status is not 2xx.
    """
    resp = requests.get(
        url,
        headers=headers or DEFAULT_HEADERS,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text


def crawl_pages(
    sample_urls: dict[str, list[str]],
    cache_dir: str = "crawled_pages",
    delay: float = DEFAULT_DELAY,
    max_workers: int = 3,
    console=None,
) -> dict[str, dict[str, str]]:
    """Crawl all sample URLs concurrently and return their HTML content.

    Args:
        sample_urls: Dict mapping template key -> list of URLs.
        cache_dir: Directory to save cached HTML files.
        delay: Seconds to wait between requests (per thread).
        max_workers: Number of concurrent threads to use.
        console: Optional rich.console.Console for status messages.

    Returns:
        A dict mapping template key -> {url: html_content}.
    """
    os.makedirs(cache_dir, exist_ok=True)
    results: dict[str, dict[str, str]] = {
        template: {} for template in sample_urls
    }
    
    total_urls = sum(len(urls) for urls in sample_urls.values())
    if total_urls == 0:
        return results

    # Flatten the tasks so we can process them concurrently
    tasks = []
    for template, urls in sample_urls.items():
        for url in urls:
            tasks.append((template, url))

    # Helper function for one url
    def _process_url(template: str, url: str) -> tuple[str, str, str, str]:
        """Returns (template, url, html, status_msg)"""
        # Sanitize template name so it doesn't cause os.path.join to jump to root
        safe_template = re.sub(r"[^a-zA-Z0-9_\-]", "_", template.strip("/")) or "root"
        filename = _sanitize_filename(url)
        cache_path = os.path.join(cache_dir, f"{safe_template}_{filename}")

        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as fh:
                html = fh.read()
            return template, url, html, "cached"

        try:
            html = fetch_page_html(url)
            with open(cache_path, "w", encoding="utf-8") as fh:
                fh.write(html)
            
            # Polite delay between requests on this thread
            time.sleep(delay)
            return template, url, html, "fetched"
        except requests.RequestException as exc:
            return template, url, "", f"error: {exc}"

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )
    
    with progress:
        task_id = progress.add_task("[cyan]Crawling pages...", total=total_urls)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(_process_url, t, u): (t, u)
                for (t, u) in tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_url):
                template, url = future_to_url[future]
                try:
                    tmpl, u, html, status = future.result()
                    results[tmpl][u] = html
                    
                    # Update progress description with the latest processed URL
                    # but keep it brief to avoid terminal spam
                    short_url = url if len(url) < 40 else f"...{url[-37:]}"
                    color = "green" if status == "fetched" else ("dim" if status == "cached" else "red")
                    
                    if console and status.startswith("error"):
                        console.print(f"  [red]Failed:[/] {url} ({status})")
                        
                    progress.update(task_id, advance=1, description=f"[cyan]Crawling pages... [{color}]{short_url}[/]")
                except Exception as exc:
                    results[template][url] = ""
                    if console:
                        console.print(f"  [red]Error processing {url}: {exc}[/]")
                    progress.update(task_id, advance=1)

    return results
