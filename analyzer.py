"""HTML weight analyzer.

Parses HTML documents to identify the heaviest elements contributing
to the overall file size. Primary focus is on inline content that
bloats the HTML document itself (inline scripts, styles, SVGs,
base64 data URIs, JSON-LD blocks, and large DOM subtrees).
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Comment, Tag

from classifiers import (
    classify_data_uri,
    classify_external_resource,
    classify_inline_content,
    classify_json_ld,
    classify_svg,
    get_element_identifier,
)

# Minimum size in bytes to flag an element as "heavy".
MIN_INLINE_SCRIPT_BYTES = 500
MIN_INLINE_STYLE_BYTES = 500
MIN_SVG_BYTES = 1000
MIN_DATA_URI_BYTES = 500
MIN_JSON_LD_BYTES = 500
MIN_DOM_SUBTREE_DESCENDANTS = 100

# Regex for finding data URIs in attribute values.
DATA_URI_RE = re.compile(r'data:[^"\')\s]+', re.I)


@dataclass
class Finding:
    """A single heavy-element finding from page analysis."""

    element_type: str
    element_identifier: str
    description: str
    visibility: str  # "user-visible" or "backend"
    size_bytes: int
    percent_of_page: float
    priority: str  # "primary" or "secondary"
    pages_found_on: list[str] = field(default_factory=list)
    scope: str = "page-specific"  # "site-wide", "template-wide", etc.
    searchable_snippet: str = ""
    is_subcomponent: bool = False

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            "element_type": self.element_type,
            "element_identifier": self.element_identifier,
            "description": self.description,
            "visibility": self.visibility,
            "size_bytes": self.size_bytes,
            "percent_of_page": round(self.percent_of_page, 2),
            "priority": self.priority,
            "pages_found_on": self.pages_found_on,
            "scope": self.scope,
            "searchable_snippet": self.searchable_snippet,
        }

def _extract_snippet(item, max_length=150) -> str:
    """Extract a searchable snippet from a Tag, Comment, or string."""
    text = str(item)
    # Remove newlines and collapse spaces for a cleaner JSON snippet
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


@dataclass
class PageAnalysis:
    """Complete analysis results for a single page."""

    url: str
    total_html_bytes: int
    findings: list[Finding] = field(default_factory=list)

    @property
    def total_flagged_bytes(self) -> int:
        """Sum of all finding sizes."""
        return sum(f.size_bytes for f in self.findings if not f.is_subcomponent)

    @property
    def flagged_percent(self) -> float:
        """Percentage of total HTML accounted for by findings."""
        if self.total_html_bytes == 0:
            return 0.0
        return (self.total_flagged_bytes / self.total_html_bytes) * 100

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            "url": self.url,
            "total_html_bytes": self.total_html_bytes,
            "total_html_kb": round(self.total_html_bytes / 1024, 1),
            "total_flagged_bytes": self.total_flagged_bytes,
            "flagged_percent": round(self.flagged_percent, 1),
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


def _element_byte_size(element: Tag) -> int:
    """Get the byte size of an element's serialized HTML."""
    return len(str(element).encode("utf-8"))


def _content_byte_size(text: str) -> int:
    """Get the byte size of a text string."""
    return len(text.encode("utf-8"))


