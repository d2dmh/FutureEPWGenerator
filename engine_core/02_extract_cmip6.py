from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from config import (
    CITIES, CACHE_DIR, CITY_CACHE_DIR, INPUT_EPW_DIR,
    ASSET_RETRIES, ASSET_TIMEOUT_SECONDS,
)
from src.cmip6_io import (
    open_public_cmip6_zarr, extract_asset_for_cities,
    cache_filename, cache_is_valid,
    city_cache_filename, city_cache_is_valid,
    process_manifest_assets_by_city, seed_city_cache_from_legacy,
)
from src.validation import resolve_city_epws
from src.epw import read_epw
from src.locations import locations_from_spec, location_summary

DEFAULT_PROVIDERS=('gcs','aws')


def _worker_command(job_path: Path):
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--engine-stage', '02_extract_cmip6.py', '--worker-job', str(job_path)]
    return [sys.executable, str(Path(__file__).resolve()), '--worker-job', str(job_path)]


def _locations(epw_dir, cities, location_spec=None):
    if location_spec is not None:
        return locations_from_spec(location_spec,cities)
    files=resolve_city_epws(epw_dir,cities)
    return {
        city:(read_epw(path).location.latitude,read_epw(path).location.longitude)
        for city,path in files.items()
    }


def _run_city_worker_subprocess(row, city, location, timeout, provider):
    """Run exactly one asset × city × provider in an isolated process."""
    with tempfile.TemporaryDirectory(prefix='cmip6_city_') as td:
        td=Path(td); job=td/'job.json'; out=td/'out.csv'
        payload={
            'row':{k:(v.item() if hasattr(v,'item') else v) for k,v in row.to_dict().items()},
            'city':str(city),
            'location':[float(location[0]),float(location[1])],
            'provider':provider,
            'output':str(out),
        }
        job.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
        cmd=_worker_command(job)
        try:
            cp=subprocess.run(cmd,timeout=timeout,check=False)
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f'{provider} city worker exceeded {timeout}s') from e
        if cp.returncode!=0:
            raise RuntimeError(f'{provider} city worker failed rc={cp.returncode}')
        if not out.exists():
            raise RuntimeError(f'{provider} city worker returned success without output CSV')
        return pd.read_csv(out,dtype={'version':str})


def _run_city_with_providers(row, city, location, timeout, providers, progress=print):
    failures=[]
    for provider in providers:
        if progress: progress(f'        provider={provider}: start')
        try:
            df=_run_city_worker_subprocess(row,city,location,timeout,provider)
            return df,provider
        except Exception as e:
            failures.append(f'{provider}: {e}')
            if progress: progress(f'        provider={provider}: failed: {e}')
    raise RuntimeError('all providers failed; '+' | '.join(failures))


# Backward-compatible helpers retained for tests/external callers. Stage 02 main
# now uses city-level workers instead of one whole-asset worker.
def _run_worker_subprocess(row, locations, timeout, provider):
    frames=[]
    for city,location in locations.items():
        frames.append(_run_city_worker_subprocess(row,city,location,timeout,provider))
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()


def _run_with_providers(row, locations, timeout, providers, progress=print):
    failures=[]
    for provider in providers:
        if progress: progress(f'    provider={provider}: start')
        try:
            return _run_worker_subprocess(row,locations,timeout,provider)
        except Exception as e:
            failures.append(f'{provider}: {e}')
            if progress: progress(f'    provider={provider}: failed: {e}')
    raise RuntimeError('all providers failed; '+' | '.join(failures))


def _worker(job_path: Path):
    job=json.loads(job_path.read_text(encoding='utf-8'))
    row=pd.Series(job['row'])
    city=str(job['city'])
    lat,lon=map(float,job['location'])
    provider=str(job.get('provider','gcs'))

    print(f'        [{provider}] opening metadata...',flush=True)
    ds=open_public_cmip6_zarr(str(row.zstore),provider=provider)
    print(f'        [{provider}] metadata opened',flush=True)
    try:
        print(f'        [{provider}] city {city}: start',flush=True)
        df=extract_asset_for_cities(ds,row,{city:(lat,lon)})
        df['provider']=provider
        print(f'        [{provider}] city {city}: done',flush=True)
        Path(job['output']).parent.mkdir(parents=True,exist_ok=True)
        df.to_csv(job['output'],index=False)
    finally:
        try: ds.close()
        except Exception: pass
        try: del ds
        except Exception: pass
        gc.collect()
    return 0


def _asset_key(row):
    return (str(row.source_id),str(row.experiment_id),str(row.variable_id))


def _promote_provider(order, winner):
    return [winner]+[p for p in order if p!=winner]


