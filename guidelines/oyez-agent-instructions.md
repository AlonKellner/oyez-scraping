# LLM Agent Instructions for Oyez Scraping Project

These instructions are designed to guide an LLM agent through the development of a high-quality, maintainable Oyez scraping project that creates an ASR/SID audio dataset. Following these principles will maximize the probability of success.

## Project Understanding Phase

1. **API Exploration First**:

   - Before writing any code, thoroughly investigate the Oyez API structure
   - Document the inconsistencies between endpoints:
     - Direct case lookup (`https://api.oyez.org/cases/{term}/{docket_number}`) returns complete audio data
     - Term-based lookup (`https://api.oyez.org/cases?filter=term:{term}`) returns only basic data without audio
   - Document response format variations:
     - Some endpoints return lists, others return single objects
     - Audio data may be under "media_file", "oral_argument_audio", or other fields
     - Duration may be in "duration" or "size" fields
   - Create example JSON responses for each endpoint as reference during development
   - Map the relationship between cases, oral arguments, speakers, and utterances

2. **Domain Modeling**:

   - Define clear domain models that represent the business entities
   - Create separate API-level DTOs that handle the inconsistent API formats
   - Use data validation (e.g., Pydantic) to ensure data integrity
   - Include validators for business rules (e.g., end_time must be greater than start_time)

3. **Architecture Planning**:
   - Plan the layered architecture before implementation:
     - Infrastructure (API clients, storage, audio processing)
     - Domain models
     - Services
     - Dataset generation
     - CLI applications
   - Define clear interfaces between layers
   - Create a dependency graph to visualize module relationships

## Development Principles

1. **Incremental Development with Testing**:

   - Start with the infrastructure layer and build upward
   - Implement one small, testable component at a time
   - Write tests for each component before moving to the next
   - Verify that existing tests continue to pass with each change
   - Prioritize having a working end-to-end flow, even with limited functionality

2. **Single Responsibility Principle**:

   - Each module, class, and function should have exactly one responsibility
   - Split large, complex functions into smaller focused ones:
     - `_extract_speakers()` should only extract speakers
     - `_extract_utterances()` should only extract utterances
     - `_find_audio_url()` should only find audio URLs
   - Keep functions under 25 lines whenever possible
   - Use meaningful names that reflect specific responsibilities

3. **Robust Error Handling**:

   - Create custom exceptions for different error scenarios:
     - `OyezApiError` for API-related issues
     - `AudioProcessingError` for audio processing issues
     - `DataExtractionError` for data extraction issues
   - Implement proper retries with exponential backoff for network operations
   - Never use `contextlib.suppress()` without logging
   - Add detailed error context to help with debugging

4. **Code Organization**:

   - Organize code following the layered architecture
   - Use consistent naming patterns across similar components
   - Add docstrings to all public functions and classes explaining:
     - What the function does
     - Parameters and their purpose
     - Return values
     - Exceptions that might be raised
   - Include type hints for all function parameters and return values

5. **Incremental Refactoring**:
   - Refactor as you go, not at the end
   - When adding new functionality, first refactor existing code if needed
   - Use the "boy scout rule": Leave the code cleaner than you found it
   - Maintain test coverage during refactoring

## Implementation Workflow

For each feature you implement, follow this workflow:

1. **Plan**:

   - Define the feature's scope
   - Identify the modules that need to be created or modified
   - Define the interfaces between components
   - Document edge cases based on API investigation
   - Identify potential failure modes

2. **Test-First Development**:

   - Write tests for the feature before implementation
   - Use real API response examples from the docs directory as test fixtures
   - Include both happy path and error cases
   - Mock external dependencies

3. **Implement**:

   - Implement the core functionality
   - Add robust error handling
   - Add appropriate logging at different levels:
     - DEBUG for detailed tracing
     - INFO for normal operations
     - WARNING for potential issues
     - ERROR for failures
   - Follow the single responsibility principle
   - Keep functions small and focused
   - Include type hints and docstrings

4. **Validate**:

   - Run tests to verify functionality
   - Fix any failures
   - Check code coverage
   - Add additional tests if needed

5. **Refactor**:

   - Clean up the implementation
   - Eliminate code smells
   - Improve naming
   - Simplify complex expressions
   - Extract reusable components

6. **Document**:

   - Update documentation
   - Add code comments for complex logic
   - Document API usage patterns and workarounds

7. **Commit**:
   - Make a clean, atomic commit
   - Write a clear commit message describing the change

## Specific Guidelines for Oyez Scraping

1. **API Handling**:

   - Create separate client classes for different endpoint types:
     - Base API client with common functionality
     - Case client for case-related endpoints
     - Audio client for audio-related endpoints
   - Explicitly handle the two different case lookup behaviors:
     - Term-based lookup requires a follow-up direct case lookup to get audio data
     - Direct case lookup provides complete data in one call
   - Use rate limiting to avoid overwhelming the API
   - Implement caching to reduce redundant API calls
   - Handle list vs object response formats consistently