def _analyze_json_bloat(
    json_data: dict,
    total_bytes: int,
    url: str,
    parent_identifier: str,
    min_node_bytes: int = 5000,
) -> list[Finding]:
    """Find the largest nodes within a JSON payload."""
    findings = []
    
    for key, value in json_data.items():
        try:
            node_str = json.dumps(value)
            node_size = len(node_str.encode("utf-8"))
            
            if node_size >= min_node_bytes:
                # Add finding for this node
                findings.append(Finding(
                    element_type="json-node",
                    element_identifier=f"{parent_identifier} -> [\"{key}\"]",
                    description=f"Large JSON node ('{key}') in script payload",
                    visibility="backend",
                    size_bytes=node_size,
                    percent_of_page=(node_size / total_bytes * 100) if total_bytes else 0,
                    priority="primary",
                    pages_found_on=[url],
                    searchable_snippet=f"\"{key}\": " + _extract_snippet(node_str, max_length=100),
                    is_subcomponent=True,
                ))
                
                # Recurse if children are also large dicts
                if isinstance(value, dict) and node_size >= min_node_bytes * 2:
                    findings.extend(_analyze_json_bloat(
                        value,
                        total_bytes,
                        url,
                        parent_identifier=f"{parent_identifier} -> [\"{key}\"]",
                        min_node_bytes=min_node_bytes
                    ))
        except (TypeError, ValueError):
            continue
            
    return findings


