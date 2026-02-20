"""Unit tests for sitemap_parser module."""

import pytest

from sitemap_parser import (
    extract_urls_from_xml,
    get_template_key,
    group_urls_by_template,
    is_sitemap_index,
    select_sample_urls,
)


SAMPLE_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/collections/shoes</loc></url>
  <url><loc>https://example.com/collections/hats</loc></url>
  <url><loc>https://example.com/collections/bags</loc></url>
  <url><loc>https://example.com/products/red-shoe</loc></url>
  <url><loc>https://example.com/products/blue-hat</loc></url>
  <url><loc>https://example.com/blog/post-1</loc></url>
  <url><loc>https://example.com/blog/post-2</loc></url>
  <url><loc>https://example.com/about</loc></url>
</urlset>
"""

SAMPLE_SITEMAP_INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-products.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-pages.xml</loc>
  </sitemap>
</sitemapindex>
"""


class TestExtractUrls:
    """Tests for extract_urls_from_xml."""

    def test_extracts_all_urls(self):
        urls = extract_urls_from_xml(SAMPLE_SITEMAP_XML)
        assert len(urls) == 9

    def test_preserves_url_strings(self):
        urls = extract_urls_from_xml(SAMPLE_SITEMAP_XML)
        assert "https://example.com/" in urls
        assert "https://example.com/collections/shoes" in urls
        assert "https://example.com/products/red-shoe" in urls

    def test_handles_empty_sitemap(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        </urlset>"""
        urls = extract_urls_from_xml(xml)
        assert urls == []


class TestIsSitemapIndex:
    """Tests for is_sitemap_index."""

    def test_regular_sitemap_is_not_index(self):
        assert is_sitemap_index(SAMPLE_SITEMAP_XML) is False

    def test_sitemap_index_is_detected(self):
        assert is_sitemap_index(SAMPLE_SITEMAP_INDEX_XML) is True


class TestGetTemplateKey:
    """Tests for get_template_key."""

    def test_root_url_is_homepage(self):
        assert get_template_key("https://example.com/") == "homepage"
        assert get_template_key("https://example.com") == "homepage"

    def test_first_segment_extraction(self):
        assert get_template_key(
            "https://example.com/collections/shoes"
        ) == "/collections/shoes"
        assert get_template_key(
            "https://example.com/products/red-shoe"
        ) == "/products/{slug}"
        assert get_template_key(
            "https://example.com/blog/post-1"
        ) == "/blog/{id}"

    def test_single_segment_path(self):
        assert get_template_key(
            "https://example.com/about"
        ) == "/about"

    def test_case_normalization(self):
        assert get_template_key(
            "https://example.com/Collections/Foo"
        ) == "/collections/foo"


class TestGroupUrlsByTemplate:
    """Tests for group_urls_by_template."""

    def test_groups_correctly(self):
        urls = extract_urls_from_xml(SAMPLE_SITEMAP_XML)
        groups = group_urls_by_template(urls)

        assert "homepage" in groups
        # The 3 collections are /shoes, /hats, /bags
        assert "/collections/shoes" in groups
        assert "/collections/hats" in groups
        assert "/collections/bags" in groups
        assert "/products/{slug}" in groups
        assert "/blog/{id}" in groups
        assert "/about" in groups

        assert len(groups["/products/{slug}"]) == 2
        assert len(groups["/blog/{id}"]) == 2
        assert len(groups["homepage"]) == 1


class TestSelectSampleUrls:
    """Tests for select_sample_urls."""

    def test_limits_samples_per_template(self):
        urls = extract_urls_from_xml(SAMPLE_SITEMAP_XML)
        groups = group_urls_by_template(urls)
        samples = select_sample_urls(groups, samples_per_template=2)

        for template, urls in samples.items():
            assert len(urls) <= 2

    def test_homepage_includes_root_url(self):
        urls = extract_urls_from_xml(SAMPLE_SITEMAP_XML)
        groups = group_urls_by_template(urls)
        samples = select_sample_urls(
            groups,
            samples_per_template=3,
            base_url="https://example.com",
        )

        assert "homepage" in samples
        assert any(
            url.rstrip("/") == "https://example.com"
            for url in samples["homepage"]
        )

    def test_respects_sample_count(self):
        groups = {
            "/products/{id}": [
                f"https://example.com/products/p{i}" for i in range(20)
            ],
        }
        samples = select_sample_urls(groups, samples_per_template=3)
        assert len(samples["/products/{id}"]) == 3

    def test_handles_fewer_urls_than_samples(self):
        groups = {
            "/products/{slug}": ["https://example.com/products/only-one"],
        }
        samples = select_sample_urls(groups, samples_per_template=3)
        assert len(samples["/products/{slug}"]) == 1
