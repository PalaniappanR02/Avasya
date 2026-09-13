from __future__ import annotations

import json
import builtins
import sys
from types import SimpleNamespace

import pytest
from shapely.geometry import Point
from shapely.wkb import dumps

from backend.ingestion.errors import IngestionError, ValidationError
from backend.ingestion.geometry import point_wkt
from backend.ingestion.readers import (
    build_7zip_extract_command,
    extract_7z,
    find_7zip_executable,
    find_dataset,
    find_datasets,
    read_csv,
    read_xlsx,
    selected_7z_extractor,
)
from backend.ingestion.service import IngestionService


def test_point_crs_validation_rejects_non_point() -> None:
    with pytest.raises(ValidationError):
        point_wkt({"geometry": {"type": "Polygon", "coordinates": []}}, 4326)


def test_point_crs_conversion() -> None:
    wkt, longitude, latitude = point_wkt(
        {"geometry": {"type": "Point", "coordinates": [0, 0]}}, 4326
    )
    assert wkt == "SRID=4326;POINT(0.0 0.0)"
    assert (longitude, latitude) == (0.0, 0.0)


def test_missing_coordinates_are_not_zero(tmp_path) -> None:
    service = IngestionService(session=None, data_dir=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="missing is not zero"):
        service._point_from_row({"name": "Village"}, "row 1")


def test_census_rows_without_coordinates_ingest_with_null_geometry(tmp_path) -> None:
    census = tmp_path / "2011-IndiaStateDistSbDist-0000.xlsx"
    census.write_bytes(b"fixture")

    class FakeSession:
        def __init__(self) -> None:
            self.records = []

        def add(self, record) -> None:
            self.records.append(record)

        def scalar(self, _statement):
            return None

        def commit(self) -> None:
            return None

    service = IngestionService(session=FakeSession(), data_dir=tmp_path)  # type: ignore[arg-type]
    service._record_dataset_metadata = lambda *_args: None  # type: ignore[method-assign]
    service._find_habitation = lambda _values: None  # type: ignore[method-assign]
    service._normalized_row = lambda row: row  # type: ignore[method-assign]
    service._text = lambda row, aliases: row.get(aliases[0])  # type: ignore[method-assign]
    service._non_negative_int = lambda row, aliases: row.get(aliases[0])  # type: ignore[method-assign]

    import backend.ingestion.service as service_module

    original_read_xlsx = service_module.read_xlsx
    service_module.read_xlsx = lambda _path: [
        {
            "name": "Village A",
            "district": "Bengaluru",
            "state": "Karnataka",
            "population": 100,
            "households": 25,
        }
    ]
    try:
        summary = service.ingest_census()
    finally:
        service_module.read_xlsx = original_read_xlsx

    assert summary.inserted == 1
    assert service.session.records[0].geom is None
    assert service.session.records[0].latitude is None
    assert service.session.records[0].longitude is None
    assert service.session.records[0].population == 100
    assert service.session.records[0].households == 25


def test_boundary_ingestion_rejects_invalid_features_and_keeps_valid_ones(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "vb_soi_ka_shp.zip"
    archive.write_bytes(b"fixture")

    class FakeSession:
        def __init__(self) -> None:
            self.records = []

        def add(self, record) -> None:
            self.records.append(record)

        def scalars(self, _statement):
            return _FakeScalarResult([])

        def flush(self) -> None:
            return None

        def commit(self) -> None:
            return None

    class _FakeScalarResult:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    service = IngestionService(session=FakeSession(), data_dir=tmp_path)  # type: ignore[arg-type]
    service._record_dataset_metadata = lambda *_args: None  # type: ignore[method-assign]
    service._find_habitation = lambda _values: None  # type: ignore[method-assign]
    monkeypatch.setattr(
        "backend.ingestion.service.iter_geo_features",
        lambda _path, batch_size=1000: iter(
            [
                (
                    {
                        "properties": {"name": "Valid", "district": "D", "state": "S"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[77.0, 12.0], [77.1, 12.0], [77.0, 12.1], [77.0, 12.0]]],
                        },
                    },
                    4326,
                ),
                (
                    {
                        "properties": {"name": "Invalid", "district": "D", "state": "S"},
                        "geometry": None,
                    },
                    4326,
                ),
            ]
        ),
    )

    summary = service.ingest_boundaries()

    assert summary.inserted == 1
    assert summary.rejected == 1
    assert len(service.session.records) == 1
    assert any("missing or unsupported geometry" in warning for warning in summary.warnings)