def main(argv=None):
    ap=argparse.ArgumentParser(
        description='Stage 02: city-checkpointed CMIP6 extraction with GCS/AWS fallback.'
    )
    ap.add_argument('--manifest',type=Path)
    ap.add_argument('--epw-dir',type=Path,default=INPUT_EPW_DIR)
    ap.add_argument('--location-spec',type=Path,help='Explicit city coordinates/baseline mapping for arbitrary-city projects.')
    ap.add_argument('--cities',nargs='+',default=None)
    ap.add_argument('--cache-dir',type=Path,default=CACHE_DIR,
                    help='Final asset-level cache consumed by Stage 03.')
    ap.add_argument('--city-cache-dir',type=Path,default=CITY_CACHE_DIR,
                    help='Fine-grained asset x city checkpoint cache.')
    ap.add_argument('--legacy-cache-dir',type=Path,help='Optional read-only legacy multi-city asset cache used for migration.')
    ap.add_argument('--legacy-city-cache-dir',type=Path,help='Optional read-only legacy city checkpoint cache used for migration.')
    ap.add_argument('--retries',type=int,default=ASSET_RETRIES)
    ap.add_argument('--timeout',type=int,default=ASSET_TIMEOUT_SECONDS,
                    help='Hard timeout in seconds for one provider x city worker.')
    ap.add_argument('--providers',nargs='+',choices=DEFAULT_PROVIDERS,default=list(DEFAULT_PROVIDERS),
                    help='Providers tried in order; successful fallback is promoted for the rest of that asset.')
    ap.add_argument('--status',action='store_true')
    ap.add_argument('--status-out',type=Path)
    ap.add_argument('--stop-file',type=Path,help='Optional pause flag checked between assets/cities.')
    ap.add_argument('--worker-job',type=Path,help=argparse.SUPPRESS)
    args=ap.parse_args(argv)

    if args.worker_job is not None:
        return _worker(args.worker_job)
    if args.manifest is None:
        ap.error('--manifest is required unless --worker-job is used')

    manifest=pd.read_csv(args.manifest,dtype={'version':str})
    if args.location_spec is not None:
        requested_cities=args.cities
    else:
        requested_cities=args.cities or list(CITIES)
    locations=_locations(args.epw_dir,requested_cities,args.location_spec)
    args.cities=list(locations)

    # One-time, read-only migration path for the original eight-city production
    # caches. Arbitrary new cities simply seed nothing and proceed to remote extraction.
    legacy_seeded=0
    if args.legacy_cache_dir is not None or args.legacy_city_cache_dir is not None:
        for row in manifest.itertuples(index=False):
            s=pd.Series(row._asdict())
            for city in locations:
                target=args.city_cache_dir/city_cache_filename(s,city)
                existed=city_cache_is_valid(target,s,city)
                if (not existed) and seed_city_cache_from_legacy(
                    s,city,target,legacy_asset_dir=args.legacy_cache_dir,legacy_city_dir=args.legacy_city_cache_dir
                ):
                    legacy_seeded+=1

    if args.status:
        complete_assets=0; city_cached=0; pending_assets=0
        for row in manifest.itertuples(index=False):
            s=pd.Series(row._asdict())
            if cache_is_valid(args.cache_dir/cache_filename(s),s,locations.keys()):
                complete_assets+=1
                continue
            pending_assets+=1
            for city in locations:
                city_cached+=int(city_cache_is_valid(
                    args.city_cache_dir/city_cache_filename(s,city),s,city
                ))
        current_city_total=len(manifest)*len(locations)
        current_city_complete=complete_assets*len(locations)+city_cached
        report={
            'total':len(manifest),
            'cached':complete_assets,
            'missing':len(manifest)-complete_assets,
            'complete_assets':complete_assets,
            'pending_assets':pending_assets,
            'city_cached_within_pending_assets':city_cached,
            'city_slots_within_pending_assets':pending_assets*len(locations),
            'current_city_complete':current_city_complete,
            'current_city_total':current_city_total,
            'cities':list(locations),
            'legacy_city_caches_seeded':legacy_seeded,
            'locations': (location_summary(args.location_spec,args.cities) if args.location_spec else
                          [{'city':city,'latitude':float(lat),'longitude':float(lon)} for city,(lat,lon) in locations.items()]),
        }
        if args.status_out:
            args.status_out.parent.mkdir(parents=True,exist_ok=True)
            args.status_out.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2)); return 0

    provider_orders={}

    def runner(row,city,location):
        key=_asset_key(row)
        order=provider_orders.setdefault(key,list(args.providers))
        df,winner=_run_city_with_providers(
            row,city,location,args.timeout,order,
            progress=lambda msg: print(msg,flush=True),
        )
        provider_orders[key]=_promote_provider(order,winner)
        return df

    should_stop=(lambda: bool(args.stop_file and args.stop_file.exists()))
    summary=process_manifest_assets_by_city(
        manifest,locations,args.cache_dir,args.city_cache_dir,runner,
        retries=args.retries,progress=lambda msg: print(msg,flush=True),should_stop=should_stop,
    )
    print(json.dumps(summary,indent=2)); return 0


if __name__=='__main__':
    raise SystemExit(main())
