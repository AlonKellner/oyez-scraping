#!/usr/bin/env python
"""Script to count the amount of labeled audio in Oyez using a different approach."""

import argparse
import json
import sys
import time
from collections import Counter

from src.api import OyezAPI


def get_sample_cases() -> list[str]:
    """Get a list of sample case IDs known to exist in Oyez."""
    return [
        # Recent cases with known audio
        "2022/21-1333",  # Gonzalez v. Google LLC (2023)
        "2021/20-1530",  # West Virginia v. EPA (2022)
        "2020/19-1392",  # Dobbs v. Jackson Women's Health Organization (2022)
        "2019/19-635",  # Trump v. Vance (2020)
        # Historical cases
        "1971/70-18",  # New York Times v. United States (1971)
        "1954/1",  # Brown v. Board of Education (1954)
        "1965/301",  # Miranda v. Arizona (1966)
        "1972/70-18",  # Roe v. Wade (1973)
    ]


def count_audio_for_cases(case_ids: list[str]) -> dict:
    """Count audio files for a list of cases.

    Args:
        case_ids: List of case IDs to check

    Returns
    -------
        Dictionary with audio statistics
    """
    results = {
        "oral-arguments": {},
        "opinion-announcements": {},
        "cases_checked": 0,
        "cases_with_audio": 0,
        "errors": 0,
    }

    term_counters = {
        "oral-arguments": Counter(),
        "opinion-announcements": Counter(),
    }

    for i, case_id in enumerate(case_ids):
        print(f"Checking case {i + 1}/{len(case_ids)}: {case_id}...")

        try:
            # Get case metadata
            case_data = OyezAPI.get_case_metadata(case_id)

            # Handle list return type
            if isinstance(case_data, list):
                case_data = case_data[0] if case_data else {}

            # Extract term information
            term = str(case_data.get("term", "unknown"))

            # Check for oral argument audio
            oral_args = case_data.get("oral_argument_audio", [])
            if oral_args:
                if term not in results["oral-arguments"]:
                    results["oral-arguments"][term] = []

                results["oral-arguments"][term].append(
                    {
                        "id": case_id,
                        "name": case_data.get("name", "Unknown"),
                        "audio_count": len(oral_args),
                    }
                )
                term_counters["oral-arguments"][term] += len(oral_args)

            # Check for opinion announcement
            opinion_announce = case_data.get("opinion_announcement", [])
            if opinion_announce:
                if term not in results["opinion-announcements"]:
                    results["opinion-announcements"][term] = []

                results["opinion-announcements"][term].append(
                    {
                        "id": case_id,
                        "name": case_data.get("name", "Unknown"),
                        "audio_count": len(opinion_announce),
                    }
                )
                term_counters["opinion-announcements"][term] += len(opinion_announce)

            # Count as a case with audio if it has either type
            if oral_args or opinion_announce:
                results["cases_with_audio"] += 1

            results["cases_checked"] += 1

            # Avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            print(f"  Error: {e}")
            results["errors"] += 1

    # Add counters to the results
    results["term_counters"] = {
        "oral-arguments": dict(term_counters["oral-arguments"]),
        "opinion-announcements": dict(term_counters["opinion-announcements"]),
    }

    return results


def print_audio_stats(results: dict) -> None:
    """Print statistics about labeled audio files.

    Args:
        results: Results dictionary from count_audio_for_cases
    """
    print("\n=== OYEZ LABELED AUDIO STATISTICS ===\n")

    # Calculate totals
    oral_arg_count = sum(results["term_counters"]["oral-arguments"].values())
    opinion_count = sum(results["term_counters"]["opinion-announcements"].values())
    total_audio = oral_arg_count + opinion_count

    # Print overall counts
    print(f"Cases checked: {results['cases_checked']}")
    print(
        f"Cases with audio: {results['cases_with_audio']} ({results['cases_with_audio'] / results['cases_checked'] * 100:.1f}% of checked cases)"
    )
    print(f"Errors encountered: {results['errors']}")
    print(f"Total audio files: {total_audio}")
    print(f"  - Oral arguments: {oral_arg_count}")
    print(f"  - Opinion announcements: {opinion_count}")

    # Print term breakdowns
    print("\n=== ORAL ARGUMENTS BY TERM ===")
    for term, count in sorted(
        results["term_counters"]["oral-arguments"].items(),
        key=lambda x: x[0],
        reverse=True,
    ):
        print(f"  Term {term}: {count} audio files")

    print("\n=== OPINION ANNOUNCEMENTS BY TERM ===")
    for term, count in sorted(
        results["term_counters"]["opinion-announcements"].items(),
        key=lambda x: x[0],
        reverse=True,
    ):
        print(f"  Term {term}: {count} audio files")

    # Print sample of cases
    if results["oral-arguments"]:
        print("\n=== SAMPLE CASES WITH ORAL ARGUMENTS ===")
        for term in list(results["oral-arguments"].keys())[:3]:
            print(f"Term {term}:")
            for case in results["oral-arguments"][term][:3]:
                print(
                    f"  - {case['name']} ({case['id']}): {case['audio_count']} audio files"
                )

    if results["opinion-announcements"]:
        print("\n=== SAMPLE CASES WITH OPINION ANNOUNCEMENTS ===")
        for term in list(results["opinion-announcements"].keys())[:3]:
            print(f"Term {term}:")
            for case in results["opinion-announcements"][term][:3]:
                print(
                    f"  - {case['name']} ({case['id']}): {case['audio_count']} audio files"
                )


def main() -> None:
    """Run the main script logic."""
    parser = argparse.ArgumentParser(description="Count labeled audio files in Oyez")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use a small sample of known cases (faster)",
    )
    parser.add_argument("--output", type=str, help="Save results to a JSON file")
    args = parser.parse_args()

    print("Counting labeled audio in Oyez...")

    try:
        # Get test cases
        if args.sample:
            case_ids = get_sample_cases()
            print(f"Using sample of {len(case_ids)} known cases")
        else:
            # In a full implementation, we would use a more comprehensive
            # list of cases, perhaps from a database or by crawling the website.
            # For now, default to the sample as well
            print("Full case list not implemented, using sample cases")
            case_ids = get_sample_cases()

        # Count audio files
        results = count_audio_for_cases(case_ids)

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


if __name__ == "__main__":
    main()
