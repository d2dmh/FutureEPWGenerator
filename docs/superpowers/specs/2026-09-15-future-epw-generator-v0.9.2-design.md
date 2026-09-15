# Future EPW Generator v0.9.2 Custom CMIP6 + Baseline Weather Library Design

**Status:** Approved design
**Base version:** v0.9.1 Functional MVP
**Target version:** v0.9.2 Functional MVP
**Date:** 2026-09-15

## 1. Goal

v0.9.2 adds two product capabilities without changing the validated morphing equations themselves:

1. **True custom CMIP6 execution:** the Climate page selection controls the Stage 01 manifest, Stage 02 remote extraction, Stage 03 factors, Stage 04 EPW generation, Stage 05 validation, progress denominator, ETA, and expected output count.
2. **Baseline Weather Library:** the Project page provides a searchable catalog of curated major-city baseline EPW stations. A user can search/select a city, download and validate the recommended EPW once, cache it in a global weather library, and copy it into a self-contained project. Local EPW browsing remains available.

The existing reproducible Protocol R1 mode remains available and must reproduce the same full 5-GCM × 3-SSP workflow as v0.9.1.

## 2. Non-goals

- Do not change BTWS/BWS morphing equations or variable-specific transformation rules.
- Do not change historical reference period 1985–2014.
- Do not add new SSP pathways beyond SSP1-2.6, SSP2-4.5, SSP3-7.0.
- Do not add new GCMs beyond the validated five-model set in v0.9.1.
- Do not bundle all third-party EPW binaries inside the application ZIP.
- Do not silently update or replace a baseline EPW already copied into an existing project.
- Do not make internet access mandatory when the selected baseline is already cached locally or the user supplies a local EPW.

## 3. Operating modes

### 3.1 Reproducible Mode

The current validated Protocol R1 behavior remains fixed:

- GCMs: ACCESS-CM2, GFDL-ESM4, MPI-ESM1-2-HR, IPSL-CM6A-LR, FGOALS-g3
- SSPs: SSP1-2.6, SSP2-4.5, SSP3-7.0
- Future windows: 2040 and 2060
- Variables: the existing ten Stage-02 variables
- Experiments per GCM: historical + ssp126 + ssp245 + ssp370
- Stage-02 climate assets: `5 × (1 + 3) × 10 = 200`
- Expected EPWs: 36 under the existing v0.9.1 output logic

Selections are locked in this mode.

### 3.2 Advanced / Custom Mode

The user may select any non-empty subset of:

- GCMs: 1–5 from the validated set
- SSPs: 1–3 from SSP126/245/370
- Future windows: 2040, 2060, or both

The software dynamically constructs only the required workflow subset.

#### Stage-02 asset count

The total is:

`selected_GCM_count × (1 historical + selected_SSP_count) × 10 variables`

Examples:

- 1 GCM + 1 SSP → 20 assets
- 1 GCM + 2 SSPs → 30 assets
- 2 GCMs + 2 SSPs → 60 assets
- 5 GCMs + 3 SSPs → 200 assets

2040/2060 do **not** multiply the Stage-02 count because both windows are extracted from the same scenario time series.

#### Output count

For each selected SSP × selected future window:

- one EPW per selected GCM
- plus one ensemble-mean EPW

Therefore:

`expected_epw = selected_SSP_count × selected_period_count × (selected_GCM_count + 1)`

Examples:

- 1 GCM × 1 SSP × 1 period → 2 EPWs
- 2 GCM × 1 SSP × 2 periods → 6 EPWs
- 5 GCM × 3 SSP × 2 periods → 36 EPWs

The ensemble mean for a one-GCM selection is still produced as a separate, explicitly named ensemble artifact for consistent downstream structure.

## 4. Dynamic workflow contract

A single project-level experiment specification becomes the source of truth for all stages.

### 4.1 Project experiment specification

Persist in `project.json` under `climate_selection`:

```json
{
  "mode": "advanced",
  "gcms": ["ACCESS-CM2"],
  "ssps": ["ssp126"],
  "periods": [2040],
  "protocol": "R1"
}
```

Reproducible mode persists the full fixed lists with `mode: "reproducible"`.

### 4.2 Stage 01

Stage 01 filters the frozen validated catalog instead of inventing new asset definitions.

For every selected GCM include:

- historical rows for the ten required variables
- only selected SSP experiment rows for the ten required variables
- required land/static rows remain available as defined by the validated catalog but are not counted in the Stage-02 dynamic denominator unless Stage 02 actually extracts them

The generated project manifest records the selection fingerprint.

### 4.3 Stage 02

Stage 02 consumes the project manifest rather than assuming 200 climate assets.

