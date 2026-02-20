"""Unit tests for analyzer module."""

import pytest

from analyzer import (
    Finding,
    PageAnalysis,
    analyze_page,
)


# --- Sample HTML fragments for testing ---

MINIMAL_HTML = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><p>Hello world</p></body>
</html>"""

HTML_WITH_INLINE_SCRIPT = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<script>
// This is a large inline script that should be flagged
var config = {
    key1: "value1",
    key2: "value2",
    key3: "value3",
    longData: "%s"
};
</script>
</body>
</html>""" % ("x" * 1000)

HTML_WITH_INLINE_STYLE = """<!DOCTYPE html>
<html>
<head>
<title>Test</title>
<style>
/* Large inline stylesheet */
.class1 { color: red; margin: 10px; padding: 5px; }
.class2 { color: blue; margin: 10px; padding: 5px; }
%s
</style>
</head>
<body><p>Hello</p></body>
</html>""" % ("\n".join(
    f".generated-class-{i} {{ color: #{i:06x}; }}" for i in range(100)
))

HTML_WITH_JSON_LD = """<!DOCTYPE html>
<html>
<head>
<title>Test</title>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Test Product",
    "description": "%s"
}
</script>
</head>
<body><p>Product page</p></body>
</html>""" % ("A very detailed product description. " * 50)

HTML_WITH_LARGE_SVG = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" fill="red"/>
  %s
</svg>
</body>
</html>""" % ("\n".join(
    f'<rect x="{i}" y="{i}" width="10" height="10" fill="#{i:06x}"/>'
    for i in range(100)
))

HTML_WITH_DATA_URI = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<img src="data:image/png;base64,%s" alt="test"/>
</body>
</html>""" % ("A" * 2000)

HTML_WITH_HIDDEN_CONTENT = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<div style="display:none">
  %s
</div>
</body>
</html>""" % ("\n".join(
    f"<p>Hidden paragraph {i} with lots of text content here.</p>"
    for i in range(100)
))

HTML_WITH_EXTERNAL_SCRIPTS = """<!DOCTYPE html>
<html>
<head>
<title>Test</title>
<script src="https://www.googletagmanager.com/gtm.js?id=GTM-XXXX"
    async></script>
<script src="https://connect.facebook.net/en_US/fbevents.js"
    async></script>
<script src="https://cdn.shopify.com/s/files/assets/theme.js"
    defer></script>
</head>
<body><p>Hello</p></body>
</html>"""

HTML_COMMENTS = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<!-- %s -->
<p>Content</p>
<!-- Another large comment block %s -->
</body>
</html>""" % ("x" * 600, "y" * 600)


