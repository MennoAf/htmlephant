"""Rule-based classifier for known third-party services and element types.

Maps URL patterns and script/style signatures to human-readable
descriptions and visibility labels.
"""

import re
from typing import Optional, Tuple

# Each entry: (compiled_regex_pattern, purpose_description, visibility)
# visibility is either "user-visible" or "backend"
KNOWN_SCRIPT_PATTERNS: list[Tuple[re.Pattern, str, str]] = [
    # --- Analytics ---
    (
        re.compile(r"google[-_]?analytics|ga\.js|analytics\.js", re.I),
        "Google Analytics",
        "backend",
    ),
    (
        re.compile(r"gtag/js|googletagmanager\.com/gtag", re.I),
        "Google Analytics 4 (gtag)",
        "backend",
    ),
    (
        re.compile(r"googletagmanager\.com/gtm", re.I),
        "Google Tag Manager",
        "backend",
    ),
    (
        re.compile(r"hotjar\.com|static\.hotjar\.com", re.I),
        "Hotjar (heatmaps/recordings)",
        "backend",
    ),
    (
        re.compile(r"fullstory\.com|fs\.js", re.I),
        "FullStory (session replay)",
        "backend",
    ),
    (
        re.compile(r"heap[-_]?analytics|heapanalytics\.com", re.I),
        "Heap Analytics",
        "backend",
    ),
    (
        re.compile(r"amplitude\.com|amplitude\.min\.js", re.I),
        "Amplitude Analytics",
        "backend",
    ),
    (
        re.compile(r"mixpanel\.com|mixpanel\.min\.js", re.I),
        "Mixpanel Analytics",
        "backend",
    ),
    (
        re.compile(r"segment\.com|analytics\.min\.js|cdn\.segment", re.I),
        "Segment (analytics router)",
        "backend",
    ),
    (
        re.compile(r"tealium\.com|utag\.js", re.I),
        "Tealium (tag management)",
        "backend",
    ),
    (
        re.compile(r"adobe.*analytics|omniture|s_code\.js", re.I),
        "Adobe Analytics",
        "backend",
    ),
    (
        re.compile(r"clarity\.ms|clarity\.js", re.I),
        "Microsoft Clarity",
        "backend",
    ),

    # --- Advertising / Tracking Pixels ---
    (
        re.compile(r"connect\.facebook\.net|fbevents\.js|fbq\(", re.I),
        "Facebook/Meta Pixel",
        "backend",
    ),
    (
        re.compile(r"googleads|google_ads|conversion\.js|adservices", re.I),
        "Google Ads conversion tracking",
        "backend",
    ),
    (
        re.compile(r"snap\.licdn|linkedin\.com/insight|_linkedin_", re.I),
        "LinkedIn Insight Tag",
        "backend",
    ),
    (
        re.compile(r"tiktok\.com/i18n|ttq\.", re.I),
        "TikTok Pixel",
        "backend",
    ),
    (
        re.compile(r"pinterest\.com/ct\.js|pintrk\(", re.I),
        "Pinterest Tag",
        "backend",
    ),
    (
        re.compile(r"ads\.twitter|static\.ads-twitter", re.I),
        "Twitter/X Ads Pixel",
        "backend",
    ),
    (
        re.compile(r"criteo\.com|criteo\.net", re.I),
        "Criteo (retargeting)",
        "backend",
    ),

    # --- Chat / Support ---
    (
        re.compile(r"intercom\.io|intercomcdn\.com|widget\.intercom", re.I),
        "Intercom (chat/support widget)",
        "user-visible",
    ),
    (
        re.compile(r"drift\.com|js\.driftt\.com", re.I),
        "Drift (chat widget)",
        "user-visible",
    ),
    (
        re.compile(r"zendesk\.com|zdassets\.com|zopim", re.I),
        "Zendesk (support widget)",
        "user-visible",
    ),
    (
        re.compile(r"livechat|livechatinc\.com", re.I),
        "LiveChat widget",
        "user-visible",
    ),
    (
        re.compile(r"tawk\.to", re.I),
        "Tawk.to (chat widget)",
        "user-visible",
    ),
    (
        re.compile(r"crisp\.chat|client\.crisp\.chat", re.I),
        "Crisp (chat widget)",
        "user-visible",
    ),
    (
        re.compile(r"gorgias", re.I),
        "Gorgias (support widget)",
        "user-visible",
    ),

    # --- E-commerce Platforms ---
    (
        re.compile(r"cdn\.shopify\.com", re.I),
        "Shopify platform script",
        "backend",
    ),
    (
        re.compile(r"shopify-analytics|shopify_analytics", re.I),
        "Shopify Analytics",
        "backend",
    ),
    (
        re.compile(r"klaviyo\.com|static\.klaviyo", re.I),
        "Klaviyo (email marketing)",
        "backend",
    ),
    (
        re.compile(r"yotpo\.com", re.I),
        "Yotpo (reviews widget)",
        "user-visible",
    ),
    (
        re.compile(r"judge\.me", re.I),
        "Judge.me (reviews widget)",
        "user-visible",
    ),
    (
        re.compile(r"stamped\.io", re.I),
        "Stamped.io (reviews/loyalty)",
        "user-visible",
    ),
    (
        re.compile(r"loox\.io", re.I),
        "Loox (reviews widget)",
        "user-visible",
    ),
    (
        re.compile(r"recharge\.com|rechargepayments", re.I),
        "ReCharge (subscriptions)",
        "user-visible",
    ),
    (
        re.compile(r"afterpay|afterpay\.js", re.I),
        "Afterpay (BNPL widget)",
        "user-visible",
    ),
    (
        re.compile(r"klarna", re.I),
        "Klarna (BNPL widget)",
        "user-visible",
    ),

    # --- Fonts ---
    (
        re.compile(r"fonts\.googleapis\.com|fonts\.gstatic\.com", re.I),
        "Google Fonts",
        "user-visible",
    ),
    (
        re.compile(r"use\.typekit\.net|typekit", re.I),
        "Adobe Fonts / Typekit",
        "user-visible",
    ),

    # --- CDN / Frameworks ---
    (
        re.compile(r"jquery\.min\.js|jquery[-.](\d)", re.I),
        "jQuery library",
        "backend",
    ),
    (
        re.compile(r"react\.production\.min|react-dom", re.I),
        "React framework",
        "backend",
    ),
    (
        re.compile(r"bootstrap\.min\.(js|css)", re.I),
        "Bootstrap framework",
        "user-visible",
    ),
    (
        re.compile(r"unpkg\.com|cdnjs\.cloudflare\.com|cdn\.jsdelivr", re.I),
        "Public CDN resource",
        "backend",
    ),

    # --- Consent / Privacy ---
    (
        re.compile(r"cookiebot|consent\.cookiebot", re.I),
        "Cookiebot (consent management)",
        "user-visible",
    ),
    (
        re.compile(r"onetrust\.com|optanon", re.I),
        "OneTrust (consent management)",
        "user-visible",
    ),
    (
        re.compile(r"trustarc|truste\.com", re.I),
        "TrustArc (privacy management)",
        "user-visible",
    ),

    # --- Performance / Monitoring ---
    (
        re.compile(r"sentry\.io|browser\.sentry", re.I),
        "Sentry (error monitoring)",
        "backend",
    ),
    (
        re.compile(r"newrelic\.com|nr-data\.net|NREUM", re.I),
        "New Relic (APM)",
        "backend",
    ),
    (
        re.compile(r"datadog.*rum|datadoghq\.com", re.I),
        "Datadog RUM",
        "backend",
    ),
]

