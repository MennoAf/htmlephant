#!/usr/bin/env python3
"""Sitemap Page-Weight Auditor.

A CLI tool that parses an XML sitemap, groups URLs into page templates,
crawls sample pages, and reports the heaviest inline HTML elements.

Usage:
    python main.py <sitemap-url> [--output report.json] [--samples 3]
    python main.py <sitemap-url> --no-secondary
    python main.py <sitemap-url> --cache-dir my_cache
"""

import argparse
import sys
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from analyzer import PageAnalysis, analyze_page
from crawler import crawl_pages
from reporter import (
    aggregate_findings,
    print_findings_report,
    print_page_summary,
    print_scope_summary,
    write_excel_report,
    write_json_report,
)
from sitemap_parser import (
    fetch_all_urls,
    group_urls_by_template,
    select_sample_urls,
)


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        A configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Sitemap Page-Weight Auditor — Identify the heaviest "
            "elements in your HTML files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py https://example.com/sitemap.xml\n"
            "  python main.py https://example.com/sitemap.xml "
            "--samples 2 --output report.json\n"
            "  python main.py https://example.com/sitemap.xml "
            "--no-secondary\n"
        ),
    )
    parser.add_argument(
        "sitemap_url",
        help="URL of the XML sitemap to analyze.",
    )
    parser.add_argument(
        "--output", "-o",
        default="report.json",
        help="Path for the JSON report output (default: report.json).",
    )
    parser.add_argument(
        "--excel", "-e",
        help="Path for the Excel report output. Defaults to the JSON filename with a .xlsx extension.",
    )
    parser.add_argument(
        "--samples", "-s",
        type=int,
        default=3,
        help=(
            "Number of sample URLs per template "
            "(default: 3, range: 1-10)."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default="crawled_pages",
        help=(
            "Directory to cache crawled HTML files "
            "(default: crawled_pages)."
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between HTTP requests (default: 1.0).",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=3,
        help="Number of concurrent workers for crawling (default: 3).",
    )
    parser.add_argument(
        "--no-secondary",
        action="store_true",
        help="Hide secondary findings (external resources) from output.",
    )
    return parser


def main() -> int:
    """Main entry point for the sitemap page-weight auditor.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = _build_arg_parser()
    args = parser.parse_args()

    console = Console()

    # Validate samples argument
    if not 1 <= args.samples <= 10:
        console.print("[red]Error: --samples must be between 1 and 10.[/]")
        return 1

    # Extract base URL for homepage detection
    parsed_url = urlparse(args.sitemap_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    # --- Banner ---
    console.print()
    console.print(Panel(
        "[bold]Sitemap Page-Weight Auditor[/]\n"
        f"[dim]Sitemap:[/] {args.sitemap_url}\n"
        f"[dim]Samples per template:[/] {args.samples}\n"
        f"[dim]Output:[/] {args.output}",
        border_style="bold blue",
    ))
    console.print()

    # --- Step 1: Parse sitemap ---
    console.print(Panel(
        "[bold]Step 1/4: Parsing Sitemap[/]",
        border_style="cyan",
    ))
    try:
        all_urls = fetch_all_urls(args.sitemap_url, console=console)
    except Exception as exc:
        console.print(f"[red]Failed to fetch sitemap: {exc}[/]")
        return 1

    if not all_urls:
        console.print("[red]No URLs found in sitemap.[/]")
        return 1

    # --- Step 2: Identify templates and select samples ---
    console.print()
    console.print(Panel(
        "[bold]Step 2/4: Identifying Templates[/]",
        border_style="cyan",
    ))

    template_groups = group_urls_by_template(all_urls)

    console.print(
        f"\n[green]Found {len(template_groups)} templates "
        f"across {len(all_urls)} URLs:[/]"
    )
    for template, urls in sorted(template_groups.items()):
        console.print(f"  [cyan]{template}[/]: {len(urls)} URLs")

    sample_urls = select_sample_urls(
        template_groups,
        samples_per_template=args.samples,
        base_url=base_url,
    )

    total_samples = sum(len(urls) for urls in sample_urls.values())
    console.print(
        f"\n[green]Selected {total_samples} sample URLs "
        f"for analysis:[/]"
    )
    for template, urls in sorted(sample_urls.items()):
        for url in urls:
            console.print(f"  [dim]{template}[/] → {url}")

    # --- Step 3: Crawl selected pages ---
    console.print()
    console.print(Panel(
        "[bold]Step 3/4: Crawling Pages[/]",
        border_style="cyan",
    ))

    crawled = crawl_pages(
        sample_urls,
        cache_dir=args.cache_dir,
        delay=args.delay,
        max_workers=args.workers,
        console=console,
    )

    # --- Step 4: Analyze pages ---
    console.print()
    console.print(Panel(
        "[bold]Step 4/4: Analyzing HTML Weight[/]",
        border_style="cyan",
    ))

    analyses: dict[str, list[PageAnalysis]] = {}
    total_pages_to_analyze = sum(len(urls) for urls in crawled.values())
    
    if total_pages_to_analyze > 0:
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
            task_id = progress.add_task("[cyan]Analyzing...", total=total_pages_to_analyze)
            for template, url_html_map in crawled.items():
                analyses[template] = []
                for url, html in url_html_map.items():
                    short_url = url if len(url) < 40 else f"...{url[-37:]}"
                    progress.update(task_id, description=f"[cyan]Analyzing [dim]{short_url}[/]")
                    
                    if not html:
                        progress.update(task_id, advance=1)
                        continue
                        
                    analysis = analyze_page(url, html)
                    analyses[template].append(analysis)
                    progress.update(task_id, advance=1)
    else:
        console.print("[yellow]No pages to analyze.[/]")

    # --- Output ---
    console.print()
    console.rule("[bold]📊 RESULTS", style="bold blue")

    # Page size summary
    print_page_summary(analyses, console=console)

    # Aggregate findings
    aggregated = aggregate_findings(analyses)

    # Shared element summary
    print_scope_summary(aggregated, console=console)

    # Detailed findings
    print_findings_report(
        aggregated,
        console=console,
        show_secondary=not args.no_secondary,
    )

    # JSON report
    write_json_report(analyses, aggregated, args.output)
    console.print()
    console.print(
        f"[green]✅ JSON report written to:[/] [bold]{args.output}[/]"
    )

    # Excel report
    excel_path = args.excel or args.output.replace('.json', '.xlsx')
    if not excel_path.endswith('.xlsx'):
        excel_path += '.xlsx'
    write_excel_report(analyses, aggregated, excel_path)
    console.print(
        f"[green]✅ Excel report written to:[/] [bold]{excel_path}[/]"
    )
    console.print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