def _analyze_inline_scripts(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find and measure inline <script> tags (no src attribute).

    This covers regular inline scripts and JSON-LD / data blocks.
    """
    findings = []

    for script in soup.find_all("script"):
        src = script.get("src")
        if src:
            continue  # External script — handled separately

        content = script.get_text()
        if not content or not content.strip():
            continue

        size = _content_byte_size(content)
        script_type = script.get("type", "").lower()

        # JSON-LD structured data
        if "ld+json" in script_type or "json" in script_type:
            if size >= MIN_JSON_LD_BYTES:
                description, visibility = classify_json_ld(content)
                identifier = get_element_identifier(
                    "script",
                    type_attr=script.get("type"),
                    id_attr=script.get("id"),
                )
                findings.append(Finding(
                    element_type="json-ld",
                    element_identifier=identifier,
                    description=description,
                    visibility=visibility,
                    size_bytes=size,
                    percent_of_page=(size / total_bytes * 100)
                    if total_bytes
                    else 0,
                    priority="primary",
                    pages_found_on=[url],
                    searchable_snippet=_extract_snippet(script),
                ))

                # Also analyze the JSON for large internal nodes
                try:
                    json_data = json.loads(content)
                    if isinstance(json_data, dict):
                        findings.extend(_analyze_json_bloat(
                            json_data,
                            total_bytes,
                            url,
                            parent_identifier=identifier
                        ))
                except (json.JSONDecodeError, TypeError):
                    pass
        elif size >= MIN_INLINE_SCRIPT_BYTES:
            description, visibility = classify_inline_content(content)
            identifier = get_element_identifier(
                "script",
                type_attr=script.get("type"),
                id_attr=script.get("id"),
            )
            findings.append(Finding(
                element_type="inline-script",
                element_identifier=identifier,
                description=description,
                visibility=visibility,
                size_bytes=size,
                percent_of_page=(size / total_bytes * 100)
                if total_bytes
                else 0,
                priority="primary",
                pages_found_on=[url],
                searchable_snippet=_extract_snippet(script),
            ))

    return findings


def _analyze_inline_styles(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find and measure inline <style> tags."""
    findings = []

    for style in soup.find_all("style"):
        content = style.get_text()
        if not content or not content.strip():
            continue

        size = _content_byte_size(content)
        if size < MIN_INLINE_STYLE_BYTES:
            continue

        identifier = get_element_identifier(
            "style",
            id_attr=style.get("id"),
        )
        findings.append(Finding(
            element_type="inline-style",
            element_identifier=identifier,
            description="Inline CSS stylesheet",
            visibility="user-visible",
            size_bytes=size,
            percent_of_page=(size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="primary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(style),
        ))

    return findings


def _analyze_inline_svgs(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find and measure inline <svg> elements."""
    findings = []

    for svg in soup.find_all("svg"):
        size = _element_byte_size(svg)
        if size < MIN_SVG_BYTES:
            continue

        description, visibility = classify_svg(svg)
        identifier = get_element_identifier(
            "svg",
            id_attr=svg.get("id"),
            class_attr=" ".join(svg.get("class", [])),
        )
        findings.append(Finding(
            element_type="inline-svg",
            element_identifier=identifier,
            description=description,
            visibility=visibility,
            size_bytes=size,
            percent_of_page=(size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="primary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(svg),
        ))

    return findings


def _analyze_data_uris(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find and measure base64 data URIs in element attributes."""
    findings = []
    seen_uris = set()

    for tag in soup.find_all(True):
        for attr_name, attr_value in tag.attrs.items():
            if isinstance(attr_value, list):
                attr_value = " ".join(attr_value)
            if not isinstance(attr_value, str):
                continue

            for match in DATA_URI_RE.finditer(attr_value):
                data_uri = match.group(0)
                # Use truncated URI as dedup key
                uri_key = data_uri[:200]
                if uri_key in seen_uris:
                    continue
                seen_uris.add(uri_key)

                size = _content_byte_size(data_uri)
                if size < MIN_DATA_URI_BYTES:
                    continue

                description, visibility = classify_data_uri(data_uri)
                identifier = get_element_identifier(
                    tag.name,
                    id_attr=tag.get("id"),
                    class_attr=" ".join(tag.get("class", []))
                    if isinstance(tag.get("class"), list)
                    else tag.get("class"),
                )
                findings.append(Finding(
                    element_type="data-uri",
                    element_identifier=f"{identifier} [{attr_name}]",
                    description=description,
                    visibility=visibility,
                    size_bytes=size,
                    percent_of_page=(size / total_bytes * 100)
                    if total_bytes
                    else 0,
                    priority="primary",
                    pages_found_on=[url],
                    searchable_snippet=_extract_snippet(tag),
                ))

    return findings


def _analyze_large_dom_subtrees(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find DOM elements with an unusually large number of descendants."""
    findings = []
    already_flagged = set()

    body = soup.find("body")
    if not body:
        return findings

    for element in body.find_all(True):
        # Skip elements nested inside already-flagged parents
        if any(parent_id in already_flagged for parent_id in [
            id(p) for p in element.parents if isinstance(p, Tag)
        ]):
            continue

        descendants = list(element.find_all(True))
        num_descendants = len(descendants)

        if num_descendants < MIN_DOM_SUBTREE_DESCENDANTS:
            continue

        size = _element_byte_size(element)
        # Only flag if it's a significant chunk of the total page
        if total_bytes > 0 and (size / total_bytes * 100) < 1.0:
            continue

        already_flagged.add(id(element))

        tag_name = element.name
        identifier = get_element_identifier(
            tag_name,
            id_attr=element.get("id"),
            class_attr=" ".join(element.get("class", []))
            if isinstance(element.get("class"), list)
            else element.get("class"),
        )
        findings.append(Finding(
            element_type="large-dom-subtree",
            element_identifier=identifier,
            description=(
                f"Large DOM subtree with {num_descendants} "
                f"descendant elements"
            ),
            visibility="user-visible",
            size_bytes=size,
            percent_of_page=(size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="primary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(element),
        ))

    return findings


def _analyze_hidden_content(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find large hidden content blocks (display:none, hidden attr)."""
    findings = []
    min_hidden_bytes = 2000  # Only flag hidden blocks > 2KB

    for element in soup.find_all(True):
        style = element.get("style", "")
        hidden_attr = element.get("hidden") is not None

        is_hidden = (
            hidden_attr
            or "display:none" in style.replace(" ", "").lower()
            or "display: none" in style.lower()
        )

        if not is_hidden:
            continue

        size = _element_byte_size(element)
        if size < min_hidden_bytes:
            continue

        identifier = get_element_identifier(
            element.name,
            id_attr=element.get("id"),
            class_attr=" ".join(element.get("class", []))
            if isinstance(element.get("class"), list)
            else element.get("class"),
        )
        findings.append(Finding(
            element_type="hidden-content",
            element_identifier=identifier,
            description="Hidden content block (display:none or hidden)",
            visibility="backend",
            size_bytes=size,
            percent_of_page=(size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="primary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(element),
        ))

    return findings


def _analyze_html_comments(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find large HTML comments."""
    findings = []
    min_comment_bytes = 1000

    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    total_comment_size = 0

    for comment in comments:
        total_comment_size += _content_byte_size(str(comment))

    if total_comment_size >= min_comment_bytes:
        findings.append(Finding(
            element_type="html-comments",
            element_identifier=f"<!-- {len(comments)} comments -->",
            description=(
                f"{len(comments)} HTML comments totaling "
                f"{total_comment_size:,} bytes"
            ),
            visibility="backend",
            size_bytes=total_comment_size,
            percent_of_page=(total_comment_size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="primary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(comments[0] if comments else ""),
        ))

    return findings


def _analyze_noscript_blocks(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find large <noscript> blocks."""
    findings = []
    min_noscript_bytes = 2000

    for ns in soup.find_all("noscript"):
        size = _element_byte_size(ns)
        if size < min_noscript_bytes:
            continue

        identifier = get_element_identifier(
            "noscript",
            id_attr=ns.get("id"),
            class_attr=" ".join(ns.get("class", []))
            if isinstance(ns.get("class"), list)
            else ns.get("class"),
        )
        findings.append(Finding(
            element_type="noscript-fallback",
            element_identifier=identifier,
            description="Large <noscript> fallback content",
            visibility="backend",
            size_bytes=size,
            percent_of_page=(size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="primary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(ns),
        ))

    return findings


def _analyze_inline_style_attributes(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Find excessive use of inline style="..." attributes."""
    findings = []
    min_total_style_bytes = 3000

    total_style_bytes = 0
    elements_with_style = 0

    for tag in soup.find_all(True):
        style = tag.get("style")
        if not style:
            continue
            
        style_str = " ".join(style) if isinstance(style, list) else style
        total_style_bytes += _content_byte_size(style_str)
        elements_with_style += 1

    if total_style_bytes >= min_total_style_bytes:
        findings.append(Finding(
            element_type="inline-style-attributes",
            element_identifier=f"{elements_with_style} style attributes",
            description=f"Excessive inline CSS properties across {elements_with_style} elements",
            visibility="backend",
            size_bytes=total_style_bytes,
            percent_of_page=(total_style_bytes / total_bytes * 100)
            if total_bytes
            else 0,
            priority="primary",
            pages_found_on=[url],
            searchable_snippet=f"Found {elements_with_style} elements with inline styles totaling {total_style_bytes} bytes.",
        ))

    return findings


def _analyze_external_scripts(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Catalog external <script src="..."> tags (secondary priority)."""
    findings = []

    for script in soup.find_all("script", src=True):
        src = script["src"]
        is_async = script.get("async") is not None
        is_defer = script.get("defer") is not None

        description, visibility = classify_external_resource(src)
        loading = []
        if is_async:
            loading.append("async")
        if is_defer:
            loading.append("defer")
        if loading:
            description += f" ({', '.join(loading)})"

        # The tag itself is small in the HTML (just the <script> tag)
        tag_size = _element_byte_size(script)

        identifier = get_element_identifier("script", src=src)
        findings.append(Finding(
            element_type="external-script",
            element_identifier=identifier,
            description=description,
            visibility=visibility,
            size_bytes=tag_size,
            percent_of_page=(tag_size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="secondary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(script),
        ))

    return findings


def _analyze_external_stylesheets(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Catalog external stylesheet <link> tags (secondary priority)."""
    findings = []

    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if not href:
            continue

        description, visibility = classify_external_resource(href)
        if description == "Unknown third-party resource":
            description = "External stylesheet"
            visibility = "user-visible"

        tag_size = _element_byte_size(link)

        identifier = get_element_identifier("link", src=href)
        findings.append(Finding(
            element_type="external-stylesheet",
            element_identifier=identifier,
            description=description,
            visibility=visibility,
            size_bytes=tag_size,
            percent_of_page=(tag_size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="secondary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(link),
        ))

    return findings


def _analyze_images(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Catalog <img> tags (secondary priority, but count them)."""
    findings = []
    images = soup.find_all("img")

    if not images:
        return findings

    total_img_tag_bytes = sum(_element_byte_size(img) for img in images)
    lazy_count = sum(
        1
        for img in images
        if img.get("loading") == "lazy"
        or "lazy" in " ".join(img.get("class", []))
    )

    findings.append(Finding(
        element_type="images",
        element_identifier=f"<img> x {len(images)}",
        description=(
            f"{len(images)} image tags "
            f"({lazy_count} lazy-loaded, "
            f"{len(images) - lazy_count} eager)"
        ),
        visibility="user-visible",
        size_bytes=total_img_tag_bytes,
        percent_of_page=(total_img_tag_bytes / total_bytes * 100)
        if total_bytes
        else 0,
        priority="secondary",
        pages_found_on=[url],
        searchable_snippet=_extract_snippet(images[0] if images else ""),
    ))

    return findings


def _analyze_iframes(
    soup: BeautifulSoup,
    total_bytes: int,
    url: str,
) -> list[Finding]:
    """Catalog <iframe> tags (secondary priority)."""
    findings = []

    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        description, visibility = classify_external_resource(src)
        if description == "Unknown third-party resource":
            description = "Embedded iframe"
            visibility = "user-visible"

        tag_size = _element_byte_size(iframe)
        identifier = get_element_identifier("iframe", src=src)

        findings.append(Finding(
            element_type="iframe",
            element_identifier=identifier,
            description=description,
            visibility=visibility,
            size_bytes=tag_size,
            percent_of_page=(tag_size / total_bytes * 100)
            if total_bytes
            else 0,
            priority="secondary",
            pages_found_on=[url],
            searchable_snippet=_extract_snippet(iframe),
        ))

    return findings


def analyze_page(url: str, html: str) -> PageAnalysis:
    """Perform a complete weight analysis on a single HTML page.

    Runs all primary and secondary analyzers and returns a
    PageAnalysis object with all findings sorted by size descending.

    Args:
        url: The page URL (for reporting).
        html: The raw HTML string.

    Returns:
        A PageAnalysis with all findings.
    """
    total_bytes = _content_byte_size(html)
    soup = BeautifulSoup(html, "lxml")

    all_findings: list[Finding] = []

    # Primary analyzers — inline content contributing to file size
    all_findings.extend(_analyze_inline_scripts(soup, total_bytes, url))
    all_findings.extend(_analyze_inline_styles(soup, total_bytes, url))
    all_findings.extend(_analyze_inline_svgs(soup, total_bytes, url))
    all_findings.extend(_analyze_data_uris(soup, total_bytes, url))
    all_findings.extend(_analyze_large_dom_subtrees(soup, total_bytes, url))
    all_findings.extend(_analyze_hidden_content(soup, total_bytes, url))
    all_findings.extend(_analyze_html_comments(soup, total_bytes, url))
    all_findings.extend(_analyze_noscript_blocks(soup, total_bytes, url))
    all_findings.extend(_analyze_inline_style_attributes(soup, total_bytes, url))

    # Secondary analyzers — external resources (less impactful on file size)
    all_findings.extend(_analyze_external_scripts(soup, total_bytes, url))
    all_findings.extend(_analyze_external_stylesheets(soup, total_bytes, url))
    all_findings.extend(_analyze_images(soup, total_bytes, url))
    all_findings.extend(_analyze_iframes(soup, total_bytes, url))

    # Sort by size descending
    all_findings.sort(key=lambda f: f.size_bytes, reverse=True)

    return PageAnalysis(
        url=url,
        total_html_bytes=total_bytes,
        findings=all_findings,
    )