2. **Audio Processing**:

   - Use small, focused functions for audio manipulation
   - Decouple audio downloading from processing
   - Implement streaming download for large files to avoid memory issues
   - Add validation to ensure audio files are valid before processing
   - Handle cases where audio might be in different formats
   - Prefer FLAC format for speech content due to its lossless compression
   - Implement proper normalization for consistent audio levels
   - Include special handling for multi-channel audio conversion to mono
   - Use torchaudio for reliable audio processing operations

> **Implementation Note**: The `audio_io.py` module follows these guidelines with focused functions for different operations (loading, saving, format detection), comprehensive parameter validation, and proper error handling through custom exceptions that preserve the original error context.

3. **Complex Data Extraction**:

   - Create specialized parsers for complex nested structures
   - Implement robust extraction of speakers from different locations:
     - Extract from "sections" array
     - Extract from "transcript.sections" if available
   - Handle the different formats of speaker role information:
     - Sometimes in "roles[0].role_title"
     - Sometimes in other fields
   - Implement proper extraction of utterances with timing information

4. **Progress and Recovery**:
   - Implement checkpointing to allow interrupted operations to resume
   - Add progress indicators for long-running operations
   - Create a clean way to retry failed operations
   - Store intermediate results to avoid losing work

## Testing Best Practices

1. **Test Structure**:

   - Organize tests to match the code structure
   - Separate unit, integration, and end-to-end tests
   - Use fixtures based on real API responses from the docs directory
   - Use parametrized tests for testing multiple similar cases

2. **Mock External Dependencies**:

   - Create detailed mock API responses based on the actual examples in `docs/api_investigation/`
   - Use dependency injection to facilitate testing
   - Test edge cases like:
     - Empty responses
     - List vs single object responses
     - Missing fields
     - Unexpected field formats
   - Verify error handling works as expected

3. **Automated Testing**:

   - Set up CI/CD to run tests automatically
   - Include both fast unit tests and slower integration tests
   - Set standards for code coverage
   - Use pre-commit hooks to enforce testing before commits

4. **Real-World Testing**:
   - Create small end-to-end tests with real API access
   - Use them sparingly to validate the full system works
   - Document the expected output
   - Include tests for specific cases known to have unique formats

## Documentation Guidelines

1. **Code Documentation**:

   - Add docstrings to all public classes and functions
   - Include parameter descriptions and return values
   - Document exceptions that might be raised
   - Add examples for complex operations

2. **Project Documentation**:

   - Create a clear README with setup and usage instructions
   - Include architecture documentation
   - Document API inconsistencies and workarounds discovered during development
   - Provide examples of using the library

3. **API Documentation**:
   - Document the structure of the Oyez API:
     - Available endpoints
     - Response formats
     - Special cases and inconsistencies
   - Update the documentation as new API behaviors are discovered
   - Include example JSON responses
   - Document the relationships between API entities

## Progress Tracking

1. **Milestone Planning**:

   - Break the project into clear milestones aligned with the layered architecture:
     - Milestone 1: Infrastructure layer
     - Milestone 2: Domain models
     - Milestone 3: Services layer
     - Milestone 4: Dataset generation
     - Milestone 5: CLI applications
   - Each milestone should deliver working functionality
   - Prioritize core functionality first

2. **Feature Tracking**:
   - Track progress on individual features
   - Note any API inconsistencies discovered during implementation
   - Document decisions and trade-offs
   - Keep track of areas that need future improvement

## Guiding Principles for Decision Making

When making decisions during development, prioritize:

1. **Correctness**: The code must work correctly and handle all the API's quirks
2. **Robustness**: Handle errors and edge cases gracefully, especially API inconsistencies
3. **Testability**: Design for testability from the beginning
4. **Maintainability**: Write code that's easy to understand and modify
5. **Simplicity**: Prefer simple solutions over complex ones
6. **Performance**: Ensure the system performs well with large datasets

## Implementation Strategy

Start with a minimal viable product (MVP) that achieves basic functionality:

1. **MVP Phase (First 20% of effort):**

   - Base API client that handles both term lookup and direct case lookup
   - Simple domain models for cases, speakers, and utterances
   - Basic service to extract data from API responses
   - Minimal dataset generator that creates directory structure and metadata
   - Simple CLI to process a single case

2. **Enhancement Phase (Next 40% of effort):**

   - Add robust error handling and retries
   - Improve data extraction to handle edge cases
   - Add audio processing to extract utterance segments
   - Enhance documentation with examples

3. **Completion Phase (Final 40% of effort):**
   - Add advanced features like bulk processing
   - Implement different output formats
   - Add analytics and reporting
   - Complete documentation and examples

By following these guidelines and focusing on incremental development with a solid understanding of the API's peculiarities, you will create a high-quality, maintainable Oyez scraping project that successfully achieves its goal of creating an ASR/SID audio dataset.
