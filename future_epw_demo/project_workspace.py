from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .epw_meta import EPWMetadata, parse_epw_metadata
from .errors import BaselineFingerprintMismatchError, InvalidBaselineError, ProjectConflictError

# Retained only as a backwards-compatible naming aid for the original validated
# eight-station study. It is no longer a gate on project creation.
SUPPORTED_WMO_TO_CITY = {
    "421820": "Delhi",
    "486980": "Singapore",
    "405820": "Kuwait City",
    "545110": "Beijing",
    "037720": "London",
    "947670": "Sydney",
    "082210": "Madrid",
    "716240": "Toronto",
}


REQUIRED_CMIP6_VARIABLES = (
    "tas", "tasmax", "tasmin", "huss", "psl", "sfcWind", "clt", "rsds", "rlds", "pr",
)
FULL_R1_GCMS = ("ACCESS-CM2", "GFDL-ESM4", "MPI-ESM1-2-HR", "IPSL-CM6A-LR", "FGOALS-g3")
FULL_R1_SCENARIOS = ("ssp126", "ssp245", "ssp370")


def _portable_relative_path(*parts: str) -> str:
    """Serialize project-internal relative paths with forward slashes on every OS."""
    return str(PurePosixPath(*parts))


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip()).strip("._-")
    return slug or "location"


def make_location_key(city: str, latitude: float, longitude: float) -> str:
    canonical = f"{city.strip()}|{float(latitude):.5f}|{float(longitude):.5f}"
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:10]
    return f"{_safe_slug(city)}__{float(latitude):+.5f}_{float(longitude):+.5f}__{digest}"


@dataclass(frozen=True)
class WorkspaceStatus:
    cmip6_total: int = 200
    cmip6_complete: int = 0
    cmip6_missing: int = 200
    city_cached: int = 0
    remote_ready: int = 0
    factors_ready: bool = False
    fallback_rows: int = 0
    epw_count: int = 0
    validation_passed: bool | None = None
    audit_groups: int = 0


