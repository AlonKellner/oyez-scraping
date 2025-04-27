# Design Recommendations for Oyez Scraping Project

## Architectural Overview

For the next iteration of the Oyez scraping project, I recommend a modular, layered architecture with clear separation of concerns. This will make the code more maintainable, testable, and extensible.

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

## Key Design Principles

1. **Single Responsibility Principle**: Each module, class, and function should have a single, well-defined responsibility.

2. **Dependency Inversion**: High-level modules should not depend on low-level modules. Both should depend on abstractions.

3. **Interface Segregation**: Clients should not be forced to depend on methods they don't use. Break interfaces into smaller ones.

4. **Error Handling Strategy**: Consistent approach to error handling throughout the codebase, with proper logging and recovery.

5. **Testing First**: Design with testability in mind from the beginning.

## Module Structure

### Infrastructure Layer

#### `oyez_api/` - API Client Module

- `client.py`: Base API client with rate limiting, retries, and error handling
- `case_client.py`: Case-specific API endpoints (direct case and term-based lookups)
- `audio_client.py`: Audio-specific API endpoints
- `models.py`: API request/response models (using Pydantic)
- `exceptions.py`: API-specific exceptions
- `response_parsers.py`: Specialized parsers for different API response formats

> **Implementation Note**: A detailed design for API client refactoring is available in [docs/designs/api_client_refactoring.md](/workspaces/oyez-scraping/docs/designs/api_client_refactoring.md). This design addresses the need to break down the large `case_client.py` class and share common functionality like auto-pagination between `case_client.py` and `tracked_client.py`.

#### `storage/` - Storage Module

- `filesystem.py`: Filesystem storage implementation
- `models.py`: Storage models
- `exceptions.py`: Storage-specific exceptions

#### `processing/` - Audio Processing Module

- `audio_io.py`: Audio loading, saving with format handling and normalization
- `format_converter.py`: Convert between audio formats
- `models.py`: Processing models
- `exceptions.py`: Processing-specific exceptions

> **Implementation Note**: The `audio_io.py` module has been implemented following these design principles. It provides robust loading and saving of audio files with proper error handling, normalization, and support for different formats including FLAC, which is preferred for speech analysis. The implementation includes comprehensive tests and follows the error handling strategy defined in this document.

#### `monitoring/` - Monitoring and Observability

- `request_logger.py`: Tracks API requests and correlates them with output files
- `request_metadata.py`: Data models for request tracking
- `utility.py`: Utility functions for analyzing request logs

> **Implementation Note**: A detailed design for the request tracking and observability system is available in [docs/designs/request_tracking.md](/workspaces/oyez-scraping/docs/designs/request_tracking.md). This design addresses the need to track API requests and correlate them with their output files, enabling better debugging and monitoring.

### Core Domain Layer

#### `domain/` - Domain Models

- `case.py`: Case domain model
- `audio.py`: Audio domain model
- `transcript.py`: Transcript domain model
- `speaker.py`: Speaker domain model
- `utterance.py`: Utterance domain model

### Domain Services Layer

#### `services/` - Business Logic

- `case_service.py`: Case-related business logic
- `audio_service.py`: Audio-related business logic
- `analytics_service.py`: Statistics and reporting logic

### Dataset Generation Layer

#### `dataset/` - Dataset Generation

- `generator.py`: Main dataset generation logic
- `formatters/`: Different dataset output formats
  - `basic.py`: Simple directory structure with audio and transcripts
  - `sid.py`: Speaker identification format
  - `asr.py`: ASR training format

### Client Applications

#### `cli/` - Command Line Interface

- `main.py`: Entry point for CLI
- `commands/`: Command implementations

## Detailed Design Recommendations

### 1. API Client Design

Based on the API investigation in `docs/api_investigation`, the API client needs to handle the specific quirks of the Oyez API:

