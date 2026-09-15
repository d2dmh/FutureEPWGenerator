from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

REQUIRED_VARIABLES = (
    'tas','tasmax','tasmin','huss','psl','sfcWind','clt','rsds','rlds','pr'
)
TABLE_ID = 'Amon'
EXPERIMENTS = ('historical','ssp126','ssp245','ssp370')
SCENARIOS = ('ssp126','ssp245','ssp370')

MODEL_CONFIG = {
    'ACCESS-CM2': ('r1i1p1f1','gn'),
    'GFDL-ESM4': ('r1i1p1f1','gr1'),
    'MPI-ESM1-2-HR': ('r1i1p1f1','gn'),
    'IPSL-CM6A-LR': ('r1i1p1f1','gr'),
    'FGOALS-g3': ('r2i1p1f1','gn'),
}

@dataclass(frozen=True)
class CitySpec:
    name: str
    wmo: str
    latitude: float
    longitude: float

CITIES = {
    'Delhi': CitySpec('Delhi','421820',28.58860,77.22220),
    'Singapore': CitySpec('Singapore','486980',1.36780,103.98260),
    'Kuwait City': CitySpec('Kuwait City','405820',29.22700,47.96900),
    'Beijing': CitySpec('Beijing','545110',40.08000,116.58500),
    'London': CitySpec('London','037720',51.47920,-0.45060),
    'Sydney': CitySpec('Sydney','947670',-33.94640,151.17310),
    'Madrid': CitySpec('Madrid','082210',40.46700,-3.55600),
    'Toronto': CitySpec('Toronto','716240',43.66580,-79.60620),
}

HISTORICAL_WINDOW = ('historical', 1985, 2014, '1985-2014')
FUTURE_WINDOWS = (
    ('ssp126',2030,2050,'2040'), ('ssp126',2050,2070,'2060'),
    ('ssp245',2030,2050,'2040'), ('ssp245',2050,2070,'2060'),
    ('ssp370',2030,2050,'2040'), ('ssp370',2050,2070,'2060'),
)

INPUT_EPW_DIR = PROJECT_ROOT / 'inputs' / 'baseline_epw'
FROZEN_CATALOG = PROJECT_ROOT / 'inputs' / 'catalog' / 'catalog_subset_205_assets.csv'
CACHE_DIR = PROJECT_ROOT / 'cache' / 'cmip6_monthly'
CITY_CACHE_DIR = PROJECT_ROOT / 'cache' / 'cmip6_monthly_city'
OUTPUT_DIR = PROJECT_ROOT / 'outputs'

ASSET_TIMEOUT_SECONDS = 300
ASSET_RETRIES = 3
