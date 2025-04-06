"""Module for collecting audio statistics from the Oyez API."""

import asyncio
import random
import time

import aiohttp
import requests
from tqdm import tqdm

from src.api import OyezAPI


class AudioStatsCollector:
    """Collects and processes audio statistics from the Oyez API."""

    def __init__(self, max_retries: int = 3, request_delay: float = 0.5) -> None:
        """Initialize the audio statistics collector.

        Args:
            max_retries: Maximum number of retries for API requests
            request_delay: Delay between requests in seconds
        """
        self.api = OyezAPI
        self.max_retries = max_retries
        self.request_delay = request_delay

    def collect_stats_by_term(
        self, term: str, max_cases: int | None = None, show_progress: bool = True
    ) -> dict[str, list[dict]]:
        """Collect audio statistics for a specific term.

        Args:
            term: The court term to collect statistics for (e.g. "2022")
            max_cases: Maximum number of cases to process (None for all)
            show_progress: Whether to show a progress bar

        Returns
        -------
            Dictionary mapping audio types to lists of cases with audio
        """
        audio_stats: dict[str, list[dict]] = {}

        # Get available audio types
        audio_types = self.api.get_audio_types()

        # Initialize result structure
        for audio_type in audio_types:
            audio_stats[audio_type] = []

        # Step 1: Get the list of cases for the specified term
        # Note: The term API response doesn't include audio data - we need to fetch that separately
        base_url = self.api.BASE_URL
        url = f"{base_url}/cases?filter=term:{term}&labels=true&page=0&per_page=1000"

        response = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
        response.raise_for_status()
        cases = response.json()

        # Limit cases if max_cases is specified
        if max_cases is not None and max_cases > 0:
            cases = cases[:max_cases]

        # Step 2: For each case in the list, fetch detailed case data to get audio information
        iterator = (
            tqdm(cases, desc=f"Processing term {term}") if show_progress else cases
        )
        for case in iterator:
            case_id = case.get("ID")
            if not case_id:
                continue

            # Step 3: Create a properly formatted case ID for detailed lookup
            # The API requires format: term/docket_number (e.g., "2022/21-1333")
            docket_number = case.get("docket_number")
            if not docket_number:
                continue

            full_case_id = f"{term}/{docket_number}"

            # Add delay to avoid overwhelming the API
            time.sleep(self.request_delay)

            # Step 4: Get detailed case data which includes audio information
            # Term-based API response doesn't include audio, so we must fetch each case directly
            detailed_case = self._get_detailed_case(full_case_id)

            # Step 5: Process the audio data from the detailed case
            # Process oral arguments
            if "oral-arguments" in audio_stats and detailed_case.get(
                "oral_argument_audio"
            ):
                audio_stats["oral-arguments"].append(detailed_case)

            # Process opinion announcements
            if "opinion-announcements" in audio_stats and detailed_case.get(
                "opinion_announcement"
            ):
                audio_stats["opinion-announcements"].append(detailed_case)

        return audio_stats

    def _get_detailed_case(self, case_id: str) -> dict:
        """Get detailed case data using direct case endpoint.

        Args:
            case_id: The case ID to fetch (format: term/docket_number)

        Returns
        -------
            Detailed case data dictionary
        """
        retries = 0
        while retries <= self.max_retries:
            try:
                # Always use the direct case endpoint to get audio information
                # Direct case endpoint is the only reliable source of audio data
                case_data = self.api.get_case_metadata(case_id)

                # Handle list response format
                if isinstance(case_data, list):
                    case_data = case_data[0] if case_data else {}

                return case_data
            except Exception as e:
                retries += 1
                if retries > self.max_retries:
                    print(
                        f"Failed to get case data for {case_id} after {self.max_retries} retries: {e}"
                    )
                    return {}

                # Exponential backoff with jitter
                backoff_time = self.request_delay * (2**retries) + random.uniform(0, 1)
                time.sleep(backoff_time)

        # This line should never be reached due to the return in the exception block,
        # but we add it to satisfy type checkers
        return {}

    async def collect_stats_by_term_async(
        self, term: str, max_cases: int | None = None
    ) -> dict[str, list[dict]]:
        """Collect audio statistics for a specific term asynchronously.

        Args:
            term: The court term to collect statistics for (e.g. "2022")
            max_cases: Maximum number of cases to process (None for all)

        Returns
        -------
            Dictionary mapping audio types to lists of cases with audio
        """
        audio_stats: dict[str, list[dict]] = {}

        # Get available audio types
        audio_types = self.api.get_audio_types()

        # Initialize result structure
        for audio_type in audio_types:
            audio_stats[audio_type] = []

        # Step 1: Get cases for the specified term
        base_url = self.api.BASE_URL
        url = f"{base_url}/cases?filter=term:{term}&labels=true&page=0&per_page=1000"

        async with aiohttp.ClientSession() as session:
            # First get the list of cases for the term
            async with session.get(
                url,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    return audio_stats

                cases = await response.json()

                # Limit cases if max_cases is specified
                if max_cases is not None and max_cases > 0:
                    cases = cases[:max_cases]

                # Use semaphore to limit concurrent requests
                semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

                # Step 2: For each case, create a proper case ID and fetch detailed data
                case_details = []
                for case in cases:
                    case_id = case.get("ID")
                    docket_number = case.get("docket_number")

                    if case_id and docket_number:
                        full_case_id = f"{term}/{docket_number}"

                        async with semaphore:
                            # Get detailed case data to access audio information
                            result = await self._fetch_detailed_case_async(
                                session, full_case_id
                            )
                            case_details.append(result)
                            # Small delay between requests
                            await asyncio.sleep(self.request_delay)

                # Step 3: Process the results and categorize by audio type
                for case in case_details:
                    if case:
                        # Process oral arguments
                        if "oral-arguments" in audio_stats and case.get(
                            "oral_argument_audio"
                        ):
                            audio_stats["oral-arguments"].append(case)

                        # Process opinion announcements
                        if "opinion-announcements" in audio_stats and case.get(
                            "opinion_announcement"
                        ):
                            audio_stats["opinion-announcements"].append(case)

        return audio_stats

    async def _fetch_detailed_case_async(
        self, session: aiohttp.ClientSession, case_id: str
    ) -> dict:
        """Fetch detailed case information asynchronously.

        Args:
            session: aiohttp session
            case_id: The case ID (format: term/docket_number)

        Returns
        -------
            Dictionary with detailed case information
        """
        base_url = self.api.BASE_URL
        url = f"{base_url}/cases/{case_id}"

        retries = 0
        while retries <= self.max_retries:
            try:
                async with session.get(
                    url,
                    headers={"Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        retries += 1
                        if retries > self.max_retries:
                            return {}

                        # Exponential backoff with jitter
                        backoff_time = self.request_delay * (
                            2**retries
                        ) + random.uniform(0, 1)
                        await asyncio.sleep(backoff_time)
                        continue

                    data = await response.json()

                    # Handle different response formats
                    if isinstance(data, list) and data:
                        return data[0]  # Return first item if response is a list
                    elif isinstance(data, dict):
                        return data
                    else:
                        return {}
            except Exception:
                retries += 1
                if retries > self.max_retries:
                    return {}

                # Exponential backoff with jitter
                backoff_time = self.request_delay * (2**retries) + random.uniform(0, 1)
                await asyncio.sleep(backoff_time)

        # This line should never be reached but is added to satisfy type checkers
        return {}

    def collect_stats_for_terms(
        self,
        terms: list[str],
        max_cases_per_term: int | None = None,
        show_progress: bool = True,
    ) -> dict[str, dict[str, list[dict]]]:
        """Collect audio statistics for multiple terms.

        Args:
            terms: List of court terms to collect statistics for
            max_cases_per_term: Maximum number of cases to process per term
            show_progress: Whether to show progress bars

        Returns
        -------
            Dictionary mapping audio types to dictionaries mapping terms to lists of cases
        """
        results: dict[str, dict[str, list[dict]]] = {}

        # Get available audio types
        audio_types = self.api.get_audio_types()

        # Initialize result structure
        for audio_type in audio_types:
            results[audio_type] = {}

        # Process each term
        term_iterator = tqdm(terms, desc="Processing terms") if show_progress else terms
        for term in term_iterator:
            term_stats = self.collect_stats_by_term(
                term, max_cases=max_cases_per_term, show_progress=show_progress
            )

            # Add non-empty results to the output
            for audio_type, cases in term_stats.items():
                if cases:  # Only include terms with actual cases
                    results[audio_type][term] = cases

        return results

    async def collect_stats_for_terms_async(
        self, terms: list[str], max_cases_per_term: int | None = None
    ) -> dict[str, dict[str, list[dict]]]:
        """Collect audio statistics for multiple terms asynchronously.

        Args:
            terms: List of court terms to collect statistics for
            max_cases_per_term: Maximum number of cases to process per term

        Returns
        -------
            Dictionary mapping audio types to dictionaries mapping terms to lists of cases
        """
        results: dict[str, dict[str, list[dict]]] = {}

        # Get available audio types
        audio_types = self.api.get_audio_types()

        # Initialize result structure
        for audio_type in audio_types:
            results[audio_type] = {}

        # Process chunks of terms concurrently to avoid overwhelming the API
        chunk_size = 2  # Reduced from 3 to avoid overwhelming the API
        for i in range(0, len(terms), chunk_size):
            term_chunk = terms[i : i + chunk_size]
            tasks = [
                self.collect_stats_by_term_async(term, max_cases=max_cases_per_term)
                for term in term_chunk
            ]

            chunk_results = await asyncio.gather(*tasks)

            # Process results from this chunk
            for term, term_stats in zip(term_chunk, chunk_results, strict=False):
                for audio_type, cases in term_stats.items():
                    if cases:  # Only include terms with actual cases
                        results[audio_type][term] = cases

        return results

    def verify_case_has_audio(self, case_id: str) -> dict[str, int]:
        """Verify if a specific case has audio and return counts.

        Args:
            case_id: The case ID to check (format: term/docket_number)

        Returns
        -------
            Dictionary with counts of different audio types
        """
        audio_counts = {"oral_arguments": 0, "opinion_announcements": 0}

        try:
            # Always use the direct case endpoint to get audio information
            detailed_case = self._get_detailed_case(case_id)

            # Count oral arguments
            oral_args = detailed_case.get("oral_argument_audio", [])
            audio_counts["oral_arguments"] = len(oral_args)

            # Count opinion announcements
            opinion_announce = detailed_case.get("opinion_announcement", [])
            audio_counts["opinion_announcements"] = len(opinion_announce)

            return audio_counts

        except Exception:
            # Return zero counts if there was an error
            return audio_counts