```python
# Example of the API client with proper handling of Oyez API peculiarities

from typing import Any, Dict, Optional, Union, List
import requests
from backoff import on_exception, expo
from ratelimit import limits, RateLimitException
from pydantic import BaseModel

class OyezApiClient:
    """Base client for Oyez API with retry and rate limiting."""

    def __init__(self, base_url: str = "https://api.oyez.org", request_delay: float = 1.0):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    @on_exception(expo, (requests.exceptions.RequestException, RateLimitException), max_tries=5)
    @limits(calls=1, period=1)  # Max 1 call per second
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request to the API with retries and rate limiting."""
        response = self.session.get(
            f"{self.base_url}/{endpoint}",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

class CaseApiClient:
    """Client for case-specific Oyez API endpoints."""

    def __init__(self, base_client: OyezApiClient):
        self.client = base_client

    def get_cases_by_term(self, term: str) -> List[Dict[str, Any]]:
        """Get cases for a specific term.

        Note: This endpoint returns basic case data WITHOUT audio information.
        """
        cases = self.client.get(f"cases", params={"filter": f"term:{term}"})
        return cases

    def get_case_by_id(self, term: str, docket_number: str) -> Dict[str, Any]]:
        """Get detailed case data by term and docket number.

        Note: This endpoint returns complete case data WITH audio information.
        """
        case_id = f"{term}/{docket_number}"
        case_data = self.client.get(f"cases/{case_id}")

        # Handle list response format (API sometimes returns a list)
        if isinstance(case_data, list):
            if not case_data:
                raise ValueError(f"No case data found for {case_id}")
            return case_data[0]

        return case_data

    def get_oral_argument_data(self, argument_url: str) -> Dict[str, Any]:
        """Get detailed oral argument data from its URL."""
        # Strip base URL if included in the argument_url
        if argument_url.startswith(self.client.base_url):
            argument_url = argument_url[len(self.client.base_url) + 1:]

        return self.client.get(argument_url)

class OralArgumentResponseDTO(BaseModel):
    """Data transfer object for oral argument API responses.

    This model handles the inconsistent response format from the API.
    """
    id: int
    title: str
    sections: List[Dict[str, Any]] = []
    transcript: Optional[Dict[str, Any]] = None
    media_file: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    duration: Optional[float] = None
    date: Optional[str] = None

    class Config:
        extra = "allow"  # Allow extra fields
```

### 2. Domain Model Design

Based on the API responses observed in the docs, here's an improved domain model:

```python
# Example of domain models that properly handle the Oyez API data

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

class Speaker(BaseModel):
    """Speaker in an oral argument."""
    identifier: str
    name: str
    role: str

class Utterance(BaseModel):
    """A single utterance in an oral argument."""
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    speaker: Speaker
    text: str
    section: Optional[str] = None
    speaker_turn: Optional[int] = None

    @validator('end_time')
    def end_time_must_be_greater_than_start_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v

class AudioFile(BaseModel):
    """Audio file metadata."""
    url: str
    mime_type: str = "audio/mpeg"
    duration: float  # in seconds
    size: Optional[int] = None  # in bytes

class OralArgument(BaseModel):
    """A complete oral argument session."""
    case_id: str
    case_name: str
    docket_number: str
    argument_date: datetime
    transcript_url: str
    audio: AudioFile
    speakers: List<Speaker>
    utterances: List<Utterance>
    term: Optional[str> = None
    description: Optional[str> = None

    def get_speaker_by_id(self, identifier: str) -> Optional[Speaker]:
        """Get a speaker by their identifier."""
        for speaker in self.speakers:
            if speaker.identifier == identifier:
                return speaker
        return None
```

### 3. Service Layer Design

The service layer needs to handle the complex extraction of data from the API responses:

