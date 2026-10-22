"""Opt-in post-run bridge: discover and validate source candidates from existing job JSON."""
from pathlib import Path
from typing import Any
import argparse, json

from .company_discovery import CompanyDiscovery, to_dict
from .ats_detector import ATSDetector
from .source_registry import SourceRegistry
from .source_validator import SourceValidator

def load_jobs(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("jobs", "raw_jobs", "results", "items"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
    raise ValueError(f"Unsupported JSON shape: {path}")

def register_from_jobs(jobs: list[dict[str, Any]], registry_path: str | Path = "data/sources/discovered_source_registry.json", validate: bool = True) -> dict[str, int]:
    discovery, detector = CompanyDiscovery(), ATSDetector()
    registry, validator = SourceRegistry(registry_path), SourceValidator()
    companies = discovery.discover_from_jobs(jobs)
    registered = verified = failed = unsupported = 0
    for company in companies:
        detected = detector.detect(company.careers_url)
        item = to_dict(company)
        item.update({"ats_platform": detected.platform, "board_token": detected.board_token,
                     "canonical_board_url": detected.canonical_board_url or company.careers_url,
                     "detection_method": detected.detection_method, "detection_confidence": detected.confidence})
        if detected.platform == "unknown":
            item.update({"validation_status": "unsupported", "validation_error": "ATS not recognized; needs a source-specific adapter"})
            registry.upsert(item)
            registered += 1
            unsupported += 1
            continue
        item = registry.upsert(item)
        registered += 1
        if validate:
            result = validator.validate(item)
            registry.update_validation(item["registry_key"], result)
            if result.get("verified"):
                verified += 1
            else:
                failed += 1
    return {"companies_discovered": len(companies), "sources_registered": registered,
            "sources_verified": verified, "sources_failed_validation": failed,
            "unsupported_sources_recorded": unsupported}

def main() -> None:
    parser = argparse.ArgumentParser(description="Register source candidates from JobPilot job JSON.")
    parser.add_argument("--jobs", default="data/jobs/raw_jobs.json")
    parser.add_argument("--registry", default="data/sources/discovered_source_registry.json")
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    result = register_from_jobs(load_jobs(args.jobs), args.registry, not args.skip_validation)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
