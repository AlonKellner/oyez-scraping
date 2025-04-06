#!/usr/bin/env python
"""Script to count all labeled audio in Oyez using the cases API endpoint."""

import argparse
import asyncio
import json
import sys
import time
from collections import Counter

import aiohttp
import requests
from tqdm import tqdm


def fetch_all_labeled_cases(term: str | None = None) -> list[dict]:
    """Fetch all cases with labels from the Oyez API.

    Args:
        term: Optional term to filter cases by (e.g., "2022")

    Returns
    -------
        List of case dictionaries
    """
    base_url = "https://api.oyez.org/cases"
    per_page = 1000
    all_cases = []

    page = 0
    more_pages = True

    # Add term as query parameter if specified
    term_param = f"&filter=term:{term}" if term else ""

    with tqdm(desc="Fetching cases", unit="page") as pbar:
        while more_pages:
            url = f"{base_url}?page={page}&per_page={per_page}{term_param}"
            try:
                response = requests.get(
                    url, headers={"Accept": "application/json"}, timeout=30
                )
                response.raise_for_status()
                cases = response.json()

                # Check if we got any cases
                if not cases or len(cases) == 0:
                    more_pages = False
                else:
                    all_cases.extend(cases)
                    page += 1
                    pbar.update(1)
                    pbar.set_postfix({"cases": len(all_cases)})

                    # Small delay to avoid overwhelming the API
                    time.sleep(0.1)
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                more_pages = False

    print(f"Retrieved {len(all_cases)} labeled cases from Oyez API")
    return all_cases