KNOWN_INLINE_PATTERNS: list[Tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"gtag\s*\(|dataLayer\.push", re.I),
        "Google Tag Manager / gtag inline config",
        "backend",
    ),
    (
        re.compile(r"fbq\s*\(", re.I),
        "Facebook Pixel inline initialization",
        "backend",
    ),
    (
        re.compile(r"_learnq|klaviyo", re.I),
        "Klaviyo inline tracking",
        "backend",
    ),
    (
        re.compile(r"shopify\..*analytics|Shopify\.analytics", re.I),
        "Shopify inline analytics",
        "backend",
    ),
    (
        re.compile(r"ttq\.", re.I),
        "TikTok Pixel inline initialization",
        "backend",
    ),
    (
        re.compile(r"pintrk\s*\(", re.I),
        "Pinterest Tag inline initialization",
        "backend",
    ),
    (
        re.compile(r"hj\s*\(|_hjSettings", re.I),
        "Hotjar inline initialization",
        "backend",
    ),
    (
        re.compile(r"intercomSettings|window\.Intercom", re.I),
        "Intercom inline configuration",
        "user-visible",
    ),
    (
        re.compile(r"window\.__reactRouterContext", re.I),
        "React Router / Hydrogen hydration state (large data payload)",
        "backend",
    ),
    (
        re.compile(r"window\.__REDUX_STATE__", re.I),
        "Redux initial state payload",
        "backend",
    ),
    (
        re.compile(r"Shopify\.theme", re.I),
        "Shopify theme configuration",
        "backend",
    ),
]

# Patterns for classifying JSON-LD structured data
JSON_LD_TYPE_PATTERNS: list[Tuple[re.Pattern, str, str]] = [
    (
        re.compile(r'"@type"\s*:\s*"Product"', re.I),
        "Product structured data (JSON-LD)",
        "backend",
    ),
    (
        re.compile(r'"@type"\s*:\s*"BreadcrumbList"', re.I),
        "Breadcrumb structured data (JSON-LD)",
        "backend",
    ),
    (
        re.compile(r'"@type"\s*:\s*"Organization"', re.I),
        "Organization structured data (JSON-LD)",
        "backend",
    ),
    (
        re.compile(r'"@type"\s*:\s*"WebSite"', re.I),
        "Website structured data (JSON-LD)",
        "backend",
    ),
    (
        re.compile(r'"@type"\s*:\s*"Article"', re.I),
        "Article structured data (JSON-LD)",
        "backend",
    ),
    (
        re.compile(r'"@type"\s*:\s*"CollectionPage"', re.I),
        "Collection page structured data (JSON-LD)",
        "backend",
    ),
    (
        re.compile(r'"@type"\s*:\s*"ItemList"', re.I),
        "Item list structured data (JSON-LD)",
        "backend",
    ),
]