class TestAnalyzePage:
    """Tests for the analyze_page function."""

    def test_minimal_page(self):
        result = analyze_page("https://example.com/", MINIMAL_HTML)
        assert isinstance(result, PageAnalysis)
        assert result.total_html_bytes > 0
        # Minimal page should have very few findings
        primary = [f for f in result.findings if f.priority == "primary"]
        assert len(primary) == 0

    def test_detects_inline_script(self):
        result = analyze_page("https://example.com/", HTML_WITH_INLINE_SCRIPT)
        inline_scripts = [
            f for f in result.findings
            if f.element_type == "inline-script"
        ]
        assert len(inline_scripts) >= 1
        assert inline_scripts[0].priority == "primary"
        assert inline_scripts[0].size_bytes > 500

    def test_detects_inline_style(self):
        result = analyze_page("https://example.com/", HTML_WITH_INLINE_STYLE)
        inline_styles = [
            f for f in result.findings
            if f.element_type == "inline-style"
        ]
        assert len(inline_styles) >= 1
        assert inline_styles[0].priority == "primary"
        assert inline_styles[0].description == "Inline CSS stylesheet"
        assert inline_styles[0].visibility == "user-visible"

    def test_detects_json_ld(self):
        result = analyze_page("https://example.com/", HTML_WITH_JSON_LD)
        json_ld = [
            f for f in result.findings if f.element_type == "json-ld"
        ]
        assert len(json_ld) >= 1
        assert "Product" in json_ld[0].description
        assert json_ld[0].visibility == "backend"

    def test_detects_inline_svg(self):
        result = analyze_page("https://example.com/", HTML_WITH_LARGE_SVG)
        svgs = [
            f for f in result.findings if f.element_type == "inline-svg"
        ]
        assert len(svgs) >= 1
        assert svgs[0].priority == "primary"
        assert svgs[0].visibility == "user-visible"

    def test_detects_data_uri(self):
        result = analyze_page("https://example.com/", HTML_WITH_DATA_URI)
        data_uris = [
            f for f in result.findings if f.element_type == "data-uri"
        ]
        assert len(data_uris) >= 1
        assert data_uris[0].priority == "primary"
        assert "image" in data_uris[0].description.lower()

    def test_detects_hidden_content(self):
        result = analyze_page(
            "https://example.com/", HTML_WITH_HIDDEN_CONTENT
        )
        hidden = [
            f for f in result.findings
            if f.element_type == "hidden-content"
        ]
        assert len(hidden) >= 1
        assert hidden[0].visibility == "backend"

    def test_detects_external_scripts(self):
        result = analyze_page(
            "https://example.com/", HTML_WITH_EXTERNAL_SCRIPTS
        )
        external = [
            f for f in result.findings
            if f.element_type == "external-script"
        ]
        assert len(external) == 3
        assert all(f.priority == "secondary" for f in external)

        # Check GTM was identified
        gtm = [f for f in external if "Tag Manager" in f.description]
        assert len(gtm) == 1

    def test_detects_html_comments(self):
        result = analyze_page("https://example.com/", HTML_COMMENTS)
        comments = [
            f for f in result.findings
            if f.element_type == "html-comments"
        ]
        assert len(comments) == 1
        assert comments[0].size_bytes > 1000

    def test_page_url_in_findings(self):
        url = "https://example.com/test-page"
        result = analyze_page(url, HTML_WITH_INLINE_SCRIPT)
        for finding in result.findings:
            assert url in finding.pages_found_on

    def test_findings_sorted_by_size(self):
        result = analyze_page("https://example.com/", HTML_WITH_INLINE_SCRIPT)
        sizes = [f.size_bytes for f in result.findings]
        assert sizes == sorted(sizes, reverse=True)

    def test_percent_of_page_calculated(self):
        result = analyze_page("https://example.com/", HTML_WITH_INLINE_SCRIPT)
        for finding in result.findings:
            if finding.size_bytes > 0:
                assert finding.percent_of_page > 0


class TestPageAnalysis:
    """Tests for the PageAnalysis dataclass."""

    def test_to_dict(self):
        analysis = analyze_page("https://example.com/", HTML_WITH_INLINE_SCRIPT)
        d = analysis.to_dict()
        assert "url" in d
        assert "total_html_bytes" in d
        assert "total_html_kb" in d
        assert "findings" in d
        assert isinstance(d["findings"], list)

    def test_flagged_percent_property(self):
        analysis = analyze_page("https://example.com/", HTML_WITH_INLINE_SCRIPT)
        assert 0 <= analysis.flagged_percent <= 100


class TestFinding:
    """Tests for the Finding dataclass."""

    def test_to_dict(self):
        finding = Finding(
            element_type="inline-script",
            element_identifier="<script>",
            description="Test script",
            visibility="backend",
            size_bytes=1024,
            percent_of_page=5.0,
            priority="primary",
            pages_found_on=["https://example.com/"],
        )
        d = finding.to_dict()
        assert d["element_type"] == "inline-script"
        assert d["size_bytes"] == 1024
        assert d["percent_of_page"] == 5.0
        assert d["priority"] == "primary"