```python
# Example of a service with specialized extraction methods

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import contextlib
from domain.case import OralArgument, Speaker, Utterance, AudioFile
from oyez_api.case_client import CaseApiClient
from oyez_api.audio_client import AudioApiClient
from oyez_api.exceptions import OyezApiError

class CaseService:
    """Service for retrieving and processing case data."""

    def __init__(self, case_client: CaseApiClient, audio_client: AudioApiClient):
        self.case_client = case_client
        self.audio_client = audio_client

    def get_case(self, term: str, docket_number: str) -> OralArgument:
        """Get a case with its oral argument data."""
        # Get detailed case data (includes audio information)
        case_data = self.case_client.get_case_by_id(term, docket_number)

        # Check if the case has oral arguments
        oral_args = case_data.get("oral_argument_audio", [])
        if not oral_args:
            raise ValueError(f"No oral argument found for case {term}/{docket_number}")

        # Get detailed oral argument data
        arg_data = self.case_client.get_oral_argument_data(oral_args[0]["href"])

        # Process case data to extract basic info
        case_basic_info = self._extract_basic_info(case_data)

        # Extract audio information
        audio_info = self._extract_audio_info(arg_data)

        # Extract speakers from the data
        speakers = self._extract_speakers(arg_data)

        # Extract utterances from the data
        utterances = self._extract_utterances(arg_data, speakers)

        # Return a complete OralArgument object
        return OralArgument(
            **case_basic_info,
            audio=audio_info,
            speakers=speakers,
            utterances=utterances
        )

    def _extract_basic_info(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic case information from case data."""
        return {
            "case_id": case_data.get("ID", ""),
            "case_name": case_data.get("name", "Unknown"),
            "docket_number": case_data.get("docket_number", "Unknown"),
            "argument_date": self._parse_date(case_data),
            "transcript_url": case_data.get("oral_argument_audio", [{}])[0].get("href", ""),
            "term": case_data.get("term", ""),
            "description": case_data.get("description", ""),
        }

    def _parse_date(self, case_data: Dict[str, Any]) -> datetime:
        """Parse date from case data."""
        # Implementation depends on the date format in the API
        # This is just a placeholder
        return datetime.now()

    def _extract_audio_info(self, arg_data: Dict[str, Any]) -> AudioFile:
        """Extract audio information from argument data."""
        audio_url, duration = self._find_audio_url(arg_data.get("media_file", []))

        if not audio_url:
            raise ValueError("Could not find valid audio URL")

        # Use fallback duration if not found in media_file
        if duration == 0.0 and "duration" in arg_data:
            with contextlib.suppress(ValueError, TypeError):
                duration = float(arg_data["duration"])

        return AudioFile(
            url=audio_url,
            duration=duration,
        )

    def _find_audio_url(self, media_files: Any) -> Tuple[str, float]:
        """Find the best audio URL and duration from media files."""
        audio_url = ""
        duration = 0.0

        # Handle the case where media_files is not a list
        if not isinstance(media_files, list):
            media_files = [media_files] if media_files else []

        # Prefer MP3 format if available
        for media in media_files:
            if not isinstance(media, dict):
                continue

            mime = media.get("mime", "")
            href = media.get("href", "")

            if "audio/mpeg" in mime or ".mp3" in href or "audio/" in mime:
                audio_url = href
                with contextlib.suppress(ValueError, TypeError):
                    if "size" in media:  # In some cases duration is labeled as size
                        duration = float(media.get("size", 0))
                    else:
                        duration = float(media.get("duration", 0))
                if audio_url:
                    break

        return audio_url, duration

    def _extract_speakers(self, arg_data: Dict[str, Any]) -> List[Speaker]:
        """Extract speakers from argument data."""
        speakers = []
        speaker_map = {}

        # Look in sections first
        for section in arg_data.get("sections", []):
            self._process_section_speakers(section, speakers, speaker_map)

        # Also check transcript section if available
        if "transcript" in arg_data and isinstance(arg_data["transcript"], dict):
            for section in arg_data["transcript"].get("sections", []):
                self._process_section_speakers(section, speakers, speaker_map)

        return speakers

    def _process_section_speakers(
        self, section: Dict[str, Any], speakers: List[Speaker], speaker_map: Dict[str, Speaker>
    ) -> None:
        """Process speakers in a section."""
        for turn in section.get("turns", []):
            spk = turn.get("speaker", {})
            if not spk or "identifier" not in spk:
                continue

            if spk["identifier"] not in speaker_map:
                speaker = Speaker(
                    name=spk.get("name", "Unknown"),
                    role=self._extract_role(spk),
                    identifier=spk["identifier"],
                )
                speakers.append(speaker)
                speaker_map[speaker.identifier] = speaker

    def _extract_role(self, speaker_data: Dict[str, Any>) -> str:
        """Extract role from speaker data."""
        if not speaker_data.get("roles"):
            return "Unknown"

        roles = speaker_data.get("roles", [{}])
        if isinstance(roles, list) and roles:
            return roles[0].get("role_title", "Unknown")

        return "Unknown"

    def _extract_utterances(
        self, arg_data: Dict[str, Any>, speakers: List[Speaker>
    ) -> List[Utterance]:
        """Extract utterances from argument data."""
        # Implementation would be similar to the original but with better error handling
        # This is just a placeholder
        return []
```

### 4. Dataset Generation Design

