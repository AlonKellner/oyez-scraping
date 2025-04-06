"""Module for generating audio statistics reports."""

from collections import Counter


class AudioStatsReporter:
    """Generates reports and statistics about Oyez audio files."""

    @staticmethod
    def get_audio_counts(
        audio_data: dict[str, dict[str, list[dict]]],
    ) -> dict[str, int]:
        """Calculate total counts for each audio type.

        Args:
            audio_data: Nested dictionary of audio types and their data

        Returns
        -------
            Dictionary with counts for each audio type
        """
        counts = {}

        for audio_type, terms_data in audio_data.items():
            total_count = 0
            for _, cases in terms_data.items():
                total_count += len(cases)
            counts[audio_type] = total_count

        return counts

    @staticmethod
    def get_term_counts(
        audio_data: dict[str, dict[str, list[dict]]],
    ) -> dict[str, dict[str, int]]:
        """Calculate audio counts by term for each audio type.

        Args:
            audio_data: Nested dictionary of audio types and their data

        Returns
        -------
            Dictionary with term counts for each audio type
        """
        term_counts = {}

        for audio_type, terms_data in audio_data.items():
            audio_type_counts = {}
            for term, cases in terms_data.items():
                audio_type_counts[term] = len(cases)
            term_counts[audio_type] = audio_type_counts

        return term_counts

    @staticmethod
    def get_unique_terms(audio_data: dict[str, dict[str, list[dict]]]) -> set[str]:
        """Get the set of unique terms across all audio types.

        Args:
            audio_data: Nested dictionary of audio types and their data

        Returns
        -------
            Set of unique term identifiers
        """
        unique_terms = set()

        for _, terms_data in audio_data.items():
            unique_terms.update(terms_data.keys())

        return unique_terms

    @staticmethod
    def get_earliest_latest_terms(
        audio_data: dict[str, dict[str, list[dict]]],
    ) -> tuple[str, str]:
        """Get the earliest and latest terms in the data.

        Args:
            audio_data: Nested dictionary of audio types and their data

        Returns
        -------
            Tuple of (earliest_term, latest_term) or ("", "") if no terms
        """
        unique_terms = AudioStatsReporter.get_unique_terms(audio_data)

        # Filter out non-numeric terms
        numeric_terms = []
        for term in unique_terms:
            if term.isdigit():
                numeric_terms.append(int(term))

        if not numeric_terms:
            return "", ""

        earliest = min(numeric_terms)
        latest = max(numeric_terms)

        return str(earliest), str(latest)

    @staticmethod
    def format_report(audio_data: dict[str, dict[str, list[dict]]]) -> str:
        """Generate a formatted text report of audio statistics.

        Args:
            audio_data: Nested dictionary of audio types and their data

        Returns
        -------
            Formatted text report
        """
        report = []
        report.append("=== OYEZ LABELED AUDIO STATISTICS ===\n")

        # Get general statistics
        total_audio_count = 0
        total_terms = AudioStatsReporter.get_unique_terms(audio_data)
        audio_types_counter = Counter()

        # Calculate totals
        for audio_type, terms_data in audio_data.items():
            type_count = 0
            for _, cases in terms_data.items():
                type_count += len(cases)
            audio_types_counter[audio_type] = type_count
            total_audio_count += type_count

        # Get earliest and latest terms
        earliest_term, latest_term = AudioStatsReporter.get_earliest_latest_terms(
            audio_data
        )
        term_range = (
            f"({earliest_term} - {latest_term})"
            if earliest_term and latest_term
            else ""
        )

        # Print overall counts
        report.append(f"Total labeled audio files: {total_audio_count} {term_range}")
        report.append(f"Total unique terms: {len(total_terms)}")

        # Avoid division by zero
        if total_audio_count > 0:
            report.append("\nBreakdown by audio type:")
            for audio_type, count in audio_types_counter.items():
                report.append(
                    f"  {audio_type}: {count} files "
                    f"({count / total_audio_count * 100:.1f}%)"
                )

        # Process each audio type
        for audio_type, terms_data in audio_data.items():
            report.append(f"\n\nAudio Type: {audio_type}")
            report.append("=" * 40)

            type_count = audio_types_counter[audio_type]
            type_terms = set(terms_data.keys())

            # Print stats for this audio type
            report.append(f"Total files: {type_count}")
            report.append(f"Available terms: {len(type_terms)}")

            # Print term breakdown
            if terms_data:
                report.append("\nBreakdown by term:")
                for term in sorted(terms_data.keys(), reverse=True):
                    cases = terms_data[term]
                    report.append(f"  Term {term}: {len(cases)} cases")

                # Print sample of the most recent term
                most_recent_terms = sorted(
                    [t for t in terms_data if t.isdigit()], reverse=True
                )[:1]
                if most_recent_terms:
                    term = most_recent_terms[0]
                    report.append(f"\nSample cases from term {term}:")
                    for i, case in enumerate(terms_data[term][:3]):
                        report.append(
                            f"  - {case.get('name', 'Unknown')} ({case.get('ID', 'Unknown')})"
                        )
                        if i >= 2:  # Limit to 3 samples
                            break

        return "\n".join(report)