@dataclass
class ProjectWorkspace:
    root: Path
    project_name: str
    city: str
    metadata: EPWMetadata
    baseline_filename: str
    latitude: float
    longitude: float
    coordinate_source: str
    scenarios: list[str]
    periods: list[str]
    gcms: list[str]
    climate_mode: str = "reproducible"
    baseline_origin: dict | None = None

    @property
    def display_city(self) -> str:
        """Human-friendly city label without changing the persisted cache identity.

        Older projects may have persisted the EPW station name in ``city``.  The
        workflow must keep that value internally because it is part of the
        location cache key, but the UI can safely show the catalog city name.
        """
        origin = self.baseline_origin if isinstance(self.baseline_origin, dict) else {}
        origin_city = str(origin.get("city") or "").strip()
        if origin_city:
            return origin_city
        persisted = str(self.city or "").strip()
        station = str(self.metadata.station or "").strip()
        if persisted and persisted.casefold() != station.casefold():
            return persisted
        try:
            from .weather_library import WeatherCatalog
            record = WeatherCatalog().by_wmo(self.metadata.wmo)
        except Exception:
            record = None
        if record is not None:
            return record.city
        return SUPPORTED_WMO_TO_CITY.get(self.metadata.wmo) or persisted or station or "Target City"

    @property
    def location_key(self) -> str:
        return make_location_key(self.city, self.latitude, self.longitude)

    @property
    def baseline_dir(self) -> Path:
        return self.root / "inputs" / "baseline_epw"

    @property
    def baseline_path(self) -> Path:
        return self.baseline_dir / self.baseline_filename

    @property
    def location_cache_root(self) -> Path:
        return self.root / "cache" / "locations" / self.location_key

    @property
    def cache_dir(self) -> Path:
        return self.location_cache_root / "cmip6_monthly"

    @property
    def city_cache_dir(self) -> Path:
        return self.location_cache_root / "cmip6_monthly_city"

    @property
    def legacy_cache_dir(self) -> Path:
        return self.root / "cache" / "cmip6_monthly"

    @property
    def legacy_city_cache_dir(self) -> Path:
        return self.root / "cache" / "cmip6_monthly_city"

    @property
    def outputs_dir(self) -> Path:
        return self.root / "outputs"

    @property
    def manifest_dir(self) -> Path:
        return self.outputs_dir / "manifest"

    @property
    def factors_dir(self) -> Path:
        return self.outputs_dir / "factors"

    @property
    def epw_dir(self) -> Path:
        return self.outputs_dir / "epw"

    @property
    def audit_dir(self) -> Path:
        return self.outputs_dir / "audit"

    @property
    def validation_dir(self) -> Path:
        return self.outputs_dir / "validation"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def runtime_dir(self) -> Path:
        return self.root / "runtime"

    @property
    def manifest_file(self) -> Path:
        return self.manifest_dir / "manifest_cmip6.csv"

    @property
    def manifest_metadata_file(self) -> Path:
        return self.manifest_dir / "manifest_metadata.json"

    @property
    def cmip6_status_file(self) -> Path:
        return self.runtime_dir / "cmip6_status.json"

    @property
    def stop_file(self) -> Path:
        return self.runtime_dir / "pause_requested.flag"

    @property
    def location_spec_file(self) -> Path:
        return self.runtime_dir / "location_spec.json"

    @property
    def workflow_state_file(self) -> Path:
        return self.runtime_dir / "workflow_state.json"

    @property
    def factor_metadata_file(self) -> Path:
        return self.factors_dir / "factor_metadata.json"

    @property
    def validation_metadata_file(self) -> Path:
        return self.validation_dir / "validation_metadata.json"

    @property
    def generation_records_file(self) -> Path:
        return self.epw_dir / "generation_records.csv"

    @property
    def project_file(self) -> Path:
        return self.root / "project.json"

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def baseline_sha256(self) -> str:
        return self._sha256_file(self.baseline_path)

    @classmethod
    def create(
        cls,
        *,
        root: Path | str,
        project_name: str,
        baseline_source: Path | str,
        scenarios: list[str],
        periods: list[str],
        gcms: list[str],
        city_name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        use_epw_coordinates: bool = True,
        climate_mode: str = "reproducible",
        baseline_origin: dict | None = None,
    ) -> "ProjectWorkspace":
        root = Path(root).expanduser().resolve()
        source = Path(baseline_source).expanduser().resolve()
        try:
            meta = parse_epw_metadata(source)
        except Exception as exc:
            raise InvalidBaselineError(
                f"Cannot read the baseline EPW: {exc}",
                recovery="Choose a valid 8760-hour EPW file.",
            ) from exc
        if not meta.valid:
            raise InvalidBaselineError(
                f"Baseline EPW must contain 8760 hourly rows and a LOCATION/WMO record; found {meta.hours} rows.",
                recovery="Choose a validated 8760-hour baseline EPW.",
            )

        if root.exists():
            contents = list(root.iterdir())
            if (root / "project.json").exists():
                raise ProjectConflictError(
                    "This folder already contains a Future EPW project.",
                    recovery="Open the existing project or choose another folder.",
                )
            if contents:
                raise ProjectConflictError(
                    "The selected folder is not empty and is not a Future EPW project.",
                    recovery="Choose a new empty project folder.",
                )

        city = (city_name or "").strip() or SUPPORTED_WMO_TO_CITY.get(meta.wmo) or meta.station.strip()
        if not city:
            raise ValueError("A non-empty target city/location label is required")
        target_lat = float(meta.latitude if use_epw_coordinates or latitude is None else latitude)
        target_lon = float(meta.longitude if use_epw_coordinates or longitude is None else longitude)
        if not -90.0 <= target_lat <= 90.0:
            raise ValueError(f"Target latitude out of range: {target_lat}")
        if not -180.0 <= target_lon <= 180.0:
            raise ValueError(f"Target longitude out of range: {target_lon}")
        coordinate_source = "epw" if use_epw_coordinates else "manual"

        for path in [
            root / "inputs" / "baseline_epw",
            root / "cache" / "cmip6_monthly",  # legacy read-only compatibility namespace
            root / "cache" / "cmip6_monthly_city",  # legacy read-only compatibility namespace
            root / "outputs" / "manifest",
            root / "outputs" / "factors",
            root / "outputs" / "epw",
            root / "outputs" / "audit",
            root / "outputs" / "validation",
            root / "logs",
            root / "runtime",
        ]:
            path.mkdir(parents=True, exist_ok=True)
        target = root / "inputs" / "baseline_epw" / source.name
        if source != target:
            shutil.copy2(source, target)
        ws = cls(
            root=root,
            project_name=project_name.strip() or f"{city}_Future_EPW",
            city=city,
            metadata=parse_epw_metadata(target),
            baseline_filename=target.name,
            latitude=target_lat,
            longitude=target_lon,
            coordinate_source=coordinate_source,
            scenarios=list(scenarios),
            periods=list(periods),
            gcms=list(gcms),
            climate_mode=str(climate_mode or "reproducible"),
            baseline_origin=dict(baseline_origin) if baseline_origin else None,
        )
        ws.cache_dir.mkdir(parents=True, exist_ok=True)
        ws.city_cache_dir.mkdir(parents=True, exist_ok=True)
        ws.save()
        return ws

    @classmethod
    def load(cls, root: Path | str) -> "ProjectWorkspace":
        root = Path(root).expanduser().resolve()
        project_file = root / "project.json"
        if not project_file.is_file():
            raise FileNotFoundError(f"Future EPW project.json not found: {project_file}")
        payload = json.loads(project_file.read_text(encoding="utf-8"))
        baseline_info = payload.get("baseline") if isinstance(payload.get("baseline"), dict) else {}
        relative = baseline_info.get("relative_path") or payload.get("baseline_epw")
        if not relative:
            raise ValueError("project.json does not define a baseline EPW")
        baseline = root / relative
        meta = parse_epw_metadata(baseline)
        selection = payload.get("climate_selection") if isinstance(payload.get("climate_selection"), dict) else None
        if selection is None:
            # v0.9/v0.9.1 projects predate true custom subsets. Treat them as
            # full reproducible R1 projects even if their UI happened to persist
            # a partial checkbox state.
            climate_mode = "reproducible"
            scenarios = list(FULL_R1_SCENARIOS)
            periods = ["2040", "2060"]
            gcms = list(FULL_R1_GCMS)
        else:
            climate_mode = str(selection.get("mode", "reproducible"))
            if climate_mode == "advanced":
                scenarios = list(selection.get("ssps", payload.get("scenarios", [])))
                periods = [str(x) for x in selection.get("periods", payload.get("periods", []))]
                gcms = list(selection.get("gcms", payload.get("gcms", [])))
            else:
                scenarios = list(FULL_R1_SCENARIOS)
                periods = ["2040", "2060"]
                gcms = list(FULL_R1_GCMS)
        ws = cls(
            root=root,
            project_name=payload["project_name"],
            city=payload["city"],
            metadata=meta,
            baseline_filename=baseline.name,
            latitude=float(payload.get("latitude", meta.latitude)),
            longitude=float(payload.get("longitude", meta.longitude)),
            coordinate_source=str(payload.get("coordinate_source", "epw")),
            scenarios=scenarios,
            periods=periods,
            gcms=gcms,
            climate_mode=climate_mode,
            baseline_origin=dict(baseline_info.get("origin")) if isinstance(baseline_info.get("origin"), dict) else None,
        )
        ws.cache_dir.mkdir(parents=True, exist_ok=True)
        ws.city_cache_dir.mkdir(parents=True, exist_ok=True)
        ws._write_location_spec()
        return ws

    def _baseline_payload(self) -> dict:
        payload = {
            "relative_path": _portable_relative_path("inputs", "baseline_epw", self.baseline_filename),
            "filename": self.baseline_filename,
            "sha256": self.baseline_sha256(),
            "hours": int(self.metadata.hours),
            "station": self.metadata.station,
            "wmo": self.metadata.wmo,
            "latitude": float(self.metadata.latitude),
            "longitude": float(self.metadata.longitude),
            "elevation": float(self.metadata.elevation),
        }
        if self.baseline_origin:
            payload["origin"] = dict(self.baseline_origin)
        return payload

    def _write_location_spec(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "location_key": self.location_key,
            "locations": [
                {
                    "city": self.city,
                    "latitude": float(self.latitude),
                    "longitude": float(self.longitude),
                    "coordinate_source": self.coordinate_source,
                    "baseline_latitude": float(self.metadata.latitude),
                    "baseline_longitude": float(self.metadata.longitude),
                    "wmo": self.metadata.wmo,
                    "station": self.metadata.station,
                    "baseline_epw": str(self.baseline_path.resolve()),
                }
            ],
        }
        self.location_spec_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def save(self) -> None:
        baseline_payload = self._baseline_payload()
        if self.project_file.is_file():
            # Never silently bless a changed baseline by rewriting its fingerprint.
            # Existing v0.9 projects keep the original baseline identity; v0.8
            # projects acquire a fingerprint the first time they are explicitly saved.
            existing = self._project_payload().get("baseline")
            if isinstance(existing, dict) and existing.get("sha256"):
                baseline_payload = existing
        effective_gcms = self.effective_gcms()
        effective_scenarios = self.effective_scenarios()
        effective_periods = self.effective_periods()
        payload = {
            "app_version": "1.0.0",
            "workflow_engine": "v1.5.1+arbitrary-city",
            "workflow_protocol": "R1",
            "project_name": self.project_name,
            "city": self.city,
            "location_key": self.location_key,
            "wmo": self.metadata.wmo,
            "station": self.metadata.station,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "coordinate_source": self.coordinate_source,
            "baseline_latitude": self.metadata.latitude,
            "baseline_longitude": self.metadata.longitude,
            "elevation": self.metadata.elevation,
            "baseline_epw": _portable_relative_path("inputs", "baseline_epw", self.baseline_filename),
            "baseline": baseline_payload,
            "scenarios": effective_scenarios,
            "periods": effective_periods,
            "gcms": effective_gcms,
            "climate_selection": {
                "mode": self.climate_mode,
                "gcms": effective_gcms,
                "ssps": effective_scenarios,
                "periods": [int(x) if str(x).isdigit() else str(x) for x in effective_periods],
                "protocol": "R1",
            },
        }
        self.project_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_location_spec()

    def _project_payload(self) -> dict:
        try:
            return json.loads(self.project_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def verify_baseline_fingerprint(self) -> bool:
        if not self.baseline_path.is_file():
            return False
        payload = self._project_payload()
        baseline = payload.get("baseline") if isinstance(payload.get("baseline"), dict) else {}
        saved = baseline.get("sha256")
        if not saved:  # v0.8 compatibility: no fingerprint was persisted.
            return True
        try:
            return self.baseline_sha256() == str(saved)
        except OSError:
            return False

    def assert_baseline_integrity(self) -> None:
        if not self.verify_baseline_fingerprint():
            raise BaselineFingerprintMismatchError(
                "The baseline EPW no longer matches this project.",
                recovery="Restore the original baseline EPW or create a new project.",
                progress_safe=True,
            )

    def project_protocol(self) -> str:
        return str(self._project_payload().get("workflow_protocol", ""))

    def location_spec_matches_project(self) -> bool:
        try:
            data = json.loads(self.location_spec_file.read_text(encoding="utf-8"))
            locations = data.get("locations", [])
            if data.get("location_key") != self.location_key or len(locations) != 1:
                return False
            loc = locations[0]
            return (
                str(loc.get("city")) == self.city
                and abs(float(loc.get("latitude")) - float(self.latitude)) <= 1e-6
                and abs(float(loc.get("longitude")) - float(self.longitude)) <= 1e-6
                and Path(str(loc.get("baseline_epw"))).resolve() == self.baseline_path.resolve()
            )
        except Exception:
            return False

    def manifest_row_count(self) -> int:
        if not self.manifest_file.is_file():
            return 0
        try:
            with self.manifest_file.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                return max(0, sum(1 for _ in csv.reader(handle)) - 1)
        except OSError:
            return 0

    def expected_asset_keys(self) -> set[str]:
        models = self.effective_gcms()
        scenarios = self.effective_scenarios()
        experiments = ["historical", *scenarios]
        return {
            f"{model}__{experiment}__{variable}"
            for model in models
            for experiment in experiments
            for variable in REQUIRED_CMIP6_VARIABLES
        }

    def manifest_matches_selection(self) -> bool:
        if not self.manifest_file.is_file():
            return False
        if self.manifest_row_count() != self.dynamic_asset_total():
            return False
        if not self.manifest_metadata_file.is_file():
            # v0.9.1 compatibility: the legacy full R1 manifest had no selection metadata.
            return self.climate_mode == "reproducible" and self.dynamic_asset_total() == 200
        try:
            data = json.loads(self.manifest_metadata_file.read_text(encoding="utf-8"))
            sel = data.get("selection", {})
            return (
                list(sel.get("models", [])) == self.effective_gcms()
                and list(sel.get("experiments", [])) == ["historical", *self.effective_scenarios()]
                and [str(x) for x in sel.get("periods", [])] == self.effective_periods()
                and int(data.get("main_assets", -1)) == self.dynamic_asset_total()
            )
        except Exception:
            return False

    def ensure_output_dirs_writable(self) -> bool:
        marker = self.outputs_dir / ".future_epw_write_test"
        try:
            self.outputs_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text("ok", encoding="utf-8")
            marker.unlink(missing_ok=True)
            return True
        except OSError:
            try:
                marker.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def effective_gcms(self) -> list[str]:
        return list(self.gcms) if self.climate_mode == "advanced" else list(FULL_R1_GCMS)

    def effective_scenarios(self) -> list[str]:
        return list(self.scenarios) if self.climate_mode == "advanced" else list(FULL_R1_SCENARIOS)

    def effective_periods(self) -> list[str]:
        return [str(x) for x in self.periods] if self.climate_mode == "advanced" else ["2040", "2060"]

    def update_climate_selection(self, *, mode: str, scenarios: list[str], periods: list[str], gcms: list[str]) -> bool:
        old_fingerprint = self.selection_fingerprint()
        new_mode = str(mode or "reproducible")
        new_scenarios = list(scenarios)
        new_periods = [str(x) for x in periods]
        new_gcms = list(gcms)
        changed = (
            new_mode != self.climate_mode
            or new_scenarios != list(self.scenarios)
            or new_periods != [str(x) for x in self.periods]
            or new_gcms != list(self.gcms)
        )
        self.climate_mode = new_mode
        self.scenarios = new_scenarios
        self.periods = new_periods
        self.gcms = new_gcms
        if changed:
            # Preserve location-specific CMIP6 caches so compatible assets can be reused.
            # Derived outputs are moved to an auditable stale-selection archive instead of
            # being deleted; the active output directories are then recreated empty.
            derived_dirs = [self.manifest_dir, self.factors_dir, self.epw_dir, self.audit_dir, self.validation_dir]
            have_derived = any(directory.exists() and any(directory.iterdir()) for directory in derived_dirs)
            if have_derived:
                stale_base = self.outputs_dir / "stale" / old_fingerprint
                stale_root = stale_base
                suffix = 2
                while stale_root.exists():
                    stale_root = stale_base.with_name(f"{old_fingerprint}_{suffix}")
                    suffix += 1
                for directory in derived_dirs:
                    if not directory.exists():
                        continue
                    children = list(directory.iterdir())
                    if not children:
                        continue
                    target_dir = stale_root / directory.name
                    target_dir.mkdir(parents=True, exist_ok=True)
                    for child in children:
                        shutil.move(str(child), str(target_dir / child.name))
            for directory in derived_dirs:
                directory.mkdir(parents=True, exist_ok=True)
            self.cmip6_status_file.unlink(missing_ok=True)
            self.workflow_state_file.unlink(missing_ok=True)
        self.save()
        return changed

    def dynamic_asset_total(self) -> int:
        return len(self.effective_gcms()) * (1 + len(self.effective_scenarios())) * len(REQUIRED_CMIP6_VARIABLES)

    def selection_fingerprint(self) -> str:
        payload = {
            "models": self.effective_gcms(),
            "experiments": ["historical", *self.effective_scenarios()],
            "periods": self.effective_periods(),
            "protocol": "R1",
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def expected_epw_count(self) -> int:
        return len(self.effective_scenarios()) * len(self.effective_periods()) * (len(self.effective_gcms()) + 1)

    def factors_complete(self) -> bool:
        required = [
            self.factors_dir / "monthly_climatology_long.csv",
            self.factors_dir / "climate_factors_per_gcm.csv",
            self.factors_dir / "climate_factors_ensemble.csv",
            self.factor_metadata_file,
        ]
        if not all(path.is_file() and path.stat().st_size > 0 for path in required):
            return False
        try:
            data = json.loads(self.factor_metadata_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return False
            # v0.9.1 factor metadata did not record a selection. It remains
            # valid only for the legacy full reproducible workflow.
            if not all(key in data for key in ("models", "scenarios", "labels")):
                return self.climate_mode == "reproducible"
            return (
                list(data.get("models", [])) == self.effective_gcms()
                and list(data.get("scenarios", [])) == self.effective_scenarios()
                and [str(x) for x in data.get("labels", [])] == self.effective_periods()
            )
        except Exception:
            return False

    def generation_complete(self) -> bool:
        if not self.generation_records_file.is_file():
            return False
        try:
            with self.generation_records_file.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                rows = list(csv.DictReader(handle))
            if len(rows) != self.expected_epw_count() or not rows or "output_epw" not in rows[0]:
                return False
            for row in rows:
                raw = str(row.get("output_epw", "")).strip()
                if not raw:
                    return False
                path = Path(raw)
                if not path.is_absolute():
                    candidate = self.epw_dir / path
                    path = candidate if candidate.exists() else self.root / path
                if not path.is_file():
                    return False
            return True
        except Exception:
            return False

    def _fallback_rows(self) -> int:
        if not self.factor_metadata_file.is_file():
            return 0
        try:
            data = json.loads(self.factor_metadata_file.read_text(encoding="utf-8"))
            return int(data.get("pr_dry_baseline_fallback_rows", 0))
        except Exception:
            return 0

    def validation_outcome(self) -> str:
        if not self.validation_metadata_file.is_file():
            return "not_run"
        try:
            data = json.loads(self.validation_metadata_file.read_text(encoding="utf-8"))
            if int(data.get("epw_count", -1)) != self.expected_epw_count():
                return "fail"
            if not bool(data.get("passed", False)):
                return "fail"
            if not self.generation_complete():
                return "fail"
            return "warning" if self._fallback_rows() > 0 else "pass"
        except Exception:
            return "fail"

    def _status_matches_location(self, data: dict) -> bool:
        locations = data.get("locations")
        if isinstance(locations, list) and len(locations) == 1:
            loc = locations[0]
            try:
                return (
                    str(loc.get("city")) == self.city
                    and abs(float(loc.get("latitude")) - float(self.latitude)) <= 1e-6
                    and abs(float(loc.get("longitude")) - float(self.longitude)) <= 1e-6
                )
            except Exception:
                return False
        return (
            self.metadata.wmo in SUPPORTED_WMO_TO_CITY
            and data.get("cities") == [self.city]
            and SUPPORTED_WMO_TO_CITY.get(self.metadata.wmo) == self.city
        )

    def status_snapshot(self) -> WorkspaceStatus:
        # v0.9.1 progress semantics deliberately keep three quantities separate:
        # fully assembled asset caches (authoritative main progress), city-level
        # checkpoints (resumability telemetry), and the union that no longer
        # requires a remote city extraction.
        cmip6_total = self.dynamic_asset_total()
        cmip6_complete, cmip6_missing = 0, cmip6_total
        city_cached, remote_ready = 0, 0
        if self.manifest_file.exists():
            rows = self.manifest_row_count()
            if rows > 0:
                cmip6_total = rows
        status_data = None
        if self.cmip6_status_file.exists():
            try:
                candidate = json.loads(self.cmip6_status_file.read_text(encoding="utf-8"))
                if self._status_matches_location(candidate):
                    status_data = candidate
            except Exception:
                status_data = None

        expected_keys = self.expected_asset_keys()
        all_asset_files = list(self.cache_dir.glob("*.csv"))
        asset_files = [p for p in all_asset_files if p.stem in expected_keys]
        # Backward-compatibility for v0.9 fixtures/early caches that predate the
        # canonical MODEL__experiment__variable filename contract.
        if self.climate_mode != "advanced" and all_asset_files and not asset_files:
            asset_files = all_asset_files
        city_files = list(self.city_cache_dir.glob("*.csv"))
        actual_complete = min(cmip6_total, len(asset_files))
        complete_keys = {p.stem for p in asset_files}
        checkpoint_keys = set()
        all_checkpoint_keys = set()
        city_suffix = f"__{_safe_slug(self.city)}"
        for path in city_files:
            stem = path.stem
            key = stem[:-len(city_suffix)] if stem.endswith(city_suffix) else stem.rsplit("__", 1)[0]
            all_checkpoint_keys.add(key)
            if key in expected_keys:
                checkpoint_keys.add(key)
        if self.climate_mode != "advanced" and city_files and not checkpoint_keys:
            checkpoint_keys = all_checkpoint_keys
        actual_city_cached = min(cmip6_total, len(checkpoint_keys))
        file_remote_ready = min(cmip6_total, len(complete_keys | checkpoint_keys))
        have_file_evidence = bool(asset_files or checkpoint_keys)

        if status_data is not None:
            # Stage 02 status uses `cached`/`complete_assets` for fully assembled
            # assets. `current_city_complete` intentionally includes resumable
            # checkpoints and therefore must never drive the main progress bar.
            reported_total = int(status_data.get("total", cmip6_total))
            if reported_total == self.dynamic_asset_total():
                cmip6_total = reported_total
            if "complete_assets" in status_data or "cached" in status_data:
                reported_complete = int(status_data.get("complete_assets", status_data.get("cached", 0)))
            else:
                # Compatibility with early v0.9 state fixtures that stored only
                # a completed count and had no checkpoint telemetry fields.
                reported_complete = int(status_data.get("current_city_complete", 0))
            pending_city_cached = int(status_data.get("city_cached_within_pending_assets", 0))
            if have_file_evidence:
                # The filesystem is authoritative.  Status JSON may be stale after
                # an interrupted v0.9 run and can contain a checkpoint-inclusive
                # count that must never inflate completed-asset progress.
                cmip6_complete = actual_complete
                city_cached = actual_city_cached
                remote_ready = file_remote_ready
            else:
                # Compatibility for early projects/tests that persisted status but
                # have not yet materialized the location cache in this workspace.
                cmip6_complete = min(cmip6_total, reported_complete)
                city_cached = min(cmip6_total, pending_city_cached)
                remote_ready = min(cmip6_total, cmip6_complete + pending_city_cached)
        else:
            cmip6_complete = actual_complete
            city_cached = actual_city_cached
            remote_ready = file_remote_ready

        remote_ready = max(cmip6_complete, remote_ready)
        cmip6_missing = max(0, cmip6_total - cmip6_complete)

        fallback_rows = self._fallback_rows()
        # Compatibility view flag: historical GUI treats metadata presence as "ready".
        # v0.9 strict orchestration uses factors_complete() instead.
        factors_ready = self.factor_metadata_file.exists()
        epw_count = 0
        if self.generation_records_file.exists():
            try:
                with self.generation_records_file.open("r", encoding="utf-8-sig", errors="replace") as handle:
                    epw_count = max(0, sum(1 for _ in handle) - 1)
            except OSError:
                epw_count = 0
        validation_passed: bool | None = None
        audit_groups = 0
        if self.validation_metadata_file.exists():
            try:
                data = json.loads(self.validation_metadata_file.read_text(encoding="utf-8"))
                validation_passed = bool(data.get("passed", False))
                epw_count = int(data.get("epw_count", epw_count))
                audit_groups = int(data.get("audit_groups", 0))
            except Exception:
                validation_passed = False
        return WorkspaceStatus(
            cmip6_total=cmip6_total,
            cmip6_complete=cmip6_complete,
            cmip6_missing=cmip6_missing,
            city_cached=city_cached,
            remote_ready=remote_ready,
            factors_ready=factors_ready,
            fallback_rows=fallback_rows,
            epw_count=epw_count,
            validation_passed=validation_passed,
            audit_groups=audit_groups,
        )