```python
# Example of a dataset generator with a clean interface

from typing import List, Optional, Dict, Any
from pathlib import Path
import json
from domain.case import OralArgument, Utterance
from services.case_service import CaseService
from processing.audio_processor import AudioProcessor
from storage.filesystem import FileSystemStorage

class DatasetGenerator:
    """Generates a dataset from Oyez oral arguments."""

    def __init__(
        self,
        case_service: CaseService,
        audio_processor: AudioProcessor,
        storage: FileSystemStorage,
        output_dir: Path
    ):
        self.case_service = case_service
        self.audio_processor = audio_processor
        self.storage = storage
        self.output_dir = output_dir

    def generate_from_case(self, term: str, docket_number: str) -> Path:
        """Generate dataset content from a single case."""
        # Get the case data
        case = self.case_service.get_case(term, docket_number)

        # Create the case directory
        case_dir = self._create_case_directory(case)

        # Download the audio file
        audio_path = self._download_audio(case, case_dir)

        # Process the audio and extract segments
        segments_dir = self._process_audio_segments(case, audio_path, case_dir)

        # Generate metadata
        self._generate_metadata(case, case_dir, audio_path)

        return case_dir

    def _create_case_directory(self, case: OralArgument) -> Path:
        """Create directory structure for a case."""
        # Handle slashes in case IDs
        safe_case_id = case.case_id.replace("/", "-")
        case_dir = self.output_dir / safe_case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        # Create segments directory
        segments_dir = case_dir / "segments"
        segments_dir.mkdir(exist_ok=True)

        return case_dir

    def _download_audio(self, case: OralArgument, case_dir: Path) -> Path:
        """Download audio for a case."""
        audio_path = case_dir / "full_audio.mp3"
        self.storage.download_file(case.audio.url, audio_path)
        return audio_path

    def _process_audio_segments(
        self, case: OralArgument, audio_path: Path, case_dir: Path
    ) -> Path:
        """Process audio and extract segments."""
        segments_dir = case_dir / "segments"

        # Load the audio file
        self.audio_processor.load_audio(audio_path)

        # Process each utterance
        for i, utterance in enumerate(case.utterances):
            segment_path = segments_dir / f"{i:04d}_{utterance.speaker.identifier}.flac"
            self.audio_processor.extract_utterance(utterance, segment_path)

        return segments_dir

    def _generate_metadata(
        self, case: OralArgument, case_dir: Path, audio_path: Path
    ) -> None:
        """Generate metadata files for the case."""
        metadata_path = case_dir / "metadata.json"

        # Calculate utterance metrics
        utterance_metrics = self._calculate_utterance_metrics(case.utterances, case.audio.duration)

        # Convert OralArgument to dict for JSON serialization
        metadata = {
            "case_id": case.case_id,
            "case_name": case.case_name,
            "docket_number": case.docket_number,
            "argument_date": case.argument_date.isoformat(),
            "transcript_url": case.transcript_url,
            "audio_url": case.audio.url,
            "duration": case.audio.duration,
            "term": case.term,
            "description": case.description,
            "speakers": [
                {
                    "name": s.name,
                    "role": s.role,
                    "identifier": s.identifier,
                }
                for s in case.speakers
            ],
            "utterance_metrics": utterance_metrics,
            "utterances": [
                {
                    "start_time": u.start_time,
                    "end_time": u.end_time,
                    "duration": u.end_time - u.start_time,
                    "speaker": u.speaker.identifier,
                    "text": u.text,
                    "section": u.section,
                    "speaker_turn": u.speaker_turn,
                    "audio_file": f"{i:04d}_{u.speaker.identifier}.flac",
                }
                for i, u in enumerate(case.utterances)
            ],
        }

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    def _calculate_utterance_metrics(
        self, utterances: List[Utterance>, total_duration: float
    ) -> Dict[str, Any>:
        """Calculate metrics about utterances."""
        # Implementation similar to original but better structured
        # This is just a placeholder
        return {
            "total_duration_seconds": total_duration,
            "total_utterance_time": sum(u.end_time - u.start_time for u in utterances),
            "utterance_count": len(utterances),
        }
```

## Testing Strategy

1. **Unit Tests**: Test individual components in isolation with proper mocking

   - Use detailed mock responses based on the real API examples in `docs/api_investigation/`
   - Test each layer with its dependencies mocked
   - Focus on business logic and edge cases

2. **Integration Tests**: Test interactions between components

   - Test API client against a mock server with realistic responses
   - Test storage operations with a test directory
   - Test audio processing with sample files

3. **End-to-end Tests**: Test complete workflows

   - Test the complete dataset generation process
   - Use a small sample of real or mock data

4. **Test Coverage**: Aim for high coverage of code
   - Target >90% coverage for core domain and services
   - Target >80% coverage for infrastructure

## Implementation Plan

1. **Phase 1: Infrastructure Layer**

   - Implement API client with proper error handling and rate limiting
   - Explicitly handle the different API endpoint behaviors discovered in the docs
   - Implement storage client for filesystem operations
   - Implement audio processing utilities

2. **Phase 2: Domain Layer**

   - Implement domain models with proper validation
   - Create DTOs for the specific Oyez API response formats

3. **Phase 3: Service Layer**

   - Implement case service with specialized methods for complex data extraction
   - Implement audio service for audio processing
   - Implement analytics service for statistics

4. **Phase 4: Dataset Generation**

   - Implement dataset generator
   - Implement formatters for different output formats

5. **Phase 5: Client Applications**
   - Implement CLI with progress indicators and checkpointing
   - Add commands for different use cases

By following this design, the next iteration of the Oyez scraping project will be more maintainable, testable, and extensible. The clear separation of concerns will make it easier to understand and modify the code, and the consistent error handling will make the scraper more robust.