All UI and persisted state fields use:

- `asset_total = len(dynamic_stage02_manifest)`
- `asset_complete` = fully assembled project cache items
- `city_checkpoints` = resumable city extraction checkpoints
- `remote_ready` = union of complete assets and resumable checkpoints that do not require repeating remote extraction

No progress component may hard-code 200.

### 4.4 Stage 03

Climate-factor generation iterates only over selected GCMs, selected SSPs, and selected periods.

It must not require factors for unselected combinations.

Ensemble factors are calculated from the selected GCM subset only.

### 4.5 Stage 04

EPW generation creates only the expected selected outputs using the formula in Section 3.2.

File naming and metadata must continue to identify GCM/ensemble, SSP, and target period unambiguously.

### 4.6 Stage 05

Validation uses the dynamic expected output set. A project with 2 expected EPWs can PASS with 2/2 valid files; it must not require 36.

## 5. Preflight and provenance

Preflight checks become dynamic:

- baseline EPW fingerprint valid
- project location valid
- selected GCM list non-empty
- selected SSP list non-empty
- selected period list non-empty
- dynamic manifest present and selection fingerprint matches `project.json`
- Stage-02 complete count equals dynamic total
- factors present for exactly the required combinations
- project output path writable

Provenance must record:

- reproducible vs advanced mode
- selected GCMs
- selected SSPs
- selected periods
- dynamic Stage-02 asset total
- baseline EPW SHA-256 and source metadata

## 6. Climate page behavior

### Reproducible mode

- selections shown checked and locked
- expected 200 assets and 36 EPWs
- validated Protocol R1 badge

### Advanced mode

- checkboxes become editable
- at least one GCM, one SSP, and one period required
- live summary shows:
  - `CMIP6 assets required: N`
  - `Expected EPW outputs: M`
  - selection fingerprint
- Save persists the selection and invalidates stale downstream products if the selection changed

Changing a climate selection after extraction has started must not delete old cache files. The project manifest and state are recomputed, and already compatible cached assets are reused.

## 7. Baseline Weather Library

### 7.1 User experience

The Project page adds two baseline-source modes:

- **Weather Library**
- **Local EPW**

Weather Library provides:

- searchable city/station field
- keyboard-searchable dropdown results
- city, country/region, station name, WMO, latitude, longitude, dataset, period, source
- local availability status: `Not downloaded`, `Cached`, `Invalid cache`
- `Download & Use` or `Use Cached` action
- progress/error text during download and validation

Local EPW retains the existing Browse behavior.

### 7.2 Catalog architecture

Ship only catalog metadata with the application:

`assets/weather_catalog.json`

Each record contains:

```json
{
  "id": "JPN_Tokyo_Haneda_476710_TMYx_2009-2023",
  "city": "Tokyo",
  "country": "Japan",
  "country_code": "JPN",
  "region": "Tokyo",
  "station": "Tokyo Intl AP - Haneda",
  "wmo": "476710",
  "latitude": 35.5533,
  "longitude": 139.7811,
  "elevation_m": 10.7,
  "dataset": "TMYx",
  "period": "2009-2023",
  "source": "Climate.OneBuilding.org",
  "download_url": "https://climate.onebuilding.org/...zip",
  "preferred_epw_name": "...epw"
}
```

No project depends on a mutable online catalog at runtime. The catalog ships with the application version and is auditable.

### 7.3 First bundled catalog scope

The first v0.9.2 catalog contains at least these 40 major-city targets, each mapped to one recommended EPW station:

Beijing, Shanghai, Guangzhou, Shenzhen, Chengdu, Wuhan, Hong Kong, Tokyo, Seoul, Singapore, Delhi, Bangkok, Kuala Lumpur, Jakarta, Manila, Kuwait City, Dubai, Riyadh, London, Paris, Berlin, Madrid, Rome, Amsterdam, Stockholm, Copenhagen, New York, Los Angeles, Chicago, San Francisco, Toronto, Vancouver, Mexico City, Miami, Houston, Sydney, Melbourne, São Paulo, Cairo, Johannesburg.

Where an exact municipal station is unavailable, the catalog uses the nearest defensible major airport/weather station and displays the actual station name and coordinates instead of pretending it is the city center.

### 7.4 Global cache

Downloaded weather-library files are stored outside project folders under the user application-data directory, for example:

`FutureEPWGenerator/weather_library/<catalog-id>/`

The cache stores:

- downloaded source archive
- extracted EPW
- `metadata.json`
- EPW SHA-256
- download timestamp
- source URL

Settings and global library paths remain separate from project provenance.

