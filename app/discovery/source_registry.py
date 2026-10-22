"""Separate JSON registry for discovered sources; never writes to SQLite."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any
import json, re

DEFAULT_PATH = Path("data/sources/discovered_source_registry.json")

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().casefold()

class SourceRegistry:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"schema_version": 1, "sources": []})

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("sources"), list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"schema_version": 1, "sources": []}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def source_key(source: dict[str, Any]) -> str:
        platform = norm(str(source.get("ats_platform", "unknown")))
        token = norm(str(source.get("board_token", "")))
        url = str(source.get("canonical_board_url") or source.get("careers_url") or "").strip().rstrip("/").casefold()
        if platform != "unknown" and token:
            return f"{platform}:{token}"
        p = urlparse(url)
        return f"{platform}:{p.netloc}{p.path}" if p.netloc else f"{platform}:{norm(str(source.get('company_name', '')))}"

    def list_sources(self, status: str | None = None) -> list[dict[str, Any]]:
        rows = self._read()["sources"]
        if status:
            rows = [x for x in rows if x.get("validation_status") == status]
        return sorted(rows, key=lambda x: (norm(x.get("company_name", "")), x.get("ats_platform", "")))

    def upsert(self, source: dict[str, Any]) -> dict[str, Any]:
        item = dict(source)
        defaults = {
            "company_name": "", "ats_platform": "unknown", "board_token": "",
            "canonical_board_url": "", "careers_url": "", "discovery_method": "unknown",
            "discovered_from_url": "", "validation_status": "pending", "verified": False,
            "reachable": None, "http_status": None, "validation_error": "",
            "validation_method": "", "capabilities": [], "first_discovered_at": now_utc()
        }
        for key, value in defaults.items():
            item.setdefault(key, value)
        item["last_seen_at"] = now_utc()
        item["registry_key"] = self.source_key(item)
        data = self._read()
        idx = next((i for i, old in enumerate(data["sources"]) if old.get("registry_key") == item["registry_key"]), None)
        if idx is None:
            data["sources"].append(item)
        else:
            item["first_discovered_at"] = data["sources"][idx].get("first_discovered_at", item["first_discovered_at"])
            item = {**data["sources"][idx], **item}
            data["sources"][idx] = item
        self._write(data)
        return item

    def update_validation(self, registry_key: str, result: dict[str, Any]) -> dict[str, Any] | None:
        data = self._read()
        for i, item in enumerate(data["sources"]):
            if item.get("registry_key") == registry_key:
                item.update(result)
                item["last_validated_at"] = now_utc()
                data["sources"][i] = item
                self._write(data)
                return item
        return None
