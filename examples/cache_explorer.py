"""Display cached file structure utility for the raw data demo.

This helper script shows the structure of cached files and allows
examining specific items in the cache.
"""

import argparse
import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# pylint: disable=wrong-import-position
from oyez_scraping.infrastructure.storage.cache import RawDataCache  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Display and examine the structure of cached Oyez data"
    )

    parser.add_argument(
        "--cache-dir",
        type=str,
        default=".app_cache",
        help="Directory where cache files are stored (default: .app_cache)",
    )

    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="List all cached cases",
    )

    parser.add_argument(
        "--list-audio",
        action="store_true",
        help="List all cached audio files",
    )

    parser.add_argument(
        "--list-structure",
        action="store_true",
        help="Show the cache directory structure",
    )

    parser.add_argument(
        "--examine-case",
        type=str,
        help="Examine a specific case (e.g., '2022/21-476')",
    )

    parser.add_argument(
        "--examine-audio",
        type=str,
        help="Examine a specific audio file by ID",
    )

    parser.add_argument(
        "--show-index",
        action="store_true",
        help="Show the cache index file contents",
    )

    return parser.parse_args()


def list_cases(cache: RawDataCache) -> None:
    """List all cases in the cache.

    Args:
        cache: The RawDataCache instance
    """
    case_ids = cache.get_all_cached_case_ids()
    if not case_ids:
        print("No cases in cache.")
        return

    print(f"\nCached Cases ({len(case_ids)}):")
    print("=" * 40)

    # Sort cases by term and docket
    sorted_cases = sorted(case_ids)

    for case_id in sorted_cases:
        has_audio = cache.cache_index["cases"][case_id].get("has_audio", False)
        print(f"  {case_id}" + (" [has audio]" if has_audio else ""))


def list_audio(cache: RawDataCache) -> None:
    """List all audio files in the cache.

    Args:
        cache: The RawDataCache instance
    """
    audio_ids = list(cache.cache_index["audio_files"].keys())
    if not audio_ids:
        print("No audio files in cache.")
        return

    print(f"\nCached Audio Files ({len(audio_ids)}):")
    print("=" * 40)

    for audio_id in audio_ids:
        audio_info = cache.cache_index["audio_files"][audio_id]
        case_id = audio_info.get("case_id", "unknown")
        media_type = audio_info.get("media_type", "unknown")
        path = audio_info.get("path", "unknown")
        print(f"  ID: {audio_id}")
        print(f"     Case: {case_id}")
        print(f"     Type: {media_type}")
        print(f"     Path: {path}")

        # Get the file size if it exists
        full_path = cache.cache_dir / path
        if full_path.exists():
            size_kb = full_path.stat().st_size / 1024
            print(f"     Size: {size_kb:.2f} KB")
        print()


def show_directory_structure(cache_dir: Path, max_depth: int = 3) -> None:
    """Show the cache directory structure.

    Args:
        cache_dir: The cache directory path
        max_depth: Maximum depth to display
    """
    if not cache_dir.exists():
        print(f"Cache directory {cache_dir} does not exist.")
        return

    print("\nCache Directory Structure:")
    print("=" * 40)

    def print_dir(path: Path, prefix: str = "", depth: int = 0) -> None:
        """Print directory structure recursively.

        Args:
            path: Current path
            prefix: Prefix for indentation
            depth: Current depth level
        """
        if depth > max_depth:
            print(f"{prefix}...")
            return

        # Print current item
        print(f"{prefix}{path.name}/")

        # Get children sorted by type (directories first, then files)
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))

        # Process all items with appropriate prefixes
        count = len(items)
        for i, item in enumerate(items):
            is_last = i == count - 1
            item_prefix = prefix + ("└── " if is_last else "├── ")
            next_level_prefix = prefix + ("    " if is_last else "│   ")

            if item.is_dir():
                # For directories, pass the next level prefix for recursive calls
                print(f"{item_prefix}{item.name}/")
                print_dir(item, next_level_prefix, depth + 1)
            else:
                # For files, show their size
                size_kb = item.stat().st_size / 1024
                print(f"{item_prefix}{item.name} ({size_kb:.2f} KB)")

    print_dir(cache_dir)