def test_all_landslide_susceptibility_pdfs_are_discovered(tmp_path) -> None:
    for name in (
        "Charmadi Ghat Stretch of NH-73 Area Susceptibility Map.pdf",
        "Kattippara Chamal Susceptibility Map.pdf",
        "Tirumala Hills Susceptibility Map.pdf",
    ):
        (tmp_path / name).write_bytes(b"pdf")

    paths = find_datasets(tmp_path, ("*Susceptibility Map.pdf",), (".pdf",))

    assert [path.name for path in paths] == [
        "Charmadi Ghat Stretch of NH-73 Area Susceptibility Map.pdf",
        "Kattippara Chamal Susceptibility Map.pdf",
        "Tirumala Hills Susceptibility Map.pdf",
    ]


def test_evidence_duplicate_hash_is_stable() -> None:
    payload = {"dataset": "rainfall", "value": 12}
    first = json.dumps(payload, sort_keys=True, default=str)
    second = json.dumps(payload, sort_keys=True, default=str)
    assert first == second


def test_parquet_bytes_geometry_is_json_serializable() -> None:
    service = IngestionService(session=None)  # type: ignore[arg-type]
    payload = {"geometry": dumps(Point(77.6, 12.9))}

    safe_payload = service._json_safe(payload)

    assert safe_payload["geometry"]["format"] == "GeoJSON"
    assert safe_payload["geometry"]["value"]["type"] == "Point"
    assert json.dumps(safe_payload)


def test_highway_bytes_geometry_ingestion_does_not_crash(tmp_path) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.records = []
            self.duplicate_queries = 0

        def scalar(self, _statement):
            return None

        def scalars(self, _statement):
            self.duplicate_queries += 1
            return _FakeScalarResult([])

        def add(self, record) -> None:
            self.records.append(record)

        def execute(self, _statement, records) -> None:
            self.records.extend(records)

        def flush(self) -> None:
            return None

        def commit(self) -> None:
            return None

    class _FakeScalarResult:
        def __init__(self, values) -> None:
            self.values = values

        def all(self):
            return self.values

    session = FakeSession()
    service = IngestionService(session=session)  # type: ignore[arg-type]
    source = tmp_path / "highways.parquet"
    source.write_bytes(b"parquet-test-fixture")

    summary = service._ingest_evidence_rows(
        "highways",
        source,
        [{"highway_id": "NH-1", "geometry": dumps(Point(77.6, 12.9))}],
        "national_highways",
    )

    assert summary.inserted == 2
    assert len(session.records) == 2
    assert json.dumps(session.records[-1]["evidence_payload"])


def test_evidence_batch_duplicate_check_is_not_per_row(tmp_path) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.duplicate_queries = 0
            self.insert_batches = []

        def add(self, _record) -> None:
            return None

        def scalar(self, _statement):
            return None

        def scalars(self, _statement):
            self.duplicate_queries += 1
            return _FakeScalarResult([])

        def execute(self, _statement, records):
            self.insert_batches.append(list(records))

        def flush(self):
            return None

        def commit(self):
            return None

    class _FakeScalarResult:
        def __init__(self, values) -> None:
            self.values = values

        def all(self):
            return self.values

    session = FakeSession()
    service = IngestionService(session=session, data_dir=tmp_path)  # type: ignore[arg-type]
    source = tmp_path / "roads.geojsonl"
    source.write_text("", encoding="utf-8")
    rows = [
        {"road_id": str(index), "geometry": {"type": "LineString", "coordinates": []}}
        for index in range(5)
    ]

    summary = service._ingest_evidence_rows(
        "roads", source, rows, "pmgsy_roads", batch_size=2
    )

    assert summary.inserted == 6  # dataset metadata plus five road records
    assert session.duplicate_queries == 3
    assert len(session.insert_batches) == 3