def classify_external_resource(url: str) -> Tuple[str, str]:
    """Classify an external resource URL.

    Args:
        url: The URL of the external resource.

    Returns:
        A tuple of (purpose_description, visibility_label).
        Falls back to ("Unknown third-party resource", "backend")
        if no pattern matches.
    """
    for pattern, description, visibility in KNOWN_SCRIPT_PATTERNS:
        if pattern.search(url):
            return description, visibility
    return "Unknown third-party resource", "backend"


def classify_inline_content(content: str) -> Tuple[str, str]:
    """Classify inline script content by checking for known signatures.

    Args:
        content: The text content of an inline script/style tag.

    Returns:
        A tuple of (purpose_description, visibility_label).
        Falls back to showing a snippet if no match.
    """
    for pattern, description, visibility in KNOWN_INLINE_PATTERNS:
        if pattern.search(content):
            return description, visibility

    # Extract a preview snippet of the first 80 characters (ignoring whitespace)
    snippet = content.strip().replace("\n", " ")[:80]
    if len(content.strip()) > 80:
        snippet += "..."

    return f"Custom inline code ({snippet})", "backend"


def classify_json_ld(content: str) -> Tuple[str, str]:
    """Classify JSON-LD structured data content.

    Args:
        content: The text content of a JSON-LD script tag.

    Returns:
        A tuple of (purpose_description, visibility_label).
    """
    for pattern, description, visibility in JSON_LD_TYPE_PATTERNS:
        if pattern.search(content):
            return description, visibility
    return "Structured data (JSON-LD)", "backend"


def classify_svg(svg_element) -> Tuple[str, str]:
    """Classify an inline SVG element.

    Args:
        svg_element: A BeautifulSoup Tag for an <svg> element.

    Returns:
        A tuple of (purpose_description, visibility_label).
    """
    # Check for common icon-system patterns
    use_tags = svg_element.find_all("use")
    symbol_tags = svg_element.find_all("symbol")

    if symbol_tags:
        return "SVG symbol sprite sheet", "user-visible"
    if use_tags:
        return "SVG icon (via <use> reference)", "user-visible"

    # Check if it's hidden (sprite sheets often are)
    style = svg_element.get("style", "")
    aria_hidden = svg_element.get("aria-hidden", "")
    class_attr = " ".join(svg_element.get("class", []))

    if "display:none" in style.replace(" ", "") or "hidden" in class_attr:
        return "Hidden SVG sprite sheet", "backend"

    if aria_hidden == "true":
        return "Decorative SVG icon", "user-visible"

    return "Inline SVG graphic", "user-visible"


def classify_data_uri(data_uri: str) -> Tuple[str, str]:
    """Classify a base64 data URI.

    Args:
        data_uri: The data URI string.

    Returns:
        A tuple of (purpose_description, visibility_label).
    """
    if data_uri.startswith("data:image/svg"):
        return "Inline SVG data URI", "user-visible"
    if data_uri.startswith("data:image/"):
        return "Inline base64-encoded image", "user-visible"
    if data_uri.startswith("data:font/") or data_uri.startswith(
        "data:application/font"
    ):
        return "Inline base64-encoded font", "user-visible"
    if data_uri.startswith("data:application/json"):
        return "Inline JSON data URI", "backend"
    return "Inline data URI", "backend"


def get_element_identifier(
    tag_name: str,
    src: Optional[str] = None,
    type_attr: Optional[str] = None,
    id_attr: Optional[str] = None,
    class_attr: Optional[str] = None,
) -> str:
    """Generate a human-readable identifier for an HTML element.

    Args:
        tag_name: The HTML tag name.
        src: The src/href attribute, if present.
        type_attr: The type attribute, if present.
        id_attr: The id attribute, if present.
        class_attr: The class attribute string, if present.

    Returns:
        A concise, human-readable identifier string.
    """
    parts = [f"<{tag_name}"]
    if id_attr:
        parts.append(f' id="{id_attr}"')
    if type_attr:
        parts.append(f' type="{type_attr}"')
    if src:
        # Truncate long URLs
        display_src = src if len(src) <= 80 else src[:77] + "..."
        parts.append(f' src="{display_src}"')
    if class_attr and not src:
        # Only show class if no src (to keep it concise)
        truncated = (
            class_attr if len(class_attr) <= 40 else class_attr[:37] + "..."
        )
        parts.append(f' class="{truncated}"')
    parts.append(">")
    return "".join(parts)
