from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from config import CITIES, INPUT_EPW_DIR, OUTPUT_DIR, PROJECT_ROOT, ASSET_RETRIES, ASSET_TIMEOUT_SECONDS
from src.cmip6_io import open_public_cmip6_zarr
from src.coastal_sensitivity import (
    paired_climatology_for_asset_city,
    build_per_model_sensitivity,
    summarize_sensitivity,
    decision_table_from_monthly_summary,
)
from src.validation import resolve_city_epws, sha256
from src.epw import read_epw

DEFAULT_PROVIDERS=('gcs','aws')
FOCUS_CITIES=('Singapore','Sydney','Kuwait City')
FOCUS_VARIABLES=('tas','tasmax','tasmin','huss','sfcWind')
DEFAULT_CACHE_DIR=PROJECT_ROOT/'cache'/'coastal_sensitivity_city'


def _locations(epw_dir, cities):
    files=resolve_city_epws(epw_dir,cities)
    return {city:(read_epw(path).location.latitude,read_epw(path).location.longitude) for city,path in files.items()}


def _filter_manifest(manifest: pd.DataFrame, variables, scenarios):
    keep_exp={'historical',*map(str,scenarios)}
    out=manifest[
        manifest['variable_id'].astype(str).isin(list(map(str,variables))) &
        manifest['experiment_id'].astype(str).isin(keep_exp)
    ].copy()
    return out.sort_values(['source_id','experiment_id','variable_id']).reset_index(drop=True)


def _clean(x): return str(x).replace('/','_').replace('\\','_').replace(' ','_')


def _cache_filename(row,city):
    return f"{_clean(row.source_id)}__{_clean(row.experiment_id)}__{_clean(row.variable_id)}__{_clean(city)}.csv"


def _cache_valid(path: Path,row,city):
    if not path.exists(): return False
    try: df=pd.read_csv(path,dtype={'version':str})
    except Exception: return False
    required={'city','source_id','experiment_id','member_id','grid_label','variable_id','zstore','version','period','month','standard_value','land_aware_value'}
    if not required.issubset(df.columns): return False
    checks={
        'city':str(city),'source_id':str(row.source_id),'experiment_id':str(row.experiment_id),
        'member_id':str(row.member_id),'grid_label':str(row.grid_label),'variable_id':str(row.variable_id),
        'zstore':str(row.zstore),'version':str(row.version),
    }
    for col,val in checks.items():
        if set(df[col].astype(str))!={val}: return False
    expected={'1985-2014'} if str(row.experiment_id)=='historical' else {'2030-2050','2050-2070'}
    if set(df.period.astype(str))!=expected: return False
    sizes=df.groupby('period').size()
    if sizes.empty or not sizes.eq(12).all(): return False
    return True


def _atomic_write(df,path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.stem+'.',suffix='.tmp',dir=path.parent); os.close(fd)
    try:
        df.to_csv(tmp,index=False); os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def _run_worker_subprocess(row,city,location,support,timeout,provider):
    with tempfile.TemporaryDirectory(prefix='cmip6_coastal_') as td:
        td=Path(td); job=td/'job.json'; out=td/'out.csv'
        payload={
            'row':{k:(v.item() if hasattr(v,'item') else v) for k,v in row.to_dict().items()},
            'city':str(city),'location':[float(location[0]),float(location[1])],
            'support':support.to_dict(orient='records'),'provider':str(provider),'output':str(out),
        }
        job.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
        cmd=[sys.executable,str(Path(__file__).resolve()),'--worker-job',str(job)]
        try:
            cp=subprocess.run(cmd,timeout=timeout,check=False)
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f'{provider} coastal worker exceeded {timeout}s') from e
        if cp.returncode!=0: raise RuntimeError(f'{provider} coastal worker failed rc={cp.returncode}')
        if not out.exists(): raise RuntimeError(f'{provider} coastal worker returned success without output CSV')
        return pd.read_csv(out,dtype={'version':str})


def _run_with_providers(row,city,location,support,timeout,providers,progress=print):
    failures=[]
    for provider in providers:
        if progress: progress(f'        provider={provider}: start')
        try:
            return _run_worker_subprocess(row,city,location,support,timeout,provider),provider
        except Exception as e:
            failures.append(f'{provider}: {e}')
            if progress: progress(f'        provider={provider}: failed: {e}')
    raise RuntimeError('all providers failed; '+' | '.join(failures))


