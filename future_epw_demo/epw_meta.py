from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EPWMetadata:
    path: Path
    station: str
    region: str
    country: str
    source: str
    wmo: str
    latitude: float
    longitude: float
    timezone: float
    elevation: float
    hours: int

    @property
    def valid(self) -> bool:
        return self.hours == 8760 and bool(self.wmo)


def parse_epw_metadata(path: Path | str) -> EPWMetadata:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    with p.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        first = handle.readline().rstrip("\r\n")
        if not first.upper().startswith("LOCATION,"):
            raise ValueError(f"{p.name}: first EPW line is not LOCATION")
        fields = next(csv.reader([first]))
        if len(fields) < 10:
            raise ValueError(f"{p.name}: malformed LOCATION line")
        # EPW has eight header lines. Count only hourly records after them.
        for _ in range(7):
            if handle.readline() == "":
                raise ValueError(f"{p.name}: incomplete EPW header")
        hours = sum(1 for line in handle if line.strip())
    return EPWMetadata(
        path=p,
        station=fields[1].strip(),
        region=fields[2].strip(),
        country=fields[3].strip(),
        source=fields[4].strip(),
        wmo=fields[5].strip().zfill(6),
        latitude=float(fields[6]),
        longitude=float(fields[7]),
        timezone=float(fields[8]),
        elevation=float(fields[9]),
        hours=hours,
    )