def examine_case(cache: RawDataCache, case_id: str) -> None:
    """Examine the details of a specific case.

    Args:
        cache: The RawDataCache instance
        case_id: The ID of the case to examine
    """
    if not cache.case_exists(case_id):
        print(f"Case {case_id} not found in cache.")
        return

    print(f"\nCase Details: {case_id}")
    print("=" * 40)

    try:
        # Get basic case information from the cache index
        case_index = cache.cache_index["cases"][case_id]
        print(f"Path: {case_index.get('path', 'unknown')}")
        print(f"Cached at: {case_index.get('cached_at', 'unknown')}")
        print(f"Has audio: {case_index.get('has_audio', False)}")

        # Load the full case data
        case_data = cache.get_case_data(case_id)

        # Print key case information
        print("\nCase Information:")
        print(f"  Name: {case_data.get('name', 'unknown')}")
        print(f"  Term: {case_data.get('term', 'unknown')}")
        print(f"  Docket: {case_data.get('docket_number', 'unknown')}")
        print(f"  Argued: {case_data.get('argued_on', 'unknown')}")
        print(f"  Decided: {case_data.get('decided_on', 'unknown')}")

        # Check for audio content
        oral_args = case_data.get("oral_argument_audio", [])
        opinion_ann = case_data.get("opinion_announcement_audio", [])

        # Count audio files
        audio_count = len(oral_args) + len(opinion_ann)

        if audio_count > 0:
            print("\nAvailable Audio Content:")

            if oral_args:
                print(f"  Oral Arguments: {len(oral_args)}")
                for i, arg in enumerate(oral_args):
                    print(
                        f"    {i + 1}. {arg.get('title', 'Unknown')} - {arg.get('href', 'No URL')}"
                    )

            if opinion_ann:
                print(f"  Opinion Announcements: {len(opinion_ann)}")
                for i, op in enumerate(opinion_ann):
                    print(
                        f"    {i + 1}. {op.get('title', 'Unknown')} - {op.get('href', 'No URL')}"
                    )
        else:
            print("\nNo audio content available for this case.")

        # Find related audio files in the cache
        related_audio = []
        for audio_id, audio_info in cache.cache_index["audio_files"].items():
            if audio_info.get("case_id") == case_id:
                related_audio.append((audio_id, audio_info))

        if related_audio:
            print("\nCached Audio Files for this Case:")
            for audio_id, audio_info in related_audio:
                path = cache.cache_dir / audio_info.get("path", "")
                size_kb = path.stat().st_size / 1024 if path.exists() else 0
                print(f"  ID: {audio_id}")
                print(f"  Type: {audio_info.get('media_type', 'unknown')}")
                print(f"  Path: {audio_info.get('path', 'unknown')}")
                print(f"  Size: {size_kb:.2f} KB")
                print()

    except Exception as e:
        print(f"Error examining case: {e}")


def examine_audio(cache: RawDataCache, audio_id: str) -> None:
    """Examine the details of a specific audio file.

    Args:
        cache: The RawDataCache instance
        audio_id: The ID of the audio to examine
    """
    if not cache.audio_exists(audio_id):
        print(f"Audio {audio_id} not found in cache.")
        return

    print(f"\nAudio File Details: {audio_id}")
    print("=" * 40)

    try:
        # Get audio information from the cache index
        audio_info = cache.cache_index["audio_files"][audio_id]
        case_id = audio_info.get("case_id", "unknown")
        media_type = audio_info.get("media_type", "unknown")
        path = audio_info.get("path", "unknown")
        cached_at = audio_info.get("cached_at", "unknown")

        print(f"Case: {case_id}")
        print(f"Media Type: {media_type}")
        print(f"Path: {path}")
        print(f"Cached at: {cached_at}")

        # Get file information
        full_path = cache.cache_dir / path
        if full_path.exists():
            size_kb = full_path.stat().st_size / 1024
            print(f"Size: {size_kb:.2f} KB")
            print(f"Full Path: {full_path}")

            # If it's an audio file, attempt to get some basic metadata
            if media_type in ("mp3", "flac", "wav", "m4a"):
                try:
                    # Just show basic file info since we don't want to import audio libraries here
                    print(
                        "\nThis is a binary audio file. You can play it with an audio player."
                    )
                    print(f"Command to play (if you have ffplay): ffplay {full_path}")
                except Exception as e:
                    print(f"Error getting audio metadata: {e}")
        else:
            print("File does not exist at the expected location.")

    except Exception as e:
        print(f"Error examining audio: {e}")


def show_cache_index(cache: RawDataCache) -> None:
    """Show the cache index contents.

    Args:
        cache: The RawDataCache instance
    """
    print("\nCache Index Contents:")
    print("=" * 40)

    # Get statistics
    stats = cache.get_cache_stats()
    print(f"Case count: {stats['case_count']}")
    print(f"Audio count: {stats['audio_count']}")
    print(f"Case list count: {stats['case_list_count']}")

    # Print metadata from the index
    metadata = cache.cache_index["metadata"]
    print("\nMetadata:")
    print(f"  Created at: {metadata.get('created_at', 'unknown')}")
    print(f"  Last updated: {metadata.get('last_updated', 'unknown')}")
    print(f"  Version: {metadata.get('version', 'unknown')}")


def main() -> None:
    """Run the cache display utility.

    Processes command line arguments and performs the requested actions.
    If no specific actions are specified, displays a basic cache summary.
    """
    args = parse_args()

    # Initialize the cache
    cache_dir = Path(args.cache_dir)
    cache = RawDataCache(cache_dir)

    # Process commands
    if args.list_cases:
        list_cases(cache)

    if args.list_audio:
        list_audio(cache)

    if args.list_structure:
        show_directory_structure(cache_dir)

    if args.examine_case:
        examine_case(cache, args.examine_case)

    if args.examine_audio:
        examine_audio(cache, args.examine_audio)

    if args.show_index:
        show_cache_index(cache)

    # If no commands were specified, show usage
    if not any(
        [
            args.list_cases,
            args.list_audio,
            args.list_structure,
            args.examine_case,
            args.examine_audio,
            args.show_index,
        ]
    ):
        print("No actions specified. Use --help to see available options.")
        # Show basic cache stats
        stats = cache.get_cache_stats()
        print("\nCache Summary:")
        print(f"  Location: {cache_dir.resolve()}")
        print(f"  Cases: {stats['case_count']}")
        print(f"  Audio files: {stats['audio_count']}")
        print(f"  Case lists: {stats['case_list_count']}")


if __name__ == "__main__":
    main()