def test_system_7zip_detection_and_command(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "roads.7z"
    output = tmp_path / "out"
    archive.write_bytes(b"archive")
    monkeypatch.setattr(
        "backend.ingestion.readers.shutil.which",
        lambda name: r"C:\Program Files\7-Zip\7z.exe" if name == "7z" else None,
    )

    assert find_7zip_executable().endswith("7z.exe")
    assert build_7zip_extract_command("7z.exe", archive, output) == [
        "7z.exe",
        "x",
        str(archive),
        "-y",
        f"-o{output}",
        "*.geojsonl",
    ]


def test_extract_7z_uses_system_command_and_cache(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "roads.7z"
    archive.write_bytes(b"archive")
    output = tmp_path / "extracted"
    output.mkdir()
    (output / "roads.geojsonl").write_text("{}", encoding="utf-8")
    calls = []
    monkeypatch.setattr("backend.ingestion.readers.find_7zip_executable", lambda: "7z.exe")
    monkeypatch.setattr(
        "backend.ingestion.readers.tempfile.mkdtemp",
        lambda prefix: str(output),
    )
    monkeypatch.setattr(
        "backend.ingestion.readers.subprocess.run",
        lambda command, **kwargs: calls.append(command) or SimpleNamespace(returncode=0, stderr="", stdout=""),
    )
    cache = {}

    first = extract_7z(archive, cache)
    second = extract_7z(archive, cache)

    assert first == second == output
    assert len(calls) == 1
    assert "*.geojsonl" in calls[0]


def test_windows_standard_7zip_path_is_preferred(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("backend.ingestion.readers.sys.platform", "win32")
    monkeypatch.setattr("backend.ingestion.readers.shutil.which", lambda _name: None)
    original_is_file = __import__("pathlib").Path.is_file

    def standard_path_exists(path):
        if str(path) == r"C:\Program Files\7-Zip\7z.exe":
            return False
        if str(path) == r"C:\Program Files (x86)\7-Zip\7z.exe":
            return True
        return original_is_file(path)

    monkeypatch.setattr("backend.ingestion.readers.Path.is_file", standard_path_exists)

    assert find_7zip_executable() == r"C:\Program Files (x86)\7-Zip\7z.exe"
    assert selected_7z_extractor() == "system 7-Zip"


def test_pmgsY_fails_fast_without_system_7zip(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "roads.7z"
    archive.write_bytes(b"archive")
    monkeypatch.setattr("backend.ingestion.readers.find_7zip_executable", lambda: None)

    with pytest.raises(IngestionError, match="requires system 7-Zip"):
        extract_7z(archive, require_system=True)


def test_extract_7z_falls_back_to_py7zr_selectively(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "roads.7z"
    archive.write_bytes(b"archive")
    output = tmp_path / "extracted"
    output.mkdir()
    (output / "roads.geojsonl").write_text("{}", encoding="utf-8")
    extracted = []

    class FakeArchive:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def getnames(self):
            return ["roads.geojsonl", "unrelated.bin"]

        def extract(self, path, targets):
            extracted.extend(targets)

    fake_py7zr = SimpleNamespace(SevenZipFile=lambda *_args, **_kwargs: FakeArchive())
    monkeypatch.setattr("backend.ingestion.readers.find_7zip_executable", lambda: None)
    monkeypatch.setitem(sys.modules, "py7zr", fake_py7zr)
    monkeypatch.setattr("backend.ingestion.readers.tempfile.mkdtemp", lambda prefix: str(output))

    extract_7z(archive)

    assert extracted == ["roads.geojsonl"]


def test_extract_7z_reports_missing_archive_and_empty_extraction(tmp_path, monkeypatch) -> None:
    with pytest.raises(IngestionError, match="does not exist"):
        extract_7z(tmp_path / "missing.7z")

    archive = tmp_path / "empty.7z"
    archive.write_bytes(b"archive")
    monkeypatch.setattr("backend.ingestion.readers.find_7zip_executable", lambda: None)

    class EmptyArchive:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def getnames(self):
            return ["unrelated.bin"]

    monkeypatch.setitem(
        sys.modules,
        "py7zr",
        SimpleNamespace(SevenZipFile=lambda *_args, **_kwargs: EmptyArchive()),
    )
    with pytest.raises(IngestionError, match="contains no GeoJSONL"):
        extract_7z(archive)


def test_schema_json_is_excluded_from_geojson_discovery(tmp_path) -> None:
    (tmp_path / "destination.schema.json").write_text("{}", encoding="utf-8")

    with pytest.raises(IngestionError, match="No dataset found"):
        find_dataset(tmp_path, ("destination",), (".geojson", ".json"))


def test_vulnerability_csv_is_not_selected_by_unrelated_csv_routes(tmp_path) -> None:
    vulnerability = tmp_path / "climate-vulnerability-indicators-district-wise.csv"
    vulnerability.write_text(
        "district,state,vulnerability_index\nBengaluru,Karnataka,0.4\n",
        encoding="utf-8",
    )
    service = IngestionService(session=None, data_dir=tmp_path)  # type: ignore[arg-type]

    with pytest.raises(IngestionError, match="No dataset found"):
        service._ingest_evidence_csv("rainfall", ("rainfall", "imd_rainfall"), "imd_rainfall")
    with pytest.raises(IngestionError, match="No dataset found"):
        service._ingest_evidence_csv("hospitals", ("hospitals", "hospital"), "hospital")


def test_missing_xlsx_dependency_has_actionable_error(tmp_path, monkeypatch) -> None:
    path = tmp_path / "census.xlsx"
    path.write_bytes(b"not-an-xlsx")
    original_import = builtins.__import__

    def missing_openpyxl(name, *args, **kwargs):
        if name == "openpyxl":
            raise ModuleNotFoundError("No module named 'openpyxl'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_openpyxl)
    with pytest.raises(IngestionError, match="requires openpyxl"):
        read_xlsx(path)


def test_missing_pdf_dependency_has_actionable_error(tmp_path, monkeypatch) -> None:
    path = tmp_path / "landslide.pdf"
    path.write_bytes(b"%PDF-1.4")
    service = IngestionService(session=None, data_dir=tmp_path)  # type: ignore[arg-type]
    service._record_dataset_metadata = lambda *_args: None  # type: ignore[method-assign]
    original_import = builtins.__import__

    def missing_pypdf(name, *args, **kwargs):
        if name == "pypdf":
            raise ModuleNotFoundError("No module named 'pypdf'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_pypdf)
    with pytest.raises(IngestionError, match="requires pypdf"):
        service._ingest_pdf_evidence("landslide_susceptibility", path)


def test_actual_dataset_filenames_resolve_to_expected_routes(tmp_path) -> None:
    filenames = [
        "2011-IndiaStateDistSbDist-0000.xlsx",
        "climate-vulnerability-indicators-district-wise.csv",
        "GatiShakti_MORTH_National_Highways.parquet",
        "hospital_directory.csv",
        "INDIA_FLOOD_INVENTORY_V3.geojson",
        "pmgsy_roads.geojsonl.7z",
        "rainfall_statewise_daily_imd.csv",
        "vb_soi_ap_geojson.zip",
        "vb_soi_ka_shp.zip",
        "vb_soi_kl_shp.zip",
        "vb_soi_py_shp.zip",
        "vb_soi_tn_shp.zip",
        "vb_soi_ts_shp.zip",
        "district_landslide_susceptibility.pdf",
        "imd_cyclone_report.pdf",
    ]
    for filename in filenames:
        (tmp_path / filename).write_bytes(b"fixture")

    assert find_dataset(tmp_path, ("2011-IndiaStateDistSbDist-0000.xlsx",), (".xlsx",)).name == "2011-IndiaStateDistSbDist-0000.xlsx"
    assert find_dataset(tmp_path, ("climate-vulnerability-indicators-district-wise.csv",), (".csv",)).name == "climate-vulnerability-indicators-district-wise.csv"
    assert find_dataset(tmp_path, ("GatiShakti_MORTH_National_Highways.parquet",), (".parquet",)).name == "GatiShakti_MORTH_National_Highways.parquet"
    assert find_dataset(tmp_path, ("hospital_directory.csv",), (".csv",)).name == "hospital_directory.csv"
    assert find_dataset(tmp_path, ("INDIA_FLOOD_INVENTORY_V3.geojson",), (".geojson",)).name == "INDIA_FLOOD_INVENTORY_V3.geojson"
    assert find_dataset(tmp_path, ("pmgsy_roads.geojsonl.7z",), (".7z",)).name == "pmgsy_roads.geojsonl.7z"
    assert find_dataset(tmp_path, ("rainfall_statewise_daily_imd.csv",), (".csv",)).name == "rainfall_statewise_daily_imd.csv"
    assert [path.name for path in find_datasets(tmp_path, ("vb_soi_*_shp.zip", "vb_soi_*_geojson.zip"), (".zip",))] == [
        "vb_soi_ap_geojson.zip",
        "vb_soi_ka_shp.zip",
        "vb_soi_kl_shp.zip",
        "vb_soi_py_shp.zip",
        "vb_soi_tn_shp.zip",
        "vb_soi_ts_shp.zip",
    ]
    assert find_dataset(tmp_path, ("*landslide*.pdf",), (".pdf",)).name == "district_landslide_susceptibility.pdf"
    assert find_dataset(tmp_path, ("*cyclone*.pdf",), (".pdf",)).name == "imd_cyclone_report.pdf"


def test_actual_csv_headers_map_to_evidence_geographies(tmp_path) -> None:
    vulnerability = tmp_path / "climate-vulnerability-indicators-district-wise.csv"
    vulnerability.write_text(
        "id,year,state_code,state_name,district_code,district_name,climate_vul_in\n"
        "1,2021-01-01,29,Karnataka,1,Bengaluru,0.4\n",
        encoding="utf-8",
    )
    rainfall = tmp_path / "rainfall_statewise_daily_imd.csv"
    rainfall.write_text(
        "State,Date,Daily Actual,Daily Normal\nKARNATAKA,2026-08-19,4.1,12.9\n",
        encoding="utf-8",
    )
    hospitals = tmp_path / "hospital_directory.csv"
    hospitals.write_text(
        "Hospital_Name,Location_Coordinates,State,District\n"
        "General Hospital,12.97 77.59,Karnataka,Bengaluru\n",
        encoding="utf-8",
    )

    vulnerability_row = read_csv(vulnerability)[0]
    rainfall_row = read_csv(rainfall)[0]
    hospital_row = read_csv(hospitals)[0]
    service = IngestionService(session=None, data_dir=tmp_path)  # type: ignore[arg-type]

    service._validate_evidence_row("vulnerability", service._normalized_row(vulnerability_row), "vulnerability")
    service._validate_evidence_row("rainfall", service._normalized_row(rainfall_row), "rainfall")
    service._validate_evidence_row("hospitals", service._normalized_row(hospital_row), "hospitals")


def test_actual_landslide_and_cyclone_pdf_discovery(tmp_path) -> None:
    (tmp_path / "Charmadi Ghat Stretch of NH-73 Area Susceptibility Map.pdf").write_bytes(b"pdf")
    (tmp_path / "33_6a2fe6738ccb6.pdf").write_bytes(b"pdf")
    service = IngestionService(session=None, data_dir=tmp_path)  # type: ignore[arg-type]

    assert service.ingest_landslides.__name__ == "ingest_landslides"
    assert find_dataset(tmp_path, ("*Susceptibility Map.pdf",), (".pdf",)).name.endswith("Susceptibility Map.pdf")
    pdfs = find_datasets(tmp_path, ("*.pdf",), (".pdf",))
    assert [path.name for path in pdfs if "susceptibility map" not in path.name.lower()] == ["33_6a2fe6738ccb6.pdf"]
