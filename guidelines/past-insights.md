# Past Insights from the Oyez Scraping Project

## Overview of Issues

The initial implementation of the Oyez scraping project faced several challenges that prevented it from achieving its goal of creating a clean, well-structured ASR/SID audio dataset. Here are the key insights gained from this experience.

## API Interaction Insights

1. **Inconsistent API Endpoints**:

   - Direct case lookup (`https://api.oyez.org/cases/{term}/{docket_number}`) returns complete case data with audio information
   - Term-based lookup (`https://api.oyez.org/cases?filter=term:{term}`) returns only summarized data without audio information
   - The code didn't properly handle this distinction, leading to inefficient multiple API calls

2. **Deeply Nested JSON Structure**:

   - API responses contain deeply nested structures (up to 5+ levels deep)
   - Speakers and roles appear in different formats across different endpoints
   - Case metadata is inconsistently structured between term lookups and case lookups

3. **Unreliable Field Names**:

   - Fields like 'duration' sometimes appear as 'size', audio files may be in different formats
   - Timestamps might use different units (seconds vs. milliseconds)
   - Audio URLs require following multiple 'href' links to access the actual media

4. **Rate Limiting Challenges**:

   - Without proper handling of rate limits, the scraper was prone to errors when making many requests in quick succession
   - The original implementation lacked proper backoff strategies

5. **Redundant API Calls**:
   - The code makes multiple calls to fetch similar data (as documented in api_notes.md)
   - Each case requires at least two API calls to get all necessary data

## Code Structure Problems

1. **Bloated Classes**:

   - Classes like `OyezScraper` and `OyezAPI` contain too much functionality
   - Methods in these classes frequently exceed 50+ lines, making them difficult to understand and test

2. **Duplicated Functionality**:

   - Audio extraction logic appears in both `AudioProcessor` class and as static methods
   - Similar data transformation logic is repeated across different modules

3. **Unclear Boundaries**:

   - Responsibilities between modules (api.py, scraper.py, audio.py) are not clearly defined
   - `OyezAPI` class handles both API requests and data transformation

4. **Monolithic Methods**:
   - Methods like `_extract_utterances` and `process_case` try to do too much at once
   - Many methods have multiple responsibilities, making them hard to test in isolation

## Error Handling Deficiencies

1. **Incomplete Error Recovery**:

   - While some retry logic exists in the `AudioStatsCollector`, other components lack robust error handling
   - Many errors that could be recoverable result in termination of the process

2. **Silent Failures**:

   - `contextlib.suppress()` is used to silently ignore exceptions in critical sections
   - Many exceptions are caught but not properly logged or handled

3. **Inconsistent Use of Exception Handling**:
   - Some areas use try/except, others use `contextlib.suppress()`, and others don't handle errors at all
   - No custom exception types to differentiate between different error scenarios

## Testing Challenges

1. **Difficult to Test**:

   - Large, monolithic functions with many responsibilities are difficult to test effectively
   - Complex nested data transformations make it hard to isolate specific logic for testing

2. **Insufficient Mocking**:

   - Tests don't properly mock the API responses to handle the different formats
   - Test fixtures don't accurately represent the complex nested structure of real API responses

3. **Integration Tests Mixed with Unit Tests**:
   - The test structure doesn't clearly separate unit and integration tests
   - Many "unit" tests actually require API access, making them slow and unreliable

## Data Handling Issues

1. **Complex Data Transformations**:

   - The code contains complex nested dictionary transformations that are hard to follow
   - Speaker and utterance extraction logic is particularly complex and fragile

2. **Inconsistent Data Models**:

   - The relationship between data models (e.g., OralArgument, Speaker, Utterance) and API responses is not clearly defined
   - No clear separation between API-level DTOs and domain models

3. **Inefficient Audio Processing**:
   - Audio processing loads entire files into memory, which is inefficient for large files
   - No streaming options for downloading or processing large audio files

## Development Process Insights

1. **Incremental Development Failures**:

   - The project tried to follow an incremental approach but didn't maintain clean interfaces between components
   - New functionality was added without proper refactoring of existing code

2. **Feature Creep**:

   - Functionality was continually added without refactoring, leading to bloated files
   - No clear definition of the minimum viable product (MVP)

3. **Missing Documentation**:

   - Poor documentation of API inconsistencies and how they're handled
   - Limited code comments to explain complex transformations

4. **Lack of Architectural Vision**:
   - No clear architectural pattern was followed, resulting in an ad-hoc design
   - No separation between infrastructure, domain, and application concerns

These insights, combined with the concrete API behavior documented in the `docs/api_investigation` folder, provide valuable lessons for the next iteration of the project, highlighting the need for better architecture, cleaner interfaces, and more consistent error handling.
