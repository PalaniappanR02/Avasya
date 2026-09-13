from __future__ import annotations

import argparse
import json
import os

from backend.core.database import SessionLocal

from .service import IngestionService


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest AVASYA source datasets.")
    parser.add_argument("command", choices=(
        "census", "boundaries", "vulnerability", "rainfall", "flood",
        "hospitals", "roads", "highways", "landslides", "cyclone", "all",
    ))
    parser.add_argument("--data-dir", default=os.getenv("DATA_DIR", "./data/raw"))
    args = parser.parse_args()
    with SessionLocal() as session:
        summary = IngestionService(session, args.data_dir).ingest(args.command)
    print(json.dumps(summary.as_dict(), indent=2))
    return 0 if not summary.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