### 7.5 Download validation pipeline

`Download & Use` performs:

1. HTTPS download
2. archive integrity check
3. locate preferred `.epw` or the single unambiguous EPW candidate
4. parse EPW header
5. verify 8760 hourly records
6. verify WMO when catalog WMO is present
7. verify coordinate difference is within a conservative tolerance of the catalog record
8. compute SHA-256
9. mark global cache valid
10. copy the EPW into the current project `inputs/baseline_epw/`
11. parse the copied EPW again and persist its project fingerprint

A download failure never alters an existing project's baseline.

### 7.6 Reproducibility rule

The weather library is only a convenience source. Once selected, the baseline EPW is copied into the project and fingerprinted. Future changes in the remote source or global cache do not modify the project copy.

## 8. City vs station data model

Project metadata separates:

- `city_name`: user-facing target city, e.g. `Tokyo`
- `station_name`: actual EPW station, e.g. `Tokyo.Intl.AP-Haneda.AP`
- WMO
- latitude/longitude/elevation

The Project Summary displays `city_name`, not a stale template value and not the raw station string.

For local EPWs, the initial city suggestion may be derived from the station name, but the user can edit `city_name` before saving.

Location-specific CMIP6 cache keys use normalized city name + coordinates + location fingerprint. Existing v0.9.1 cache directories remain readable; v0.9.2 must not require deleting prior cache data.

## 9. Project migration and invalidation

Existing v0.9/v0.9.1 projects open without manual migration.

If `climate_selection` is absent:

- infer reproducible mode when the project matches the full Protocol R1 configuration
- persist the inferred selection when the project is next saved

If the user changes GCM/SSP/period selections:

- preserve all compatible cached remote data
- regenerate the project manifest
- mark Stage 03–05 stale
- keep outputs on disk but do not report them as current until regenerated under the new selection

## 10. ETA and progress

ETA uses the dynamic Stage-02 total and the v0.9.1 rolling remote-extraction timing logic.

Display fields:

- Complete Assets `x / N`
- Pending `N - x`
- Failed
- City Checkpoints
- Remote Data Ready `r / N`
- Estimated Remaining Time

Cached assets are skipped and do not inflate remote timing samples.

## 11. Internationalization

All new UI labels, dialogs, download states, validation errors, weather-library messages, and custom-mode summaries are added to the existing English/Simplified Chinese i18n system.

Scientific identifiers remain untranslated where appropriate: CMIP6, SSP1-2.6, GCM names, WMO, TMYx, GCS, AWS, BTWS, BWS, tas, huss, etc.

## 12. Error handling

Weather Library distinguishes at least:

- network unavailable
- HTTP/download failure
- corrupt ZIP/archive
- EPW not found in archive
- EPW not 8760 hours
- station/WMO mismatch
- coordinate mismatch
- permission/write failure

Dynamic workflow distinguishes:

- empty selection
- stale manifest selection fingerprint
- incomplete dynamic cache
- stale factor/output set after configuration change

Technical details remain available in logs.

## 13. Tests and acceptance

### Dynamic selection acceptance

Tokyo smoke test:

- Advanced mode
- ACCESS-CM2 only
- SSP1-2.6 only
- 2040 only
- Stage-02 denominator = 20
- expected output = 2 EPWs
- extraction starts at 0/20 for a fresh Tokyo location
- pause/reopen/resume preserves dynamic denominator and completed count
- full run can PASS with 2/2 valid EPWs

Protocol regression:

- Reproducible mode remains 200 Stage-02 assets
- expected outputs remain 36
- existing Singapore v0.9.1 200/200 cache remains reusable

### Weather Library acceptance

- search `Tokyo` returns the curated Tokyo/Haneda record
- `Download & Use` yields a valid 8760-hour project baseline
- Project Summary displays Tokyo, not Singapore and not the raw station name
- reopening the project does not require internet access
- cached weather-library entry can be reused in a second project
- local EPW Browse path remains functional

## 14. Definition of done

v0.9.2 is complete only when:

1. dynamic Stage 01–05 execution follows the saved selection end to end;
2. no UI/state/preflight code assumes 200 assets or 36 outputs outside Reproducible Mode;
3. Tokyo 1-GCM/1-SSP/1-period project reports 20 assets and 2 expected EPWs;
4. existing full Protocol R1 projects still report 200 assets and 36 EPWs;
5. Weather Library search/download/cache/use works for curated catalog entries;
6. city and station metadata are separated and Project Summary is correct;
7. existing v0.9.1 projects and caches remain readable;
8. application tests, self-test, compile check, and engine regression tests pass;
9. scientific morphing equations remain unchanged.
