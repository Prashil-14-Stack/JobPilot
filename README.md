# JobPilot

AI-assisted international job discovery and application intelligence platform.

## MVP 2 scope
1. Derive relevant job roles from the candidate profile.
2. Discover jobs across permitted/searchable sources.
3. Normalize and deduplicate listings.
4. Preserve international jobs even when visa sponsorship is not mentioned.
5. Exclude jobs only when sponsorship is explicitly unavailable (or another hard exclusion applies).
6. Export relevant jobs to Excel.

## Current milestone
MVP 2.1 — Candidate profile and role universe.

## Planned structure
- `app/discovery/` — source adapters and discovery orchestration
- `app/ai/` — JD analysis, role expansion, matching
- `app/models/` — job and candidate data models
- `app/services/` — persistence and business logic
- `data/` — local development data and exports
- `tests/` — automated tests