def _worker(job_path: Path):
    job=json.loads(job_path.read_text(encoding='utf-8'))
    row=pd.Series(job['row']); city=str(job['city']); location=tuple(map(float,job['location']))
    support=pd.DataFrame(job['support']); provider=str(job.get('provider','gcs'))
    print(f'        [{provider}] opening Amon metadata...',flush=True)
    ds=open_public_cmip6_zarr(str(row.zstore),provider=provider)
    print(f'        [{provider}] metadata opened',flush=True)
    try:
        print(f'        [{provider}] {city}: standard + land-aware start',flush=True)
        df=paired_climatology_for_asset_city(ds,row,city,location,support)
        df['provider']=provider
        Path(job['output']).parent.mkdir(parents=True,exist_ok=True)
        df.to_csv(job['output'],index=False)
        print(f'        [{provider}] {city}: done',flush=True)
    finally:
        try: ds.close()
        except Exception: pass
        try: del ds
        except Exception: pass
        gc.collect()
    return 0


def _support_for(land_support,model,city):
    hit=land_support[(land_support.model.astype(str)==str(model))&(land_support.city.astype(str)==str(city))].copy()
    if len(hit)!=4 or set(hit.support_point.astype(str))!={'SW','SE','NW','NE'}:
        raise RuntimeError(f'Need exactly four sftlf support rows for {model}/{city}; found {len(hit)}')
    return hit


