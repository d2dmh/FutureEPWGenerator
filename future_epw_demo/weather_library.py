from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import zipfile

from .app_settings import default_settings_path
from .epw_meta import parse_epw_metadata
from .runtime_paths import resource_path
from .errors import (
    WeatherArchiveError, WeatherDownloadError, WeatherEPWNotFoundError,
    WeatherNetworkError, WeatherValidationError, WeatherWriteError,
)


def default_weather_library_root(platform_name: str | None = None, env: dict | None = None) -> Path:
    platform_name = platform_name or os.name
    env = env or os.environ
    if platform_name == "nt":
        local = env.get("LOCALAPPDATA")
        if local:
            return Path(local).expanduser() / "FutureEPWGenerator" / "weather_library"
    return default_settings_path().parent / "weather_library"


@dataclass(frozen=True)
class WeatherRecord:
    id: str
    city: str
    country: str
    country_code: str
    region: str
    station: str
    wmo: str
    latitude: float
    longitude: float
    elevation_m: float
    dataset: str
    period: str
    source: str
    download_url: str
    preferred_epw_name: str
    aliases: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict) -> "WeatherRecord":
        payload=dict(data)
        payload["aliases"]=tuple(payload.get("aliases") or ())
        return cls(**payload)

    @property
    def display_name(self) -> str:
        return f"{self.city}, {self.country} — {self.station} (WMO {self.wmo})"


class WeatherCatalog:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else resource_path("assets", "weather_catalog.json")
        raw=json.loads(self.path.read_text(encoding="utf-8"))
        self.records=[WeatherRecord.from_dict(x) for x in raw]

    def search(self, query: str) -> list[WeatherRecord]:
        q=(query or "").strip().casefold()
        if not q:
            return list(self.records)
        scored=[]
        for record in self.records:
            fields=[record.city,record.country,record.region,record.station,record.wmo,*record.aliases]
            hay=" | ".join(fields).casefold()
            if q not in hay:
                continue
            primary=0 if record.city.casefold().startswith(q) else 1 if record.station.casefold().startswith(q) else 2
            scored.append((primary,record.city.casefold(),record))
        return [x[2] for x in sorted(scored,key=lambda t:(t[0],t[1]))]

    def by_wmo(self, wmo: str) -> WeatherRecord | None:
        target=str(wmo or "").strip().lstrip("0")
        if not target:
            return None
        for record in self.records:
            if str(record.wmo).strip().lstrip("0") == target:
                return record
        return None


