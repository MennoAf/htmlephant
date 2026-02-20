"""Unit tests for classifiers module."""

import pytest

from classifiers import (
    classify_data_uri,
    classify_external_resource,
    classify_inline_content,
    classify_json_ld,
    classify_svg,
    get_element_identifier,
)


class TestClassifyExternalResource:
    """Tests for classify_external_resource."""

    def test_google_analytics(self):
        desc, vis = classify_external_resource(
            "https://www.google-analytics.com/analytics.js"
        )
        assert "Google Analytics" in desc
        assert vis == "backend"

    def test_gtm(self):
        desc, vis = classify_external_resource(
            "https://www.googletagmanager.com/gtm.js?id=GTM-XXXX"
        )
        assert "Google Tag Manager" in desc
        assert vis == "backend"

    def test_facebook_pixel(self):
        desc, vis = classify_external_resource(
            "https://connect.facebook.net/en_US/fbevents.js"
        )
        assert "Facebook" in desc or "Meta" in desc
        assert vis == "backend"

    def test_intercom(self):
        desc, vis = classify_external_resource(
            "https://widget.intercom.io/widget/abc123"
        )
        assert "Intercom" in desc
        assert vis == "user-visible"

    def test_shopify(self):
        desc, vis = classify_external_resource(
            "https://cdn.shopify.com/s/files/1/xxx/assets/theme.js"
        )
        assert "Shopify" in desc
        assert vis == "backend"

    def test_unknown_url(self):
        desc, vis = classify_external_resource(
            "https://totally-unknown.example.com/mystery.js"
        )
        assert desc == "Unknown third-party resource"
        assert vis == "backend"

    def test_google_fonts(self):
        desc, vis = classify_external_resource(
            "https://fonts.googleapis.com/css2?family=Inter"
        )
        assert "Google Fonts" in desc
        assert vis == "user-visible"

    def test_jquery(self):
        desc, vis = classify_external_resource(
            "https://cdnjs.cloudflare.com/ajax/libs/jquery.min.js"
        )
        # Should match either jQuery or Public CDN
        assert vis == "backend"

    def test_hotjar(self):
        desc, vis = classify_external_resource(
            "https://static.hotjar.com/c/hotjar-12345.js"
        )
        assert "Hotjar" in desc
        assert vis == "backend"

    def test_klaviyo(self):
        desc, vis = classify_external_resource(
            "https://static.klaviyo.com/onsite/js/klaviyo.js"
        )
        assert "Klaviyo" in desc
        assert vis == "backend"


class TestClassifyInlineContent:
    """Tests for classify_inline_content."""

    def test_gtag_inline(self):
        content = "gtag('config', 'G-XXXXXXX');"
        desc, vis = classify_inline_content(content)
        assert "gtag" in desc.lower() or "tag" in desc.lower()
        assert vis == "backend"

    def test_facebook_pixel_inline(self):
        content = "fbq('init', '123456789');"
        desc, vis = classify_inline_content(content)
        assert "Facebook" in desc
        assert vis == "backend"

    def test_datalayer_push(self):
        content = "dataLayer.push({'event': 'page_view'});"
        desc, vis = classify_inline_content(content)
        assert "Tag Manager" in desc or "gtag" in desc
        assert vis == "backend"

    def test_unknown_inline(self):
        content = "var x = 42; console.log(x);"
        desc, vis = classify_inline_content(content)
        assert "Custom inline code" in desc
        assert "var x = 42" in desc
        assert vis == "backend"

    def test_shopify_analytics_inline(self):
        content = "Shopify.analytics.publish('page_viewed');"
        desc, vis = classify_inline_content(content)
        assert "Shopify" in desc
        assert vis == "backend"


class TestClassifyJsonLd:
    """Tests for classify_json_ld."""

    def test_product_json_ld(self):
        content = '{"@type": "Product", "name": "Red Shoes"}'
        desc, vis = classify_json_ld(content)
        assert "Product" in desc
        assert vis == "backend"

    def test_breadcrumb_json_ld(self):
        content = '{"@type": "BreadcrumbList"}'
        desc, vis = classify_json_ld(content)
        assert "Breadcrumb" in desc

    def test_unknown_json_ld(self):
        content = '{"@type": "SomeCustomThing"}'
        desc, vis = classify_json_ld(content)
        assert "Structured data" in desc


class TestClassifyDataUri:
    """Tests for classify_data_uri."""

    def test_svg_data_uri(self):
        desc, vis = classify_data_uri("data:image/svg+xml;base64,PHN2Zz4=")
        assert "SVG" in desc
        assert vis == "user-visible"

    def test_png_data_uri(self):
        desc, vis = classify_data_uri("data:image/png;base64,iVBOR=")
        assert "image" in desc.lower()
        assert vis == "user-visible"

    def test_font_data_uri(self):
        desc, vis = classify_data_uri("data:font/woff2;base64,AAA=")
        assert "font" in desc.lower()
        assert vis == "user-visible"

    def test_json_data_uri(self):
        desc, vis = classify_data_uri("data:application/json;base64,ey=")
        assert "JSON" in desc
        assert vis == "backend"


class TestElementIdentifier:
    """Tests for get_element_identifier."""

    def test_basic_tag(self):
        result = get_element_identifier("script")
        assert result == "<script>"

    def test_with_src(self):
        result = get_element_identifier("script", src="main.js")
        assert '<script src="main.js">' == result

    def test_with_id(self):
        result = get_element_identifier("div", id_attr="header")
        assert '<div id="header">' == result

    def test_long_url_truncation(self):
        long_url = "https://example.com/" + "x" * 100
        result = get_element_identifier("script", src=long_url)
        assert "..." in result
        assert len(result) < 120
