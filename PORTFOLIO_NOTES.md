# Portfolio Notes

## Problems solved
- Created a reproducible multi-source business dataset suitable for demonstrating an automated reporting pipeline.
- Added realistic data-quality failures so validation and anomaly handling can be demonstrated rather than merely described.

## Skills demonstrated
- Python data generation
- pandas
- SQLite
- deterministic test fixtures
- data modeling across multiple business domains
- pytest

## Architectural decisions
- Use four regional departments across two regions so dashboard filters and department comparisons are meaningful.
- Generate different source formats now to make the ETL milestone commercially realistic.
- Keep intentional bad data in raw sources; cleaning belongs in the ETL layer, not the generator.
- Use a fixed random seed so demos and tests are reproducible.

## Measurable business benefits to quantify later
- reporting preparation time reduced
- fewer manual spreadsheet errors
- faster detection of missed targets or deteriorating service levels

## Demo moments to capture later
- one-command data regeneration
- ETL rejecting impossible source values
- dashboard showing the Southwest staffing issue and downstream performance impact

## Potential Upwork proposal talking points
- Can consolidate CSV, API, and SQL data into a consistent reporting model.
- Separates deterministic business calculations from AI-generated narrative summaries.