def main(argv=None):
    ap=argparse.ArgumentParser(description='Stage 02b: coastal sensitivity of standard bilinear vs sftlf-weighted CMIP6 change signals.')
    ap.add_argument('--manifest',type=Path,default=OUTPUT_DIR/'manifest'/'manifest_cmip6.csv')
    ap.add_argument('--land-support',type=Path,default=OUTPUT_DIR/'diagnostics'/'land_fraction'/'land_fraction_support_points.csv')
    ap.add_argument('--epw-dir',type=Path,default=INPUT_EPW_DIR)
    ap.add_argument('--cities',nargs='+',default=list(FOCUS_CITIES))
    ap.add_argument('--variables',nargs='+',choices=FOCUS_VARIABLES,default=list(FOCUS_VARIABLES))
    ap.add_argument('--scenarios',nargs='+',choices=('ssp126','ssp245','ssp370'),default=['ssp126','ssp245','ssp370'])
    ap.add_argument('--cache-dir',type=Path,default=DEFAULT_CACHE_DIR)
    ap.add_argument('--out-dir',type=Path,default=OUTPUT_DIR/'diagnostics'/'coastal_sensitivity')
    ap.add_argument('--timeout',type=int,default=ASSET_TIMEOUT_SECONDS)
    ap.add_argument('--retries',type=int,default=ASSET_RETRIES)
    ap.add_argument('--providers',nargs='+',choices=DEFAULT_PROVIDERS,default=list(DEFAULT_PROVIDERS))
    ap.add_argument('--status',action='store_true')
    ap.add_argument('--worker-job',type=Path,help=argparse.SUPPRESS)
    args=ap.parse_args(argv)
    if args.worker_job is not None: return _worker(args.worker_job)
    if not args.manifest.exists(): raise FileNotFoundError(f'main manifest not found: {args.manifest}')
    if not args.land_support.exists(): raise FileNotFoundError(f'land support diagnostic not found: {args.land_support}; run 01b first')

    manifest=pd.read_csv(args.manifest,dtype={'version':str})
    land_support=pd.read_csv(args.land_support,dtype={'version':str})
    manifest=_filter_manifest(manifest,args.variables,args.scenarios)
    locations=_locations(args.epw_dir,args.cities)
    jobs=[(pd.Series(r._asdict()),city) for r in manifest.itertuples(index=False) for city in locations]
    cached=sum(_cache_valid(args.cache_dir/_cache_filename(row,city),row,city) for row,city in jobs)
    if args.status:
        report={'assets':len(manifest),'cities':list(locations),'city_jobs':len(jobs),'cached_city_jobs':int(cached),'missing_city_jobs':int(len(jobs)-cached)}
        print(json.dumps(report,indent=2)); return 0

    frames=[]; provider_orders={}; total=len(jobs)
    for idx,(row,city) in enumerate(jobs,start=1):
        path=args.cache_dir/_cache_filename(row,city)
        if _cache_valid(path,row,city):
            print(f'[{idx}/{total}] cached  {row.source_id} {row.experiment_id} {row.variable_id} | {city}',flush=True)
            frames.append(pd.read_csv(path,dtype={'version':str})); continue
        support=_support_for(land_support,row.source_id,city)
        key=(str(row.source_id),str(row.experiment_id),str(row.variable_id))
        order=provider_orders.setdefault(key,list(args.providers))
        last=None
        for attempt in range(1,args.retries+1):
            print(f'[{idx}/{total}] extract {row.source_id} {row.experiment_id} {row.variable_id} | {city} attempt {attempt}/{args.retries}',flush=True)
            try:
                df,winner=_run_with_providers(row,city,locations[city],support,args.timeout,order,progress=lambda m:print(m,flush=True))
                order=[winner]+[p for p in order if p!=winner]; provider_orders[key]=order
                _atomic_write(df,path); frames.append(df); last=None; break
            except Exception as e:
                last=e
        if last is not None:
            raise RuntimeError(f'Failed coastal sensitivity job after {args.retries} attempts: {row.source_id}/{row.experiment_id}/{row.variable_id}/{city}: {last}') from last

    paired=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    per=build_per_model_sensitivity(paired,scenarios=args.scenarios)
    monthly=summarize_sensitivity(per)
    decision=decision_table_from_monthly_summary(monthly)
    model_count=int(manifest['source_id'].astype(str).nunique())
    expected_per=len(locations)*model_count*len(args.scenarios)*2*12*len(args.variables)
    expected_monthly=len(locations)*len(args.scenarios)*2*12*len(args.variables)
    expected_decision=len(locations)*len(args.scenarios)*2*len(args.variables)
    if len(per)!=expected_per or len(monthly)!=expected_monthly or len(decision)!=expected_decision:
        raise RuntimeError(
            'Coastal sensitivity output is incomplete: '
            f'per_gcm={len(per)}/{expected_per}, monthly={len(monthly)}/{expected_monthly}, '
            f'decision={len(decision)}/{expected_decision}'
        )
    args.out_dir.mkdir(parents=True,exist_ok=True)
    paired.to_csv(args.out_dir/'coastal_paired_monthly_climatology.csv',index=False)
    per.to_csv(args.out_dir/'coastal_sensitivity_per_gcm.csv',index=False)
    monthly.to_csv(args.out_dir/'coastal_sensitivity_monthly_ensemble.csv',index=False)
    decision.to_csv(args.out_dir/'coastal_sensitivity_decision_screen.csv',index=False)
    meta={
        'manifest':str(args.manifest),'manifest_sha256':sha256(args.manifest),
        'land_support':str(args.land_support),'land_support_sha256':sha256(args.land_support),
        'cities':list(args.cities),'variables':list(args.variables),'scenarios':list(args.scenarios),
        'method_a':'standard bilinear','method_b':'bilinear weights multiplied by sftlf fraction and renormalized',
        'temperature_review_trigger':'|method difference| >= 0.2 C for any GCM-month; engineering review trigger only',
        'gcm_spread_screen':'monthly mean absolute method difference / standard-method inter-GCM SD',
        'final_method_decision':'not automated; requires downstream EPW/EnergyPlus/SET sensitivity if weather-level screen is material',
        'primary_stage02_changed':False,
        'expected_rows':{'per_gcm':expected_per,'monthly_ensemble':expected_monthly,'decision_screen':expected_decision},
        'actual_rows':{'per_gcm':len(per),'monthly_ensemble':len(monthly),'decision_screen':len(decision)},
    }
    (args.out_dir/'coastal_sensitivity_metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    with pd.option_context('display.max_rows',None,'display.width',180):
        print('\nDecision screen (weather-level only):')
        print(decision.to_string(index=False))
    print(f'\nWrote: {args.out_dir}')
    return 0


if __name__=='__main__': raise SystemExit(main())
