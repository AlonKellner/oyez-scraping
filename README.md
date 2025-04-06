# Oyez Audio Dataset Generator

A modular, well-tested Python toolkit for creating high-quality ASR/SID (Automatic Speech Recognition/Speaker Identification) datasets by scraping the [Oyez Project](https://www.oyez.org/) website.

## Project Overview

This project aims to create a comprehensive audio dataset containing oral arguments and opinion announcements from the United States Supreme Court, leveraging the high-quality labels provided by the Oyez Project. The dataset includes:

- Audio recordings in FLAC format
- Speaker diarization with accurate timing information
- High-quality speaker labels and roles
- Complete transcriptions
- Rich metadata about cases and participants

## Project Goals

1. Create a clean, well-structured dataset suitable for training ASR and SID models
2. Handle the complex and inconsistent Oyez API with robust error handling
3. Demonstrate incremental development with comprehensive testing
4. Provide a modular architecture that separates concerns for maintainability
5. Document the Oyez API behavior for future developers

## Architecture

The project follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Applications                     │
└─────────────────────────────────────────────────────────────┘
                               ▲
                               │
┌─────────────────────────────┼─────────────────────────────┐
│                             │                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                 Dataset Generation                  │  │
│  └─────────────────────────────────────────────────────┘  │
│                             ▲                             │
│                             │                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                  Domain Services                     │  │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────┐  │  │
│  │  │ Case Service  │ │ Audio Service │ │ Analytics │  │  │
│  │  └───────────────┘ └───────────────┘ └───────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                             ▲                             │
│                             │                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                   Core Domain                        │  │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────┐  │  │
│  │  │  Case Models  │ │ Audio Models  │ │ Transcript│  │  │
│  │  └───────────────┘ └───────────────┘ └───────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                             ▲                             │
│                             │                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                  Infrastructure                      │  │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────┐  │  │
│  │  │   API Client  │ │ Storage Client│ │ Processing│  │  │
│  │  └───────────────┘ └───────────────┘ └───────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Key Components

1. **Infrastructure Layer**

   - API clients for interacting with the Oyez API
   - Storage modules for managing files
   - Audio processing utilities based on `torchaudio`

2. **Core Domain Layer**

   - Domain models representing cases, audio, transcripts, speakers, and utterances
   - Data validation and business rules

3. **Domain Services Layer**

   - Business logic for working with cases, audio, and analytics
   - Data transformation and extraction

4. **Dataset Generation Layer**

   - Dataset creation and formatting
   - Quality control and validation

5. **Client Applications**
   - Command line interface for dataset generation

## Development Approach

This project follows these development principles:

1. **Incremental Development**

   - Implementing one small, testable component at a time
   - Verifying that existing tests pass before moving on
   - Focusing on having a working end-to-end flow, even with limited functionality

2. **Clean Code Practices**

   - Following the Single Responsibility Principle
   - Keeping functions under 25 lines whenever possible
   - Using meaningful and descriptive names

3. **Robust Error Handling**

   - Creating appropriate custom exceptions for different error scenarios
   - Implementing proper retries with backoff for network operations
   - Adding contextual information to error messages

4. **Comprehensive Testing**
   - Writing tests before implementation when possible
   - Separating unit, integration, and end-to-end tests
   - Mocking external dependencies appropriately

## Getting Started

### Prerequisites

- Python 3.9+
- Docker (optional, for containerized execution)

### Installation

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/oyez-scraping.git
   cd oyez-scraping
   ```

2. Install dependencies:

   ```
   pip install -e .
   ```

3. Run the pre-commit setup:
   ```
   pre-commit install
   ```

### Usage

Basic usage examples will be provided as the project develops.

## Project Status

This project is currently in the second iteration of development, focusing on a modular and well-tested implementation that learns from the issues identified in the first iteration.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [The Oyez Project](https://www.oyez.org/) for providing access to Supreme Court audio and transcripts
- All contributors to this open-source project
