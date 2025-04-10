# Changelog

## [Unreleased]

### Added

- Enhanced download resilience for complete dataset acquisition:

  - Improved `AdaptiveRateLimiter` with more robust rate limiting strategies:

    - Added jitter to prevent synchronized requests and API rate limit triggers
    - Implemented global delay floor that adapts based on error patterns
    - Added tracking of consecutive successes/failures for smarter adaptation
    - Increased maximum retries and backoff times for persistent downloads

  - Added `DownloadTracker` for ensuring download completeness:
    - Persistent tracking of download state to support resume functionality
    - Automatic retry mechanism for failed downloads with progressive backoff
    - Multi-phase download process with targeted retry rounds
    - Statistics for monitoring download completion status

- Implemented parallel processing and performance optimizations for data scraping:

  - Created `AdaptiveRateLimiter` service for intelligent API rate limit handling
  - Developed high-performance `AudioDownloader` with concurrent download capabilities
  - Added multithreaded case processing to significantly improve scraping speed
  - Implemented streaming downloads for better memory efficiency
  - Added performance monitoring with real-time statistics reporting
  - Enhanced API client with batch processing capabilities to reduce overhead
  - Optimized caching mechanisms to minimize redundant API calls

- Implemented raw data scraping and caching system:

  - Created filesystem storage module with comprehensive error handling
  - Developed `RawDataCache` for efficiently caching Oyez API responses and audio files
  - Built `RawDataScraperService` for downloading and managing raw data with robust caching
  - Implemented utilities for exploring cached data structure and content
  - Added demo scripts for scraping and exploring cached data
  - Improved security by using SHA-256 instead of MD5 for hashing operations

- Added support for opinion announcements and dissenting opinions in addition to oral arguments:

  - New `AudioContentType` constants for different content types
  - Enhanced `OyezCaseClient` to retrieve and categorize different audio content types
  - Added methods for fetching and processing opinion announcements and dissenting opinions
  - Created integration tests validating the handling of all audio content types

- Implemented robust audio processing module (`oyez_scraping.infrastructure.processing.audio_io`) with the following features:

  - FLAC format support with high-quality audio encoding/decoding
  - Comprehensive error handling with custom exceptions
  - Audio normalization for consistent processing
  - Audio segment extraction functionality
  - Audio format conversion capabilities
  - Audio metadata retrieval

- Created custom exception hierarchy for infrastructure layer:

  - Base `InfrastructureError` class
  - Specialized `AudioProcessingError` class with context information
  - API-specific exceptions including `OyezApiError`, `RateLimitError`, `NetworkError`, `ResponseFormatError`, and `AudioUrlError`
  - Storage-specific exceptions including `StorageError`, `FileReadError`, `FileWriteError`, `DirectoryCreationError`, and `CacheError`

- Added comprehensive testing suite:

  - Unit tests for all audio processing functions
  - Integration tests for file operations and format conversions
  - Error handling tests for edge cases
  - Integration tests for Oyez API endpoints validating structure, relations, and media availability
  - Unit tests for storage and caching components
  - Integration tests for the raw data scraper service
  - Complete test coverage for `DownloadService` including retry logic, error handling, and progress monitoring

- Implemented Oyez API client infrastructure:
  - Base API client with rate limiting and retry functionality
  - Case-specific client for handling different Oyez API endpoints
  - Robust error handling for API requests

### Changed

- Refactored original audio_io.py into a modular, well-structured component
- Implemented proper type hints and docstrings throughout the codebase
- Added documentation for all public functions and classes
- Reduced logging verbosity by changing log levels from INFO to DEBUG for cache operations and API interactions

### Fixed

- Fixed the `DownloadService` class to handle retry logic properly:

  - Corrected retry mechanism in `_retry_failed_cases` method with proper exponential backoff
  - Fixed wait time calculation between retry rounds
  - Ensured proper updating of statistics during retry operations
  - Improved error handling in retry flows

- Fixed parameter order issue in `DownloadTracker._save_tracker` method:

  - Corrected parameter order when calling the storage service's `write_json` method
  - Fixed initialization process to consistently use the storage service
  - Added comprehensive test coverage to prevent similar issues
  - Resolved warning messages during download operations

- Fixed issue with `DownloadService` class comparing MagicMock objects with integers:
  - Added safe type conversion for retry statistics to handle MagicMock objects in testing environments
  - Made the retry statistics reporting more robust by handling None values
  - Improved the comparison logic in the statistics calculation

### Improved

- Enhanced error handling with detailed context information
- Improved code organization following layered architecture principles
- Added robust parameter validation for all functions
- Added API response samples for development reference in docs/api_investigation

### Infrastructure

- Set up project structure following the layered architecture design
- Added package initialization files with proper documentation
- Implemented pre-commit hooks for code quality assurance
