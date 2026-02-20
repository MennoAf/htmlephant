"""Sitemap parser and template identifier.

Fetches XML sitemaps (including sitemap indexes), extracts URLs,
groups them by page template (first path segment), and selects
sample URLs for analysis.
"""

import random
import re
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

# Default HTTP headers for sitemap fetching.
DEFAULT_HEADERS = {
    "User-Agent": (
        "HTMLephant/1.0 "
        "(+https://github.com/htmlephant)"
    ),
    "Accept": "application/xml, text/xml, */*",
}

# Maximum number of child sitemaps to follow from a sitemap index.
MAX_CHILD_SITEMAPS = 50


def fetch_sitemap_xml(
    url: str,
    timeout: int = 30,
    headers: Optional[dict] = None,
) -> str:
    """Fetch raw XML content from a sitemap URL.

    Args:
        url: The URL of the sitemap.
        timeout: Request timeout in seconds.
        headers: Optional custom HTTP headers.

    Returns:
        The raw XML string.

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


def extract_urls_from_xml(xml_content: str) -> list[str]:
    """Extract all <loc> URLs from a single sitemap XML document.

    Args:
        xml_content: Raw XML string of a sitemap.

    Returns:
        A list of URL strings found in <loc> elements.
    """
    soup = BeautifulSoup(xml_content, "lxml-xml")
    return [loc.get_text(strip=True) for loc in soup.find_all("loc")]


def is_sitemap_index(xml_content: str) -> bool:
    """Check whether XML content is a sitemap index.

    Args:
        xml_content: Raw XML string.

    Returns:
        True if this is a <sitemapindex> document.
    """
    soup = BeautifulSoup(xml_content, "lxml-xml")
    return soup.find("sitemapindex") is not None


def fetch_all_urls(sitemap_url: str, console=None) -> list[str]:
    """Fetch all page URLs from a sitemap, handling sitemap indexes.

    If the sitemap is a sitemap index, recursively fetches child
    sitemaps up to MAX_CHILD_SITEMAPS.

    Args:
        sitemap_url: The root sitemap URL to fetch.
        console: Optional rich.console.Console for status messages.

    Returns:
        A deduplicated list of all page URLs found.
    """
    if console:
        console.print(f"[cyan]Fetching sitemap:[/] {sitemap_url}")

    xml_content = fetch_sitemap_xml(sitemap_url)

    if is_sitemap_index(xml_content):
        child_urls = extract_urls_from_xml(xml_content)
        if console:
            console.print(
                f"[yellow]Sitemap index found with "
                f"{len(child_urls)} child sitemaps[/]"
            )

        all_page_urls = []
        urls_to_fetch = child_urls[:MAX_CHILD_SITEMAPS]
        
        if console and urls_to_fetch:
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
                task_id = progress.add_task("[cyan]Fetching child sitemaps...", total=len(urls_to_fetch))
                for child_url in urls_to_fetch:
                    short_url = child_url if len(child_url) < 40 else f"...{child_url[-37:]}"
                    progress.update(task_id, description=f"[cyan]Fetching child [dim]{short_url}[/]")
                    
                    try:
                        child_xml = fetch_sitemap_xml(child_url)
                        all_page_urls.extend(extract_urls_from_xml(child_xml))
                    except requests.RequestException as exc:
                        console.print(f"  [red]Failed to fetch {child_url}: {exc}[/]")
                    progress.update(task_id, advance=1)
        else:
            for child_url in urls_to_fetch:
                try:
                    child_xml = fetch_sitemap_xml(child_url)
                    all_page_urls.extend(extract_urls_from_xml(child_xml))
                except requests.RequestException:
                    pass

        return list(dict.fromkeys(all_page_urls))  # deduplicate, keep order
    else:
        urls = extract_urls_from_xml(xml_content)
        if console:
            console.print(f"[green]Found {len(urls)} URLs in sitemap[/]")
        return urls


def get_template_key(url: str) -> str:
    """Extract a template fingerprint from a URL's path shape.

    Instead of just taking the first folder, we analyze the entire path.
    - Numbers -> {id}
    - Long strings with hyphens/underscores -> {slug}
    - Literal names -> keep as is

    Args:
        url: A full URL string.

    Returns:
        The template fingerprint (e.g. "/products/{slug}", "/{slug}").
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        return "homepage"

    segments = path.split("/")
    fingerprint_parts = []

    for segment in segments:
        # Check if it has an extension (like .html)
        if "." in segment:
            name, ext = segment.rsplit(".", 1)
        else:
            name = segment
            ext = ""

        # Remove trailing slashes and common noise
        name = name.lower()

        if re.search(r'\d+', name):
            # If the segment contains numbers, treat it as an ID or dynamic slug
            part = "{id}"
        elif "-" in name or "_" in name or len(name) > 20:
            # If it has hyphens/underscores or is very long, it's a slug
            part = "{slug}"
        else:
            # Otherwise, keep the literal folder name
            part = name

        if ext:
            part = f"{part}.{ext}"
            
        fingerprint_parts.append(part)

    return "/" + "/".join(fingerprint_parts)


def group_urls_by_template(urls: list[str]) -> dict[str, list[str]]:
    """Group URLs into template buckets by first path segment.

    Args:
        urls: A list of full URL strings.

    Returns:
        A dict mapping template key -> list of URLs.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for url in urls:
        key = get_template_key(url)
        groups[key].append(url)
    return dict(groups)


def select_sample_urls(
    template_groups: dict[str, list[str]],
    samples_per_template: int = 3,
    base_url: Optional[str] = None,
) -> dict[str, list[str]]:
    """Select sample URLs from each template group.

    For the "homepage" template, always includes the root URL.
    For other templates, randomly selects up to samples_per_template URLs.

    Args:
        template_groups: Dict mapping template key -> list of URLs.
        samples_per_template: Max URLs to sample per template.
        base_url: Optional base URL (scheme + domain) for ensuring
            the homepage root is included.

    Returns:
        A dict mapping template key -> list of selected sample URLs.
    """
    samples: dict[str, list[str]] = {}

    for template, urls in template_groups.items():
        if template == "homepage":
            # Always include the root URL
            selected = []
            root_url = None

            # Find the root URL (shortest path or exact root)
            for url in urls:
                parsed = urlparse(url)
                if not parsed.path.strip("/"):
                    root_url = url
                    break

            # If no explicit root found but we have a base_url, add it
            if root_url is None and base_url:
                root_url = base_url.rstrip("/") + "/"

            if root_url:
                selected.append(root_url)

            # Add more pages from this group if available
            remaining = [u for u in urls if u != root_url]
            extra_needed = samples_per_template - len(selected)
            if extra_needed > 0 and remaining:
                selected.extend(
                    random.sample(
                        remaining, min(extra_needed, len(remaining))
                    )
                )
            samples[template] = selected
        else:
            count = min(samples_per_template, len(urls))
            samples[template] = random.sample(urls, count)

    return samples
