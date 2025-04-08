# Changelog

## [Unreleased]

### Added

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

- Implemented Oyez API client infrastructure:
  - Base API client with rate limiting and retry functionality
  - Case-specific client for handling different Oyez API endpoints
  - Robust error handling for API requests

### Changed

- Refactored original audio_io.py into a modular, well-structured component
- Implemented proper type hints and docstrings throughout the codebase
- Added documentation for all public functions and classes

### Improved

- Enhanced error handling with detailed context information
- Improved code organization following layered architecture principles
- Added robust parameter validation for all functions
- Added API response samples for development reference in docs/api_investigation

### Infrastructure

- Set up project structure following the layered architecture design
- Added package initialization files with proper documentation
- Implemented pre-commit hooks for code quality assurance
