from __future__ import annotations

import csv
import json
import tempfile
import zipfile
import shutil
import subprocess
import sys
import os
from pathlib import Path
from typing import Any, Iterable, Iterator

from .errors import IngestionError, ValidationError


def find_datasets(data_dir: Path, names: tuple[str, ...], extensions: tuple[str, ...]) -> list[Path]:
    candidates: list[Path] = []
    for name in names:
        candidates.extend(data_dir.glob(name))
        if Path(name).suffix.lower() not in {extension.lower() for extension in extensions}:
            for extension in extensions:
                candidates.extend(data_dir.glob(f"{name}{extension}"))
    candidates = sorted(
        {
            path
            for path in candidates
            if path.is_file() and not path.name.lower().endswith(".schema.json")
        }
    )
    if not candidates:
        raise IngestionError(
            f"No dataset found in {data_dir}. Expected names {names} with extensions {extensions}."
        )
    return candidates


def find_dataset(data_dir: Path, names: tuple[str, ...], extensions: tuple[str, ...]) -> Path:
    return find_datasets(data_dir, names, extensions)[0]


def read_csv(path: Path) -> list[dict[str, Any]]:
    return list(read_csv_iter(path))


def read_csv_iter(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def read_xlsx(path: Path) -> list[dict[str, Any]]:
    try:
        import openpyxl
    except ImportError as exc:
        raise IngestionError("Census XLSX ingestion requires openpyxl.") from exc
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    headers = [str(value).strip() if value is not None else "" for value in next(rows)]
    return [dict(zip(headers, row, strict=False)) for row in rows if any(value is not None for value in row)]


def read_json_features(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Invalid GeoJSON file {path}: {exc}") from exc
    if payload.get("type") == "FeatureCollection":
        return payload.get("features", [])
    if payload.get("type") == "Feature":
        return [payload]
    raise ValidationError(f"{path} is not a GeoJSON Feature or FeatureCollection.")


def read_geo_features(path: Path) -> tuple[list[dict[str, Any]], int]:
    if path.suffix.lower() in {".geojson", ".json"}:
        return read_json_features(path), 4326
    if path.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory() as temporary:
            with zipfile.ZipFile(path) as archive:
                archive.extractall(temporary)
            files = list(Path(temporary).rglob("*.geojson")) + list(Path(temporary).rglob("*.json"))
            if files:
                return read_json_features(files[0]), 4326
            shapefiles = list(Path(temporary).rglob("*.shp"))
            if not shapefiles:
                raise ValidationError(f"Archive {path} contains no supported geospatial file.")
            return read_vector_with_pyogrio(shapefiles[0])
    return read_vector_with_pyogrio(path)


def iter_geo_features(path: Path, batch_size: int = 1000) -> Iterator[tuple[dict[str, Any], int]]:
    if path.suffix.lower() in {".geojson", ".json"}:
        for feature in read_json_features(path):
            yield feature, 4326
        return
    if path.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory() as temporary:
            with zipfile.ZipFile(path) as archive:
                archive.extractall(temporary)
            files = list(Path(temporary).rglob("*.geojson")) + list(Path(temporary).rglob("*.json"))
            if files:
                for feature in read_json_features(files[0]):
                    yield feature, 4326
                return
            shapefiles = list(Path(temporary).rglob("*.shp"))
            if not shapefiles:
                raise ValidationError(f"Archive {path} contains no supported geospatial file.")
            yield from iter_vector_features(shapefiles[0], batch_size)
        return
    yield from iter_vector_features(path, batch_size)


def iter_vector_features(path: Path, batch_size: int = 1000) -> Iterator[tuple[dict[str, Any], int]]:
    try:
        import pyogrio
    except ImportError as exc:
        raise IngestionError("SHP/ZIP ingestion requires pyogrio.") from exc
    info = pyogrio.read_info(path)
    source_crs = info.get("crs")
    if not source_crs:
        raise ValidationError(f"Dataset {path} has no identifiable CRS.")
    epsg = source_crs.to_epsg() if hasattr(source_crs, "to_epsg") else None
    if epsg is None:
        from pyproj import CRS

        epsg = CRS.from_user_input(source_crs).to_epsg()
    if epsg is None:
        raise ValidationError(f"Dataset {path} has no identifiable EPSG CRS.")
    offset = 0
    while True:
        frame = pyogrio.read_dataframe(
            path,
            skip_features=offset,
            max_features=batch_size,
        )
        if frame.empty:
            break
        for feature in json.loads(frame.to_json())["features"]:
            yield feature, epsg
        offset += len(frame)
        if len(frame) < batch_size:
            break


def read_vector_with_pyogrio(path: Path) -> tuple[list[dict[str, Any]], int]:
    try:
        import pyogrio
    except ImportError as exc:
        raise IngestionError("SHP/ZIP ingestion requires pyogrio.") from exc
    frame = pyogrio.read_dataframe(path)
    source_crs = getattr(frame, "crs", None)
    epsg = source_crs.to_epsg() if source_crs is not None else None
    if epsg is None:
        raise ValidationError(f"Dataset {path} has no identifiable CRS.")
    features = json.loads(frame.to_json())["features"]
    return features, epsg


def read_jsonl_iter(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return list(read_jsonl_iter(path))


def read_parquet(path: Path) -> list[dict[str, Any]]:
    return list(read_parquet_iter(path))


def read_parquet_iter(path: Path, batch_size: int = 2000) -> Iterator[dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise IngestionError("Parquet ingestion requires pyarrow.") from exc
    parquet_file = parquet.ParquetFile(path)
    for batch in parquet_file.iter_batches(batch_size=batch_size):
        yield from batch.to_pylist()


def find_7zip_executable() -> str | None:
    if sys.platform == "win32":
        standard_path = Path(r"C:\Program Files\7-Zip\7z.exe")
        if standard_path.is_file():
            return str(standard_path)
        for executable in ("7z", "7zz"):
            located = shutil.which(executable)
            if located:
                return located
        program_files = {
            os.environ.get("ProgramW6432"),
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        }
        for candidate in (
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
            *(
                Path(root) / "7-Zip" / "7z.exe"
                for root in program_files
                if root
            ),
            *(
                Path(root) / "7zip" / "7z.exe"
                for root in program_files
                if root
            ),
        ):
            if candidate.is_file():
                return str(candidate)
        registry_candidates = _find_7zip_from_registry()
        for candidate in registry_candidates:
            if candidate.is_file():
                return str(candidate)
        return None
    for executable in ("7z", "7zz"):
        located = shutil.which(executable)
        if located:
            return located
    return None


def _find_7zip_from_registry() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []

    locations: list[Path] = []
    registry_keys = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\7-Zip"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\7-Zip"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\7-Zip"),
    )
    for hive, key_path in registry_keys:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                install_location, _ = winreg.QueryValueEx(key, "Path")
        except (FileNotFoundError, OSError):
            continue
        if install_location:
            locations.append(Path(str(install_location)) / "7z.exe")
    return locations


def selected_7z_extractor() -> str:
    return "system 7-Zip" if find_7zip_executable() else "py7zr fallback"


def build_7zip_extract_command(executable: str, archive: Path, output_dir: Path) -> list[str]:
    return [
        executable,
        "x",
        str(archive),
        "-y",
        f"-o{output_dir}",
        "*.geojsonl",
    ]


def extract_7z(
    path: Path,
    cache: dict[str, Path] | None = None,
    *,
    require_system: bool = False,
) -> Path:
    path = Path(path)
    if not path.is_file():
        raise IngestionError(f"7z archive does not exist: {path}")
    cache_key = str(path.resolve())
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    temporary = Path(tempfile.mkdtemp(prefix="avasya-7z-"))
    executable = find_7zip_executable()
    if executable is None and require_system:
        raise IngestionError(
            "PMGSY extraction requires system 7-Zip (7z.exe/7zz.exe) for this large archive. "
            "Install 7-Zip and ensure it is available in one of the standard Windows locations or PATH."
        )
    if executable:
        command = build_7zip_extract_command(executable, path, temporary)
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise IngestionError(f"System 7-Zip could not be started for {path}: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise IngestionError(f"System 7-Zip failed to extract {path}: {detail}")
    else:
        try:
            import py7zr
        except ImportError as exc:
            raise IngestionError(
                "7z ingestion requires system 7-Zip (7z.exe/7zz.exe) or py7zr."
            ) from exc
        try:
            with py7zr.SevenZipFile(path, mode="r") as archive:
                names = [name for name in archive.getnames() if name.lower().endswith(".geojsonl")]
                if not names:
                    raise IngestionError(f"7z archive contains no GeoJSONL file: {path}")
                archive.extract(path=temporary, targets=names)
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError(f"py7zr failed to extract {path}: {exc}") from exc

    extracted = list(temporary.rglob("*.geojsonl"))
    if not extracted:
        raise IngestionError(f"7z archive contains no GeoJSONL file: {path}")
    if cache is not None:
        cache[cache_key] = temporary
    return temporary


def validate_required(row: dict[str, Any], fields: Iterable[str], context: str) -> None:
    missing = [field for field in fields if row.get(field) in (None, "")]
    if missing:
        raise ValidationError(f"{context}: missing required fields: {', '.join(missing)}")


def first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return None
