#!/usr/bin/env python3
"""
Download and analyze academic papers using Playwright.

Usage:
    python download_paper.py "豆包" --output summary.md
    python download_paper.py "ByteDance Doubao" --source arxiv
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Download directory
DOWNLOAD_DIR = Path(__file__).parent.parent.parent.parent / "tmp"


def ensure_download_dir():
    """Ensure download directory exists."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_DIR


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search arxiv for papers matching query."""
    from playwright.sync_api import sync_playwright

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Search arxiv
        search_url = f"https://arxiv.org/search/?query={query}&searchtype=all&source=header"
        page.goto(search_url, timeout=30000)
        page.wait_for_load_state("networkidle")

        # Extract paper info
        papers = page.locator("li.arxiv-result").all()

        for paper in papers[:max_results]:
            try:
                title_elem = paper.locator("p.title")
                title = title_elem.text_content().strip() if title_elem.count() > 0 else ""

                # Get arxiv ID from the link
                link_elem = paper.locator("p.list-title a").first
                arxiv_url = link_elem.get_attribute("href") if link_elem.count() > 0 else ""
                arxiv_id = arxiv_url.split("/")[-1] if arxiv_url else ""

                # Get abstract
                abstract_elem = paper.locator("span.abstract-full")
                abstract = ""
                if abstract_elem.count() > 0:
                    abstract = abstract_elem.text_content().strip()
                    # Remove "Less" button text
                    abstract = re.sub(r'\s*△ Less\s*$', '', abstract)

                # Get authors
                authors_elem = paper.locator("p.authors")
                authors = authors_elem.text_content().strip() if authors_elem.count() > 0 else ""
                authors = authors.replace("Authors:", "").strip()

                # Get submission date
                date_elem = paper.locator("p.is-size-7")
                date_text = date_elem.text_content() if date_elem.count() > 0 else ""

                if title and arxiv_id:
                    results.append({
                        "title": title,
                        "arxiv_id": arxiv_id,
                        "url": f"https://arxiv.org/abs/{arxiv_id}",
                        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                        "authors": authors,
                        "abstract": abstract,
                        "date": date_text
                    })
            except Exception as e:
                print(f"Error parsing paper: {e}", file=sys.stderr)
                continue

        browser.close()

    return results


def download_pdf(pdf_url: str, filename: str | None = None) -> Path:
    """Download PDF from URL."""
    from playwright.sync_api import sync_playwright

    download_dir = ensure_download_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Download PDF
        with page.expect_download(timeout=60000) as download_info:
            page.goto(pdf_url)

        download = download_info.value

        # Determine filename
        if filename:
            save_path = download_dir / filename
        else:
            save_path = download_dir / download.suggested_filename

        download.save_as(save_path)
        browser.close()

    return save_path


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF file."""
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

        return "\n\n".join(text_parts)
    except ImportError:
        print("Warning: pdfplumber not installed. Install with: pip install pdfplumber",
              file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Error extracting PDF text: {e}", file=sys.stderr)
        return ""


def generate_summary(paper_info: dict, pdf_text: str) -> str:
    """Generate a summary markdown document."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary = f"""# Paper Summary

**Generated:** {timestamp}

## Paper Information

- **Title:** {paper_info.get('title', 'N/A')}
- **Authors:** {paper_info.get('authors', 'N/A')}
- **ArXiv ID:** {paper_info.get('arxiv_id', 'N/A')}
- **URL:** {paper_info.get('url', 'N/A')}
- **PDF:** {paper_info.get('pdf_url', 'N/A')}

## Abstract

{paper_info.get('abstract', 'No abstract available.')}

## Key Sections

"""

    # Try to extract key sections from PDF text
    if pdf_text:
        # Look for common section headers
        sections = ["Introduction", "Method", "Methodology", "Approach", "Results",
                    "Experiments", "Conclusion", "Discussion"]

        for section in sections:
            pattern = rf"(?i)\n\s*\d*\.?\s*{section}\s*\n"
            if re.search(pattern, pdf_text):
                summary += f"- {section}\n"

        # Add a snippet of the introduction
        intro_match = re.search(
            r"(?i)(?:introduction|1\.\s*introduction)\s*\n([\s\S]{200,1000}?)(?=\n\s*\d+\.|\n\s*[A-Z][a-z]+\s*\n)",
            pdf_text
        )
        if intro_match:
            intro_snippet = intro_match.group(1).strip()
            intro_snippet = re.sub(r'\s+', ' ', intro_snippet)[:500]
            summary += f"\n## Introduction Excerpt\n\n{intro_snippet}...\n"

    summary += f"""
## Download Location

PDF saved to: `{paper_info.get('local_path', 'N/A')}`

---
*This summary was generated automatically by the browser skill.*
"""

    return summary


def main():
    parser = argparse.ArgumentParser(description="Download and analyze academic papers")
    parser.add_argument("query", help="Search query (e.g., '豆包' or 'ByteDance Doubao')")
    parser.add_argument("--source", choices=["arxiv"], default="arxiv",
                        help="Paper source (default: arxiv)")
    parser.add_argument("--output", "-o", help="Output summary filename")
    parser.add_argument("--max-results", "-n", type=int, default=5,
                        help="Maximum search results")
    parser.add_argument("--download-first", "-d", action="store_true",
                        help="Download the first matching paper")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")

    args = parser.parse_args()

    print(f"Searching for: {args.query}", file=sys.stderr)

    # Search for papers
    if args.source == "arxiv":
        results = search_arxiv(args.query, args.max_results)

    if not results:
        print("No papers found.", file=sys.stderr)
        sys.exit(1)

    if args.json and not args.download_first:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        sys.exit(0)

    # Show results
    print(f"\nFound {len(results)} papers:\n", file=sys.stderr)
    for i, paper in enumerate(results, 1):
        print(f"{i}. {paper['title'][:80]}...", file=sys.stderr)
        print(f"   ID: {paper['arxiv_id']}", file=sys.stderr)

    # Download first paper if requested
    if args.download_first and results:
        paper = results[0]
        print(f"\nDownloading: {paper['title'][:60]}...", file=sys.stderr)

        # Download PDF
        pdf_filename = f"{paper['arxiv_id'].replace('/', '_')}.pdf"
        pdf_path = download_pdf(paper['pdf_url'], pdf_filename)
        paper['local_path'] = str(pdf_path)
        print(f"Saved to: {pdf_path}", file=sys.stderr)

        # Extract text
        print("Extracting text...", file=sys.stderr)
        pdf_text = extract_pdf_text(pdf_path)

        # Generate summary
        summary = generate_summary(paper, pdf_text)

        # Save or print summary
        if args.output:
            output_path = ensure_download_dir() / args.output
            output_path.write_text(summary, encoding="utf-8")
            print(f"Summary saved to: {output_path}", file=sys.stderr)
        else:
            print(summary)

        if args.json:
            paper['summary_generated'] = True
            print(json.dumps(paper, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
