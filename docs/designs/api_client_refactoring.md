# API Client Refactoring Design

## Overview

This document outlines a comprehensive refactoring plan for the Oyez API client classes to address the growing complexity of `case_client.py` and to share common functionality between the various client implementations.

## Problem Statement

The current implementation faces several challenges:

1. **Excessive Class Size**: The `OyezCaseClient` class has grown to approximately 760 lines of code with multiple responsibilities.

2. **Code Duplication**: Common functionality like pagination handling is duplicated between `OyezCaseClient` and `TrackedOyezClient`.

3. **Limited Testability**: Large classes with multiple responsibilities are difficult to test effectively.

4. **Limited Reusability**: Key features like auto-pagination aren't easily shared between client implementations.

## Design Principles

1. **Single Responsibility Principle**: Each class and module should have one clearly defined responsibility.

2. **Composition Over Inheritance**: Use mixins and composition to build client functionality.

3. **Dependency Injection**: Inject dependencies to improve testability.

4. **Test-Driven Development**: Write tests before implementation to ensure correctness.

5. **Interface Consistency**: Maintain consistent interfaces across client implementations.

## Architecture

The refactoring will separate concerns into distinct components:

### 1. Base Client Components

```
┌─────────────────────────┐
│    BaseOyezClient       │
│  (core HTTP functions)  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐       ┌───────────────────────┐
│  PaginationMixin        │◄──────│  AdaptiveRateLimiter  │
│(pagination capabilities)│       │  (manage API limits)  │
└───────────┬─────────────┘       └───────────────────────┘
            │
            ▼
┌─────────────────────────┐
│    TrackedClientMixin   │
│  (request tracking)     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│    OyezClient           │
│(combines capabilities)  │
└─────────────────────────┘
```

### 2. Feature-specific Parsers

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   CaseDataParser    │  │   SpeakerParser     │  │   UtteranceParser   │
│                     │  │                     │  │                     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
            ▲                      ▲                        ▲
            │                      │                        │
            └──────────────────────┼────────────────────────┘
                                  │
                                  ▼
                        ┌─────────────────────┐
                        │  AudioContentParser │
                        │                     │
                        └─────────────────────┘
```

### 3. Specialized Clients (Depend on Base Client)

```
┌─────────────────────┐     ┌─────────────────────┐
│    CaseClient       │     │   TrackedClient     │
│ (case specific API) │     │ (with tracking)     │
└────────┬────────────┘     └──────────┬──────────┘
         │                             │
         │                             │
         ▼                             ▼
┌─────────────────────┐     ┌─────────────────────┐
│  AudioContentClient │     │ TrackedCaseClient   │
│ (audio content)     │     │ (tracked case API)  │
└─────────────────────┘     └─────────────────────┘
```

## Component Specifications

### 1. `PaginationMixin`

**Responsibility**: Handle pagination for API endpoints that support it.

**Key methods**:

- `iter_paginated_resource(endpoint, params)`: Generator that yields results across pages
- `get_paginated_resource(endpoint, params)`: Return all results from all pages
- `get_page_resource(endpoint, params, page)`: Get a specific page of results

**Testing strategy**:

- Test with mock responses for various pagination scenarios
- Test with edge cases (empty pages, partial pages)

### 2. Data Parsers

**CaseDataParser**:

- Methods for extracting case information from API responses
- Validate and normalize case data

**AudioContentParser**:

- Methods for extracting audio URLs from various formats
- Handle different audio formats and sources

**SpeakerParser**:

- Extract and normalize speaker information
- Handle different speaker formats across API endpoints

**UtteranceParser**:

- Extract and normalize utterance information
- Handle timing information and text segments

### 3. Specialized Clients

**CaseClient**:

- Focus on case-specific API methods
- Use parsers for data extraction
- Reuse pagination logic

**AudioContentClient**:

- Focus on audio content retrieval and processing
- Reuse pagination logic where needed

**TrackedClient**:

- Add tracking functionality to any client
- Record API interactions for debugging and monitoring

## Implementation Plan

### Phase 1: Create Common Components with TDD

1. **Create pagination mixin**:

   - Extract pagination logic into a reusable `PaginationMixin` class
   - Start with a test class that verifies pagination behavior
   - Ensure it works with different endpoint structures

2. **Create a base client interface**:
   - Define an abstract base class for all Oyez API clients
   - Focus on core HTTP operations
   - Add appropriate unit tests

### Phase 2: Create Specialized Parsers with TDD

1. **Create `CaseDataParser`**:

   - Extract case data parsing logic from `OyezCaseClient`
   - Create comprehensive tests for different API response formats

2. **Create `AudioContentParser`**:

   - Extract audio URL extraction logic
   - Include comprehensive tests

3. **Create `SpeakerParser`**:

   - Extract speaker extraction logic
   - Test with different response formats

4. **Create `UtteranceParser`**:
   - Extract utterance extraction logic
   - Test with different response formats

### Phase 3: Recreate Specialized Clients using TDD

1. **Create `CaseClient`**:

   - Use the base client and parsers
   - Only include case-specific API methods
   - Develop comprehensive tests

2. **Create `AudioContentClient`**:
   - Focus solely on audio content retrieval
   - Use existing parsers
   - Add thorough test coverage

### Phase 4: Integrate Tracking Functionality

1. **Create `TrackedClientMixin`**:

   - Extract tracking logic into a reusable mixin
   - Ensure it can be applied to any client
   - Test thoroughly

2. **Create `TrackedCaseClient`**:
   - Combine `CaseClient` with tracking functionality
   - Ensure all original functionality is preserved
   - Test comprehensively

## Testing Strategy

### Unit Tests

1. **Component Tests**:

   - Test each parser with various API response formats
   - Test pagination with different page sizes and result sets
   - Test tracking with mock loggers

2. **Interface Tests**:
   - Ensure consistent interfaces between components
   - Verify behavior of abstract classes and mixins

### Integration Tests

1. **Combined Component Tests**:

   - Test combinations of components (e.g., clients with parsers)
   - Ensure tracking properly integrates with API calls

2. **Client Compatibility Tests**:
   - Verify that new clients behave identically to old ones
   - Test with identical API responses

### End-to-End Tests

1. **Workflow Tests**:
   - Test complete workflows with mock API responses
   - Verify correct data flow through components

## Migration Strategy

To ensure a smooth transition from the current implementation to the new architecture:

1. **Parallel Implementation**:

   - Keep existing clients functional while developing new ones
   - Add tests for existing behavior to ensure compatibility

2. **Incremental Adoption**:

   - Migrate internal features first (parsers, mixins)
   - Replace client implementations once features are stable

3. **Feature Parity Validation**:
   - Ensure all features are available in the new implementation
   - Run integration tests against both implementations

## Benefits

1. **Improved Maintainability**: Smaller, focused classes are easier to understand and modify
2. **Better Testability**: Single-responsibility components are easier to test thoroughly
3. **Enhanced Reusability**: Common functionality can be shared between client implementations
4. **Future Extensibility**: New clients can be created by composing existing components

## Conclusion

This refactoring will significantly improve the maintainability, testability, and reusability of the Oyez API client code. By applying TDD principles and focusing on single-responsibility components, we'll create a more robust foundation for future development.
