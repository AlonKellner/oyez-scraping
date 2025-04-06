#!/usr/bin/env python
"""Script to count the amount of labeled audio in Oyez using refactored components."""

import argparse
import sys

from src.api import OyezAPI
from src.audio_stats import AudioStatsCollector, AudioStatsReporter


def check_specific_case(case_id: str) -> None:
    """Check a specific case and print its audio information.

    Args:
        case_id: The case ID to check
    """
    print("\n=== CHECKING SPECIFIC CASE ===")
    collector = AudioStatsCollector()

    try:
        print(f"Checking case {case_id}...")
        case_data = OyezAPI.get_case_metadata(case_id)

        if isinstance(case_data, list):
            case_data = case_data[0] if case_data else {}

        case_name = case_data.get("name", "Unknown")
        print(f"Case name: {case_name}")

        # Get audio counts
        audio_counts = collector.verify_case_has_audio(case_id)

        # Report oral arguments
        if audio_counts["oral_arguments"] > 0:
            print(f"✓ Has {audio_counts['oral_arguments']} oral argument audio files")
            oral_args = case_data.get("oral_argument_audio", [])
            for i, arg in enumerate(oral_args):
                print(f"  Audio {i + 1}: {arg.get('href', 'Unknown URL')}")
        else:
            print("✗ No oral argument audio found")

        # Report opinion announcements
        if audio_counts["opinion_announcements"] > 0:
            print(
                f"✓ Has {audio_counts['opinion_announcements']} opinion announcement audio files"
            )
        else:
            print("✗ No opinion announcement audio found")

    except Exception as e:
        print(f"Error checking specific case: {e}")


def main() -> None:
    """Run the main script logic."""
    parser = argparse.ArgumentParser(description="Count labeled audio files in Oyez")
    parser.add_argument("--term", help="Limit to a specific term (e.g., '2022')")
    parser.add_argument(
        "--check-case", help="Check a specific case by ID (e.g. '2022/21-1333')"
    )
    parser.add_argument(
        "--max-terms",
        type=int,
        default=5,
        help="Maximum number of recent terms to check (default: 5)",
    )
    args = parser.parse_args()

    # Check specific case if requested
    if args.check_case:
        check_specific_case(args.check_case)
        return

    # Create the collector
    collector = AudioStatsCollector()

    print("Fetching labeled audio information from Oyez...")
    try:
        # Get term list if not specified
        if args.term:
            terms = [args.term]
            print(f"Processing term: {args.term}")
        else:
            terms = OyezAPI.get_term_list()
            print(
                f"Found {len(terms)} terms. Processing the "
                f"{args.max_terms} most recent terms..."
            )
            terms = terms[: args.max_terms]

        # Collect stats for the specified terms
        all_audio = collector.collect_stats_for_terms(terms)

        # Get case counts for each term
        for term in terms:
            term_has_audio = False
            for audio_type, term_data in all_audio.items():
                if term in term_data:
                    term_has_audio = True
                    print(f"  Found {len(term_data[term])} cases with {audio_type}")

            if not term_has_audio:
                print(f"  No audio found for term {term}")

        # Generate and print the report
        reporter = AudioStatsReporter()
        report = reporter.format_report(all_audio)
        print("\n" + report)

    except Exception as e:
        print(f"Error fetching audio information: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
