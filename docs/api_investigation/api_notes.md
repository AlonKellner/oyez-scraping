# Oyez API Behavior Notes

## API Endpoints Behavior

### Direct Case Lookup

- Endpoint: `https://api.oyez.org/cases/{term}/{docket_number}`
- Example: `https://api.oyez.org/cases/2022/21-1333`
- Returns complete case data including audio information
- Audio data is available in the `oral_argument_audio` and `opinion_announcement` fields
- This is the reliable source for audio data

### Term-Based Lookup

- Endpoint: `https://api.oyez.org/cases?filter=term:{term}`
- Example: `https://api.oyez.org/cases?filter=term:2022`
- Returns summarized case data without audio information
- The response includes basic case metadata (ID, name, docket number) but omits audio fields
- To get audio data, each case ID must be followed up with a direct case lookup

## API Discrepancy

The API has different behavior for different endpoints:

1. Term-based queries don't include audio fields in the response
2. Direct case lookups include complete audio metadata

For accurate audio stats collection, we must:

1. First query the term-based endpoint to get a list of cases
2. Then query the direct case endpoint for each case ID to get audio data
3. Aggregate results from the detailed case data

This explains why our tests pass when checking specific cases directly but fail when searching by term.