async def fetch_detailed_case_async(
    session: aiohttp.ClientSession, case_id: str
) -> dict:
    """Fetch detailed case information for a specific case ID asynchronously.

    Args:
        session: aiohttp session
        case_id: The case ID

    Returns
    -------
        Dictionary with detailed case information
    """
    url = f"https://api.oyez.org/cases/{case_id}"
    try:
        async with session.get(
            url,
            headers={"Accept": "application/json"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                return {}

            data = await response.json()

            # Handle different response formats
            if isinstance(data, list) and data:
                return data[0]  # Return first item if response is a list
            elif isinstance(data, dict):
                return data
            else:
                print(f"Unexpected response format for case {case_id}")
                return {}
    except Exception as e:
        print(f"Error fetching detailed case {case_id}: {e}")
        return {}


async def process_case(
    session: aiohttp.ClientSession, case: dict, results: dict, term_counters: dict
) -> bool:
    """Process a single case and update the results.

    Args:
        session: aiohttp session
        case: Case dictionary
        results: Results dictionary to update
        term_counters: Term counters dictionary to update

    Returns
    -------
        True if the case has audio, False otherwise
    """
    # Extract case ID
    case_id = case.get("ID", "")
    if not case_id:
        return False

    # Extract term (defaulting to 'unknown')
    term = str(case.get("term", "unknown"))

    has_audio = False

    # Check for audio directly in the case data first
    oral_args = case.get("oral_argument_audio", [])
    opinion_announce = case.get("opinion_announcement", [])

    # If no audio found directly, get detailed case data
    # This is necessary as the list API doesn't always include audio information
    detailed_case = await fetch_detailed_case_async(session, case_id)
    if detailed_case:
        oral_args = detailed_case.get("oral_argument_audio", []) or oral_args
        opinion_announce = (
            detailed_case.get("opinion_announcement", []) or opinion_announce
        )

    # Process oral arguments if found
    if oral_args:
        has_audio = True
        if term not in results["oral-arguments"]:
            results["oral-arguments"][term] = []

        # Initialize term counter if it doesn't exist
        if term not in term_counters["oral-arguments"]:
            term_counters["oral-arguments"][term] = 0

        results["oral-arguments"][term].append(
            {
                "id": case_id,
                "name": case.get("name", "Unknown"),
                "audio_count": len(oral_args),
            }
        )
        term_counters["oral-arguments"][term] += len(oral_args)

    # Process opinion announcements if found
    if opinion_announce:
        has_audio = True
        if term not in results["opinion-announcements"]:
            results["opinion-announcements"][term] = []

        # Initialize term counter if it doesn't exist
        if term not in term_counters["opinion-announcements"]:
            term_counters["opinion-announcements"][term] = 0

        results["opinion-announcements"][term].append(
            {
                "id": case_id,
                "name": case.get("name", "Unknown"),
                "audio_count": len(opinion_announce),
            }
        )
        term_counters["opinion-announcements"][term] += len(opinion_announce)

    return has_audio


async def analyze_cases_async(cases: list[dict]) -> dict:
    """Analyze the cases to count audio files asynchronously.

    Args:
        cases: List of case dictionaries

    Returns
    -------
        Dictionary with audio statistics
    """
    results = {
        "oral-arguments": {},
        "opinion-announcements": {},
        "cases_total": len(cases),
        "cases_with_audio": 0,
    }

    term_counters = {
        "oral-arguments": Counter(),
        "opinion-announcements": Counter(),
    }

    # Set to track unique IDs
    processed_ids: set[str] = set()

    # Process cases in parallel with rate limiting
    connector = aiohttp.TCPConnector(limit=50)  # Limit concurrent connections
    async with aiohttp.ClientSession(connector=connector) as session:
        # Create a progress bar
        pbar = tqdm(total=len(cases), desc="Analyzing cases", unit="case")

        # Filter out duplicates before processing
        unique_cases = []
        for case in cases:
            case_id = case.get("ID", "")
            if case_id and case_id not in processed_ids:
                processed_ids.add(case_id)
                unique_cases.append(case)

        # Process cases in chunks to avoid overwhelming the API
        chunk_size = 50
        for i in range(0, len(unique_cases), chunk_size):
            chunk = unique_cases[i : i + chunk_size]
            chunk_tasks = []

            for case in chunk:
                task = asyncio.create_task(
                    process_case(session, case, results, term_counters)
                )
                chunk_tasks.append(task)

            # Wait for all tasks in the chunk to complete
            chunk_results = await asyncio.gather(*chunk_tasks)

            # Update the counter for cases with audio
            results["cases_with_audio"] += sum(
                1 for has_audio in chunk_results if has_audio
            )

            # Update the progress bar
            pbar.update(len(chunk))

            # Small delay between chunks to avoid overwhelming the API
            await asyncio.sleep(0.5)

        pbar.close()

    # Add counters to the results
    results["term_counters"] = {
        "oral-arguments": dict(term_counters["oral-arguments"]),
        "opinion-announcements": dict(term_counters["opinion-announcements"]),
    }

    return results


def get_earliest_latest_terms(results: dict) -> tuple[str | None, str | None]:
    """Get the earliest and latest terms with audio.

    Args:
        results: Results from analyze_cases

    Returns
    -------
        Tuple of (earliest_term, latest_term)
    """
    all_terms = set()

    # Collect all terms from both audio types
    for audio_type in ["oral-arguments", "opinion-announcements"]:
        all_terms.update(results["term_counters"][audio_type].keys())

    # Filter out non-numeric and 'unknown' terms
    numeric_terms = []
    for term in all_terms:
        if term != "unknown" and term.isdigit():
            numeric_terms.append(int(term))

    if not numeric_terms:
        return None, None

    earliest = min(numeric_terms)
    latest = max(numeric_terms)

    return str(earliest), str(latest)


def print_audio_stats(results: dict) -> None:
    """Print statistics about labeled audio files.

    Args:
        results: Results dictionary from analyze_cases
    """
    print("\n=== OYEZ LABELED AUDIO STATISTICS ===\n")

    # Calculate totals
    oral_arg_count = sum(results["term_counters"]["oral-arguments"].values())
    opinion_count = sum(results["term_counters"]["opinion-announcements"].values())
    total_audio = oral_arg_count + opinion_count

    # Get earliest and latest terms
    earliest_term, latest_term = get_earliest_latest_terms(results)
    term_range = (
        f"({earliest_term} - {latest_term})" if earliest_term and latest_term else ""
    )

    # Print overall counts
    print(f"Total cases analyzed: {results['cases_total']}")
    print(
        f"Cases with audio: {results['cases_with_audio']} ({results['cases_with_audio'] / results['cases_total'] * 100:.1f}% of all cases)"
    )
    print(f"Total audio files: {total_audio} {term_range}")
    print(f"  - Oral arguments: {oral_arg_count}")
    print(f"  - Opinion announcements: {opinion_count}")

    # Print term breakdowns
    print("\n=== ORAL ARGUMENTS BY TERM ===")
    for term, count in sorted(
        results["term_counters"]["oral-arguments"].items(),
        key=lambda x: x[0] if x[0].isdigit() else "0",
        reverse=True,
    ):
        print(f"  Term {term}: {count} audio files")

    print("\n=== OPINION ANNOUNCEMENTS BY TERM ===")
    for term, count in sorted(
        results["term_counters"]["opinion-announcements"].items(),
        key=lambda x: x[0] if x[0].isdigit() else "0",
        reverse=True,
    ):
        print(f"  Term {term}: {count} audio files")

    # Print sample of cases for the most recent terms
    if results["oral-arguments"]:
        print("\n=== SAMPLE RECENT CASES WITH ORAL ARGUMENTS ===")
        recent_terms = sorted(
            [term for term in results["oral-arguments"] if term.isdigit()],
            reverse=True,
        )[:3]
        for term in recent_terms:
            print(f"Term {term}:")
            for case in results["oral-arguments"][term][:3]:
                print(
                    f"  - {case['name']} ({case['id']}): {case['audio_count']} audio files"
                )

    if results["opinion-announcements"]:
        print("\n=== SAMPLE RECENT CASES WITH OPINION ANNOUNCEMENTS ===")
        recent_terms = sorted(
            [term for term in results["opinion-announcements"] if term.isdigit()],
            reverse=True,
        )[:3]
        for term in recent_terms:
            print(f"Term {term}:")
            for case in results["opinion-announcements"][term][:3]:
                print(
                    f"  - {case['name']} ({case['id']}): {case['audio_count']} audio files"
                )


async def main_async() -> None:
    """Run the main script logic asynchronously."""
    parser = argparse.ArgumentParser(
        description="Count all labeled audio files in Oyez"
    )
    parser.add_argument("--output", type=str, help="Save results to a JSON file")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Maximum number of cases to process (for testing)",
    )
    parser.add_argument(
        "--check-case",
        action="store_true",
        help="Check a specific case we know has audio",
    )
    parser.add_argument(
        "--term",
        type=str,
        help="Filter cases by specific term (e.g., '2022')",
    )
    args = parser.parse_args()

    try:
        # Check a specific case if requested
        if args.check_case:
            await check_specific_case()
            return

        print("Fetching all labeled cases from Oyez API...")
        all_cases = fetch_all_labeled_cases(term=args.term)

        # If term is specified, print it
        if args.term:
            print(f"Filtering cases for term: {args.term}")

        # Limit cases if requested (for testing)
        if args.max_cases and args.max_cases < len(all_cases):
            print(f"Limiting analysis to {args.max_cases} cases (for testing)")
            all_cases = all_cases[: args.max_cases]

        print(f"Analyzing {len(all_cases)} cases for audio files...")
        results = await analyze_cases_async(all_cases)

        # Print statistics
        print_audio_stats(results)

        # Save to file if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {args.output}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


async def check_specific_case() -> None:
    """Check a specific case we know has audio to validate the script."""
    print("\n=== CHECKING SPECIFIC CASE ===")
    try:
        # Gonzalez v. Google LLC (2023)
        case_id = "2022/21-1333"

        print(f"Checking case {case_id}...")

        # Create session for async requests
        async with aiohttp.ClientSession() as session:
            # Get case data
            url = f"https://api.oyez.org/cases/{case_id}"
            async with session.get(
                url,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    print(f"Error: Could not fetch case {case_id}")
                    return

                case_data = await response.json()

                if isinstance(case_data, list):
                    case_data = case_data[0] if case_data else {}

                case_name = case_data.get("name", "Unknown")
                print(f"Case name: {case_name}")

                # Check for oral argument audio
                oral_args = case_data.get("oral_argument_audio", [])
                if oral_args:
                    print(f"✓ Has {len(oral_args)} oral argument audio files")
                    for i, arg in enumerate(oral_args):
                        print(f"  Audio {i + 1}: {arg.get('href', 'Unknown URL')}")
                else:
                    print("✗ No oral argument audio found")

                # Check for opinion announcement
                opinion_announce = case_data.get("opinion_announcement", [])
                if opinion_announce:
                    print(
                        f"✓ Has {len(opinion_announce)} opinion announcement audio files"
                    )
                else:
                    print("✗ No opinion announcement audio found")
    except Exception as e:
        print(f"Error checking specific case: {e}")


def main() -> None:
    """Run the main script logic."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