class WeatherLibrary:
    def __init__(self, cache_root: Path | str | None = None):
        if cache_root is None:
            cache_root = default_weather_library_root()
        self.cache_root=Path(cache_root).expanduser()

    def record_dir(self, record: WeatherRecord) -> Path:
        return self.cache_root / record.id

    def cached_epw(self, record: WeatherRecord) -> Path | None:
        directory=self.record_dir(record)
        meta_path=directory / "metadata.json"
        if not meta_path.is_file(): return None
        try:
            meta=json.loads(meta_path.read_text(encoding="utf-8"))
            epw=directory / str(meta["epw_filename"])
            self._validate_epw(epw,record)
            saved_sha=str(meta.get("epw_sha256") or "")
            if not saved_sha or self._sha256(epw) != saved_sha:
                return None
            return epw
        except Exception:
            return None

    @staticmethod
    def _sha256(path: Path) -> str:
        h=hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _fetch(url: str) -> bytes:
        req=Request(url,headers={"User-Agent":"FutureEPWGenerator/1.0.0"})
        try:
            with urlopen(req,timeout=45) as r:
                return r.read()
        except HTTPError as exc:
            raise WeatherDownloadError(
                f"Weather source returned HTTP {exc.code}: {url}",
                recovery="Check the source URL or try again later.",
            ) from exc
        except URLError as exc:
            raise WeatherNetworkError(
                f"Could not reach the baseline weather source: {exc.reason}",
                recovery="Check your internet connection and try again. Cached EPWs remain available offline.",
            ) from exc
        except OSError as exc:
            raise WeatherDownloadError(
                f"Could not read the baseline weather source: {exc}",
                recovery="Check the source path/URL and try again.",
            ) from exc

    def _resolve_archive_url(self, record: WeatherRecord) -> str:
        url=record.download_url
        if url.lower().endswith(".zip"):
            return url
        html=self._fetch(url).decode("utf-8",errors="replace")
        hrefs=re.findall(r'href=["\']([^"\']+)["\']',html,flags=re.I)
        candidates=[]
        for href in hrefs:
            full=urljoin(url,href)
            name=urlparse(full).path.rsplit("/",1)[-1]
            if record.wmo in name and name.lower().endswith(".zip"):
                candidates.append(full)
        if not candidates:
            # One bounded directory level handles country pages that link state/city subdirectories.
            directories=[]
            base_host=urlparse(url).netloc
            for href in hrefs:
                if href.startswith("../") or "?" in href or "#" in href: continue
                full=urljoin(url,href)
                parsed=urlparse(full)
                if parsed.netloc==base_host and parsed.path.endswith("/") and full.rstrip('/')!=url.rstrip('/'):
                    directories.append(full)
            for directory in directories[:80]:
                try:
                    child=self._fetch(directory).decode("utf-8",errors="replace")
                except Exception:
                    continue
                for href in re.findall(r'href=["\']([^"\']+)["\']',child,flags=re.I):
                    full=urljoin(directory,href)
                    name=urlparse(full).path.rsplit("/",1)[-1]
                    if record.wmo in name and name.lower().endswith(".zip"):
                        candidates.append(full)
                if candidates: break
        if not candidates:
            raise WeatherEPWNotFoundError(
                f"No TMYx archive for {record.city} / WMO {record.wmo} was found on {url}",
                recovery="Use a local EPW or try another catalog station.",
            )
        preferred=[u for u in candidates if f"TMYx.{record.period}.zip".lower() in u.lower()]
        if preferred: candidates=preferred
        return sorted(candidates)[0]

    def _validate_epw(self, path: Path, record: WeatherRecord) -> None:
        if not path.is_file():
            raise WeatherEPWNotFoundError(
                f"EPW file was not found after extraction: {path}",
                recovery="Retry the download or choose a local EPW file.",
            )
        meta=parse_epw_metadata(path)
        if not meta.valid:
            raise WeatherValidationError(
                f"Downloaded EPW is invalid: expected 8760 hourly rows, found {meta.hours}",
                recovery="Choose another baseline station or provide a validated local EPW.",
            )
        if record.wmo and str(meta.wmo).lstrip("0") != str(record.wmo).lstrip("0"):
            raise WeatherValidationError(
                f"Downloaded EPW WMO mismatch: expected {record.wmo}, found {meta.wmo}",
                recovery="Do not use this file; choose another station or a local EPW.",
            )
        if abs(float(meta.latitude)-float(record.latitude))>0.5 or abs(float(meta.longitude)-float(record.longitude))>0.5:
            raise WeatherValidationError(
                "Downloaded EPW coordinates do not match the catalog station",
                recovery="Do not use this file; choose another station or a local EPW.",
            )

    def download_and_validate(self, record: WeatherRecord) -> Path:
        cached=self.cached_epw(record)
        if cached is not None: return cached
        directory=self.record_dir(record)
        try:
            directory.mkdir(parents=True,exist_ok=True)
        except OSError as exc:
            raise WeatherWriteError(
                f"Cannot create the weather-library cache directory: {exc}",
                recovery="Check permissions for the application data directory.",
            ) from exc
        archive_url=self._resolve_archive_url(record)
        archive_bytes=self._fetch(archive_url)
        archive=directory / "source.zip"
        temp_archive=archive.with_suffix(".tmp")
        temp_archive.write_bytes(archive_bytes)
        temp_archive.replace(archive)
        if not zipfile.is_zipfile(archive):
            archive.unlink(missing_ok=True)
            raise WeatherArchiveError(
                "Downloaded baseline archive is not a valid ZIP file",
                recovery="Retry the download or choose a local EPW file.",
            )
        with tempfile.TemporaryDirectory(prefix="future_epw_weather_") as td:
            td_path=Path(td)
            with zipfile.ZipFile(archive) as z:
                safe=[]
                for info in z.infolist():
                    target=(td_path / info.filename).resolve()
                    if td_path.resolve() not in target.parents and target != td_path.resolve():
                        raise WeatherArchiveError(
                            "Unsafe path detected in weather archive",
                            recovery="Do not use this archive; choose another station or a local EPW.",
                        )
                    if info.filename.lower().endswith(".epw"):
                        safe.append(info)
                if not safe:
                    raise WeatherEPWNotFoundError(
                        "Weather archive contains no EPW file",
                        recovery="Choose another catalog station or provide a local EPW.",
                    )
                preferred=[x for x in safe if Path(x.filename).name==record.preferred_epw_name]
                wmo=[x for x in safe if record.wmo in Path(x.filename).name]
                chosen=(preferred or wmo or safe)[0]
                z.extract(chosen,td_path)
                extracted=td_path / chosen.filename
                self._validate_epw(extracted,record)
                target=directory / Path(chosen.filename).name
                shutil.copy2(extracted,target)
        meta=parse_epw_metadata(target)
        payload={
            "catalog_id":record.id,"city":record.city,"station":meta.station,"wmo":meta.wmo,
            "latitude":meta.latitude,"longitude":meta.longitude,"hours":meta.hours,
            "source":record.source,"archive_url":archive_url,"archive_sha256":self._sha256(archive),
            "epw_filename":target.name,"epw_sha256":self._sha256(target),
            "downloaded_at":datetime.now(timezone.utc).isoformat(),
        }
        (directory / "metadata.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        return target
