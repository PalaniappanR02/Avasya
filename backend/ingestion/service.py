from __future__ import annotations

import hashlib
import json
import os
import base64
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping

from geoalchemy2.elements import WKTElement
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from backend.models import Evidence, Habitation, Hazard
from backend.models.enums import DataOrigin

from .errors import IngestionError, ValidationError
from .geometry import point_wkt
from .readers import (
    extract_7z,
    find_dataset,
    first_value,
    read_csv,
    read_csv_iter,
    read_geo_features,
    iter_geo_features,
    read_jsonl,
    read_jsonl_iter,
    read_parquet,
    read_parquet_iter,
    read_xlsx,
    find_datasets,
    validate_required,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestionSummary:
    dataset: str
    source: str
    inserted: int = 0
    updated: int = 0
    skipped_duplicates: int = 0
    rejected: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    discovered: int = 0
    processed: int = 0
    elapsed_seconds: float = 0.0
    file_summaries: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class IngestionService:
    def __init__(self, session: Session, data_dir: str | Path | None = None):
        self.session = session
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR", "./data/raw"))
        self._archive_extraction_cache: dict[str, Path] = {}

    def ingest(self, dataset: str) -> IngestionSummary:
        handlers: dict[str, Callable[[], IngestionSummary]] = {
            "census": self.ingest_census,
            "boundaries": self.ingest_boundaries,
            "vulnerability": self.ingest_vulnerability,
            "rainfall": self.ingest_rainfall,
            "flood": self.ingest_flood,
            "hospitals": self.ingest_hospitals,
            "roads": self.ingest_roads,
            "highways": self.ingest_highways,
            "landslides": self.ingest_landslides,
            "cyclone": self.ingest_cyclone,
        }
        if dataset == "all":
            summaries: list[IngestionSummary] = []
            for name, handler in handlers.items():
                try:
                    summaries.append(handler())
                except IngestionError as exc:
                    summaries.append(
                        IngestionSummary(
                            dataset=name,
                            source=str(self.data_dir),
                            errors=[str(exc)],
                        )
                    )
            return self._combine(summaries)
        try:
            started = time.perf_counter()
            summary = handlers[dataset]()
            if summary.elapsed_seconds == 0.0:
                summary.elapsed_seconds = round(time.perf_counter() - started, 3)
            return summary
        except KeyError as exc:
            raise IngestionError(f"Unsupported dataset command: {dataset}") from exc

    def ingest_census(self) -> IngestionSummary:
        path = find_dataset(self.data_dir, ("2011-IndiaStateDistSbDist-0000.xlsx",), (".xlsx", ".xls"))
        rows = read_xlsx(path)
        summary = self._summary("census", path)
        self._record_dataset_metadata("census", path, summary)
        for number, row in enumerate(rows, 1):
            row = self._normalized_row(row)
            name = self._text(row, ("name", "village_name", "habitation_name", "locality"))
            validate_required({"name": name}, ("name",), f"{path}:{number}")
            values = {
                "name": name,
                "village_or_ward": self._text(row, ("village_or_ward", "village", "ward", "town_village")),
                "district": self._text(row, ("district",)),
                "state": self._text(row, ("state",)),
                "population": self._non_negative_int(row, ("population", "tot_p")),
                "households": self._non_negative_int(row, ("households", "no_hh")),
                "latitude": None,
                "longitude": None,
                "geom": None,
                "data_origin": DataOrigin.REAL,
            }
            existing = self._find_habitation(values)
            if existing:
                for key, value in values.items():
                    if value is not None:
                        setattr(existing, key, value)
                summary.updated += 1
            else:
                self.session.add(Habitation(**values))
                summary.inserted += 1
        self.session.commit()
        return summary

    def ingest_boundaries(self) -> IngestionSummary:
        paths = find_datasets(
            self.data_dir,
            ("vb_soi_*_shp.zip", "vb_soi_*_geojson.zip"),
            (".geojson", ".json", ".shp", ".zip"),
        )
        summary = IngestionSummary(dataset="boundaries", source=";".join(str(path) for path in paths))
        for path in paths:
            started = time.perf_counter()
            file_summary = {
                "file": str(path),
                "discovered": 0,
                "processed": 0,
                "inserted": 0,
                "updated": 0,
                "skipped_duplicates": 0,
                "rejected": 0,
                "warnings": [],
                "errors": [],
            }
            try:
                feature_iter = iter_geo_features(path, batch_size=1000)
            except (IngestionError, ValidationError) as exc:
                summary.rejected += 1
                summary.errors.append(f"{path}: boundary dataset rejected: {exc}")
                summary.warnings.append(f"{path}: skipped; remaining boundary datasets will continue.")
                file_summary["errors"].append(str(exc))
                file_summary["rejected"] = 1
                file_summary["elapsed_seconds"] = round(time.perf_counter() - started, 3)
                summary.file_summaries.append(file_summary)
                continue
            self._record_dataset_metadata("boundaries", path, summary)
            pending: list[dict[str, Any]] = []
            try:
                for number, (feature, source_epsg) in enumerate(feature_iter, 1):
                    file_summary["discovered"] += 1
                    summary.discovered += 1
                    properties = feature.get("properties") or {}
                    geometry = feature.get("geometry") or {}
                    if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                        summary.rejected += 1
                        file_summary["rejected"] += 1
                        warning = f"{path}:{number}: skipped boundary with missing or unsupported geometry."
                        summary.warnings.append(warning)
                        file_summary["warnings"].append(warning)
                        continue
                    try:
                        centroid = self._centroid(feature, source_epsg)
                        values = {
                            "name": self._text(properties, ("name", "village", "habitation_name")),
                            "village_or_ward": self._text(properties, ("village", "ward")),
                            "district": self._text(properties, ("district",)),
                            "state": self._text(properties, ("state",)),
                            "latitude": centroid[1],
                            "longitude": centroid[2],
                            "geom": WKTElement(centroid[0], srid=4326),
                            "data_origin": DataOrigin.REAL,
                        }
                        validate_required(values, ("name", "district", "state"), f"{path}:{number}")
                        pending.append(values)
                    except (TypeError, ValueError, ValidationError) as exc:
                        summary.rejected += 1
                        file_summary["rejected"] += 1
                        warning = f"{path}:{number}: skipped invalid boundary feature: {exc}"
                        summary.warnings.append(warning)
                        file_summary["warnings"].append(warning)
                    if len(pending) >= 1000:
                        self._persist_boundary_batch(pending, summary, file_summary)
                        pending.clear()
                    if number % 1000 == 0:
                        logger.info("Boundary progress file=%s discovered=%d", path.name, number)
                if pending:
                    self._persist_boundary_batch(pending, summary, file_summary)
            except (IngestionError, ValidationError) as exc:
                summary.errors.append(f"{path}: boundary dataset failed: {exc}")
                file_summary["errors"].append(str(exc))
            file_summary["processed"] = file_summary["discovered"] - file_summary["rejected"]
            file_summary["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            summary.processed += file_summary["processed"]
            summary.file_summaries.append(file_summary)
        summary.elapsed_seconds = round(sum(item["elapsed_seconds"] for item in summary.file_summaries), 3)
        self.session.commit()
        return summary

    def _persist_boundary_batch(
        self,
        values: list[dict[str, Any]],
        summary: IngestionSummary,
        file_summary: dict[str, Any],
    ) -> None:
        from sqlalchemy import tuple_

        keys = [(value["name"], value["district"], value["state"]) for value in values]
        existing = self.session.scalars(
            select(Habitation).where(
                tuple_(Habitation.name, Habitation.district, Habitation.state).in_(keys)
            )
        ).all()
        existing_by_key = {
            (row.name, row.district, row.state): row
            for row in existing
        }
        for value in values:
            row = existing_by_key.get((value["name"], value["district"], value["state"]))
            if row is not None:
                for key, item in value.items():
                    if item is not None:
                        setattr(row, key, item)
                summary.updated += 1
                file_summary["updated"] += 1
            else:
                self.session.add(Habitation(**value))
                summary.inserted += 1
                file_summary["inserted"] += 1
        self.session.flush()

    def ingest_vulnerability(self) -> IngestionSummary:
        return self._ingest_evidence_csv(
            "vulnerability",
            (
                "climate-vulnerability-indicators-district-wise",
                "climate_vulnerability",
                "vulnerability",
            ),
            "climate_vulnerability",
        )

    def ingest_rainfall(self) -> IngestionSummary:
        return self._ingest_evidence_csv("rainfall", ("rainfall_statewise_daily_imd.csv",), "imd_rainfall")

    def ingest_hospitals(self) -> IngestionSummary:
        return self._ingest_evidence_csv("hospitals", ("hospital_directory.csv",), "hospital")

    def ingest_roads(self) -> IngestionSummary:
        path = find_dataset(self.data_dir, ("pmgsy_roads.geojsonl.7z",), (".7z",))
        if path.suffix.lower() == ".7z":
            path = next(
                extract_7z(path, self._archive_extraction_cache, require_system=True).rglob("*.geojsonl"),
                None,
            )
            if path is None:
                raise IngestionError("PMGSY archive contains no GeoJSONL file.")
        rows = (
            read_jsonl_iter(path)
            if path.suffix.lower() in {".geojsonl", ".jsonl"}
            else read_geo_features(path)[0]
        )
        return self._ingest_evidence_rows("roads", path, rows, "pmgsy_roads")

    def ingest_highways(self) -> IngestionSummary:
        path = find_dataset(self.data_dir, ("GatiShakti_MORTH_National_Highways.parquet",), (".parquet",))
        return self._ingest_evidence_rows("highways", path, read_parquet_iter(path), "national_highways")

    def ingest_landslides(self) -> IngestionSummary:
        paths = find_datasets(self.data_dir, ("*Susceptibility Map.pdf",), (".pdf",))
        summary = IngestionSummary(
            dataset="landslide_susceptibility",
            source=";".join(str(path) for path in paths),
        )
        for path in paths:
            try:
                item = self._ingest_pdf_evidence("landslide_susceptibility", path)
            except IngestionError as exc:
                summary.rejected += 1
                summary.errors.append(f"{path}: {exc}")
                continue
            summary.inserted += item.inserted
            summary.skipped_duplicates += item.skipped_duplicates
            summary.warnings.extend(item.warnings)
            summary.errors.extend(item.errors)
        return summary

    def ingest_cyclone(self) -> IngestionSummary:
        pdfs = find_datasets(self.data_dir, ("*.pdf",), (".pdf",))
        candidates = [
            candidate
            for candidate in pdfs
            if "susceptibility map" not in candidate.name.lower()
        ]
        if not candidates:
            raise IngestionError(
                f"No cyclone PDF found in {self.data_dir}; all PDFs matched landslide susceptibility files."
            )
        path = candidates[0]
        return self._ingest_pdf_evidence("cyclone_imd", path)

    def ingest_flood(self) -> IngestionSummary:
        path = find_dataset(self.data_dir, ("INDIA_FLOOD_INVENTORY_V3.geojson",), (".geojson",))
        summary = self._summary("flood", path)
        self._record_dataset_metadata("flood", path, summary)
        non_point_warning_added = False
        evidence_batch: list[dict[str, Any]] = []
        for number, (feature, source_epsg) in enumerate(iter_geo_features(path, 500), 1):
            summary.discovered += 1
            geometry = feature.get("geometry") or {}
            try:
                if geometry.get("type") == "Point":
                    wkt, _, _ = point_wkt(feature, source_epsg)
                    self.session.add(Hazard(
                        hazard_type="FLOOD",
                        hazard_name=str((feature.get("properties") or {}).get("name") or "flood"),
                        description="India Flood Inventory feature",
                        geom=WKTElement(wkt, srid=4326),
                        data_origin=DataOrigin.REAL,
                    ))
                    summary.inserted += 1
                elif geometry.get("type") in {"Polygon", "MultiPolygon", "LineString", "MultiLineString"}:
                    evidence_batch.append(feature)
                    if not non_point_warning_added:
                        summary.warnings.append(
                            "Non-point flood geometries were preserved as evidence because hazards.geom is point-only."
                        )
                        non_point_warning_added = True
                else:
                    summary.rejected += 1
                    summary.warnings.append(f"{path}:{number}: invalid or unsupported flood geometry.")
                    continue
                summary.processed += 1
            except (TypeError, ValueError, ValidationError) as exc:
                summary.rejected += 1
                summary.warnings.append(f"{path}:{number}: skipped invalid flood feature: {exc}")
            if len(evidence_batch) >= 500:
                self._persist_evidence_batch("flood", path, evidence_batch, "india_flood_inventory", summary)
                evidence_batch.clear()
            if number % 500 == 0:
                logger.info("Flood progress file=%s discovered=%d", path.name, number)
        if evidence_batch:
            self._persist_evidence_batch("flood", path, evidence_batch, "india_flood_inventory", summary)
        self.session.commit()
        return summary

    def _ingest_evidence_csv(self, dataset: str, names: tuple[str, ...], source_name: str) -> IngestionSummary:
        path = find_dataset(self.data_dir, names, (".csv",))
        return self._ingest_evidence_rows(dataset, path, read_csv_iter(path), source_name)

    def _ingest_evidence_rows(
        self,
        dataset: str,
        path: Path,
        rows: Iterable[dict[str, Any]],
        source_name: str,
        batch_size: int = 2000,
    ) -> IngestionSummary:
        summary = self._summary(dataset, path)
        self._record_dataset_metadata(dataset, path, summary)
        batch: list[dict[str, Any]] = []
        for number, row in enumerate(rows, 1):
            summary.discovered += 1
            if not row:
                summary.rejected += 1
                summary.warnings.append(f"{path}:{number}: empty record.")
                continue
            normalized = self._normalized_row(row)
            try:
                self._validate_evidence_row(dataset, normalized, f"{path}:{number}")
            except ValidationError as exc:
                summary.rejected += 1
                summary.warnings.append(str(exc))
                continue
            batch.append(normalized)
            summary.processed += 1
            if len(batch) >= batch_size:
                self._persist_evidence_batch(dataset, path, batch, source_name, summary)
                batch.clear()
        if batch:
            self._persist_evidence_batch(dataset, path, batch, source_name, summary)
        self.session.commit()
        return summary

    def _ingest_pdf_evidence(self, dataset: str, path: Path) -> IngestionSummary:
        summary = self._summary(dataset, path)
        self._record_dataset_metadata(dataset, path, summary)
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise IngestionError("PDF evidence ingestion requires pypdf.") from exc
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self._add_evidence(
            dataset,
            path,
            {"page_count": len(reader.pages), "text": text},
            dataset,
            summary,
        )
        self.session.commit()
        return summary

    def _record_dataset_metadata(self, dataset: str, path: Path, summary: IngestionSummary) -> None:
        payload = {
            "dataset": dataset,
            "version_or_date": date.fromtimestamp(path.stat().st_mtime).isoformat(),
            "data_origin": DataOrigin.REAL.value,
            "source_path": str(path),
            "metadata_record": True,
        }
        self._add_evidence(dataset, path, payload, dataset, summary)

    def _add_evidence(self, dataset: str, path: Path, payload: Any, source_name: str, summary: IngestionSummary) -> None:
        serializable_payload = self._json_safe(payload)
        encoded = json.dumps(serializable_payload, sort_keys=True)
        external_reference = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        existing = self.session.scalar(
            select(Evidence).where(
                Evidence.source_name == source_name,
                Evidence.external_reference == external_reference,
            )
        )
        if existing:
            summary.skipped_duplicates += 1
            return
        self.session.add(Evidence(
            source_name=source_name,
            source_type=path.suffix.lower().lstrip("."),
            evidence_type=dataset,
            summary=f"{dataset} source record",
            evidence_payload={
                "dataset": dataset,
                "version_or_date": date.today().isoformat(),
                "data_origin": DataOrigin.REAL.value,
                "source_path": str(path),
                "record": serializable_payload,
            },
            external_reference=external_reference,
            data_origin=DataOrigin.REAL,
        ))
        summary.inserted += 1

    def _persist_evidence_batch(
        self,
        dataset: str,
        path: Path,
        rows: list[dict[str, Any]],
        source_name: str,
        summary: IngestionSummary,
    ) -> None:
        records: list[dict[str, Any]] = []
        hashes: list[str] = []
        seen: set[str] = set()
        for row in rows:
            serializable_payload = self._json_safe(row)
            encoded = json.dumps(serializable_payload, sort_keys=True)
            external_reference = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            if external_reference in seen:
                summary.skipped_duplicates += 1
                continue
            seen.add(external_reference)
            hashes.append(external_reference)
            records.append(
                {
                    "source_name": source_name,
                    "source_type": path.suffix.lower().lstrip("."),
                    "evidence_type": dataset,
                    "summary": f"{dataset} source record",
                    "evidence_payload": {
                        "dataset": dataset,
                        "version_or_date": date.today().isoformat(),
                        "data_origin": DataOrigin.REAL.value,
                        "source_path": str(path),
                        "record": serializable_payload,
                    },
                    "external_reference": external_reference,
                    "data_origin": DataOrigin.REAL,
                }
            )

        if not records:
            return

        existing_hashes = set(
            self.session.scalars(
                select(Evidence.external_reference).where(
                    Evidence.source_name == source_name,
                    Evidence.external_reference.in_(hashes),
                )
            ).all()
        )
        new_records = [
            record
            for record in records
            if record["external_reference"] not in existing_hashes
        ]
        summary.skipped_duplicates += len(records) - len(new_records)
        if new_records:
            self.session.execute(insert(Evidence), new_records)
            self.session.flush()
            summary.inserted += len(new_records)

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, bytes):
            try:
                from shapely.geometry import mapping
                from shapely.errors import GEOSException
                from shapely.wkb import loads
            except ImportError:
                return {
                    "type": "Binary",
                    "format": "base64",
                    "value": base64.b64encode(value).decode("ascii"),
                }
            try:
                geometry = loads(value)
                return {
                    "type": "Geometry",
                    "format": "GeoJSON",
                    "value": mapping(geometry),
                }
            except (ValueError, TypeError, GEOSException):
                return {
                    "type": "Binary",
                    "format": "base64",
                    "value": base64.b64encode(value).decode("ascii"),
                }
        if isinstance(value, Mapping):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if hasattr(value, "item"):
            return self._json_safe(value.item())
        if hasattr(value, "isoformat"):
            return value.isoformat()
        raise ValidationError(f"Unsupported value in evidence payload: {type(value).__name__}")

    def _normalized_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            str(key).strip().lower().replace(" ", "_").replace("-", "_"): value
            for key, value in row.items()
            if key not in (None, "")
        }

    def _validate_evidence_row(self, dataset: str, row: dict[str, Any], context: str) -> None:
        if dataset == "roads":
            if "geometry" not in row or not row["geometry"]:
                raise ValidationError(f"{context}: road feature is missing geometry.")
            return
        if dataset == "highways":
            if not any(row.get(key) not in (None, "") for key in ("id", "highway_id", "road_id", "name")):
                raise ValidationError(f"{context}: highway record is missing a stable identifier or name.")
            return
        requirements = {
            "vulnerability": (("state_name", "state"), ("district_name", "district")),
            "rainfall": (("state",), ("date",)),
            # Coordinates are useful when present, but missing hospital coordinates
            # must not discard the otherwise useful directory record.
            "hospitals": (("hospital_name", "name"),),
        }.get(dataset)
        if requirements:
            for aliases in requirements:
                if not any(row.get(alias) not in (None, "") for alias in aliases):
                    raise ValidationError(
                        f"{context}: missing required field group ({', '.join(aliases)})."
                    )

    def _summary(self, dataset: str, path: Path) -> IngestionSummary:
        return IngestionSummary(dataset=dataset, source=str(path))

    def _find_habitation(self, values: dict[str, Any]) -> Habitation | None:
        statement = select(Habitation).where(
            Habitation.name == values["name"],
            Habitation.district == values.get("district"),
            Habitation.state == values.get("state"),
        )
        return self.session.scalar(statement)

    def _point_from_row(self, row: dict[str, Any], context: str) -> tuple[str, float, float]:
        longitude = first_value(row, ("longitude", "lon", "lng"))
        latitude = first_value(row, ("latitude", "lat"))
        if longitude in (None, "") or latitude in (None, ""):
            raise ValidationError(f"{context}: latitude and longitude are required; missing is not zero.")
        feature = {"geometry": {"type": "Point", "coordinates": [float(longitude), float(latitude)]}}
        return point_wkt(feature, 4326)

    def _centroid(self, feature: dict[str, Any], source_epsg: int) -> tuple[str, float, float]:
        try:
            from shapely.geometry import shape
            from shapely.errors import GEOSException
            from shapely.ops import transform
            from pyproj import Transformer
        except ImportError as exc:
            raise IngestionError("Boundary ingestion requires shapely and pyproj.") from exc
        try:
            geometry = shape(feature["geometry"])
            if geometry.is_empty or not geometry.is_valid:
                raise ValidationError("Boundary geometry is empty or invalid.")
            if source_epsg != 4326:
                transformer = Transformer.from_crs(source_epsg, 4326, always_xy=True)
                geometry = transform(transformer.transform, geometry)
            centroid = geometry.centroid
        except (GEOSException, TypeError, ValueError) as exc:
            raise ValidationError(f"Boundary geometry is invalid: {exc}") from exc
        if centroid.is_empty or not centroid.is_valid:
            raise ValidationError("Boundary centroid is empty or invalid.")
        return f"SRID=4326;POINT({centroid.x} {centroid.y})", centroid.x, centroid.y

    def _text(self, row: dict[str, Any], aliases: tuple[str, ...]) -> str | None:
        value = first_value(row, aliases)
        return str(value).strip() if value not in (None, "") else None

    def _non_negative_int(self, row: dict[str, Any], aliases: tuple[str, ...]) -> int | None:
        value = first_value(row, aliases)
        if value in (None, ""):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid integer value {value!r}.") from exc
        if parsed < 0:
            raise ValidationError(f"Negative values are invalid: {value!r}.")
        return parsed

    def _combine(self, summaries: list[IngestionSummary]) -> IngestionSummary:
        combined = IngestionSummary(dataset="all", source=str(self.data_dir))
        for summary in summaries:
            combined.inserted += summary.inserted
            combined.updated += summary.updated
            combined.skipped_duplicates += summary.skipped_duplicates
            combined.rejected += summary.rejected
            combined.discovered += summary.discovered
            combined.processed += summary.processed
            combined.elapsed_seconds += summary.elapsed_seconds
            combined.warnings.extend(summary.warnings)
            combined.errors.extend(summary.errors)
            combined.file_summaries.extend(summary.file_summaries)
        return combined
