# Request Tracking and Observability Design

## Overview

This document outlines a request tracking system to enhance observability in the Oyez scraping project. The system will track API requests and correlate them with output files, enabling better debugging, monitoring, and understanding of API behavior.

## Problem Statement

When scraping the Oyez API, we need better observability into API interactions to:

1. Trace the relationship between output files and the requests that generated them
2. Debug API issues more effectively
3. Understand pagination patterns and rate limiting behavior
4. Maintain a historical record of API interactions

We're currently seeing unexpected results from the API (e.g., only 30 cases being returned when there should be more), and without request tracking, it's difficult to diagnose what's happening.

## Design Principles

1. **Simplicity**: Use naming conventions to create natural mappings between files
2. **Minimal Dependencies**: Minimize impact on existing codebase
3. **Complete Information**: Capture all relevant request metadata
4. **Structured Storage**: Organize logs for easy analysis
5. **Performance**: Minimal overhead for request tracking
6. **Testability**: Design for isolated component testing

## Architecture

### Components

1. **Request Metadata Model**

   - Structured representation of HTTP request/response details
   - Captures URLs, methods, headers, parameters, response codes, etc.
   - Includes timing information and error context

2. **Request Logger**

   - Records request metadata to files
   - Maintains parallel directory structure to data files
   - Uses consistent naming conventions

3. **Request Tracking Middleware**

   - Hooks into API client to capture request details
   - Records pre-request metadata and post-response details
   - Tracks errors and exceptional conditions

4. **Storage Integration**
   - Updates cache implementation to track request origins
   - Maintains relationship between data and request logs

### Storage Structure

The system will maintain parallel directory structures for data and request logs:

```
.app_cache/
├── raw/                    # Main data directory
│   ├── audio/              # Audio files
│   │   └── 70-161.mp3
│   ├── cases/              # Case JSON data
│   │   └── 1971_70-161.json
│   └── case_lists/         # Lists of cases
│       └── all_cases.json
└── request_logs/           # Request logs with parallel structure
    ├── audio/              # Audio request logs
    │   └── 70-161.request.json
    ├── cases/              # Case request logs
    │   └── 1971_70-161.request.json
    └── case_lists/         # Case list request logs
        └── all_cases.request.json
```

## Key Behaviors

### Recording Requests

1. Before making an API request, capture initial metadata (URL, method, parameters, headers)
2. After receiving a response, update metadata with response details (status code, timing, content type)
3. When storing resulting data, save request metadata with matching filename pattern

### Pagination Tracking

1. Track paginated requests as a related sequence
2. Record which page is being requested and how many items per page
3. Store cumulative statistics about items encountered across all pages

### Error Handling

1. Capture detailed information about failed requests
2. Include error messages and stack traces when applicable
3. Maintain the request-to-file relationship even for failed requests

## Testing Strategy

### Unit Testing

- Test components in isolation with appropriate mocks
- Verify metadata capture is accurate
- Ensure file naming conventions work as expected
- Test pagination tracking and error handling

### Integration Testing

- Verify API client integration works end-to-end
- Test actual file creation with temporary directories
- Ensure relationships between files are maintained correctly

## Implementation Phases

1. **Core Metadata Model**

   - Define data structure for request metadata
   - Implement serialization/deserialization

2. **Logging Infrastructure**

   - Create logging component with directory structure management
   - Implement file naming conventions

3. **API Client Integration**

   - Add middleware hooks to API client
   - Track request/response lifecycle

4. **Enhanced Pagination**

   - Improve pagination with proper metadata tracking
   - Fix current limitation of only 30 cases being retrieved

5. **Analysis Utilities**
   - Add tools to analyze request logs
   - Implement relationship navigation between files

## Benefits

1. **Debugging**: Easily diagnose API issues by examining request logs
2. **Reproducibility**: Recreate exact API requests for testing
3. **Observability**: Monitor API behavior and performance
4. **Data Integrity**: Verify that cached data came from expected API calls

## Conclusion

This request tracking system will significantly improve observability into the Oyez API scraping process with minimal impact on the existing codebase. The design follows the project's architecture guidelines and integrates cleanly with existing components.
