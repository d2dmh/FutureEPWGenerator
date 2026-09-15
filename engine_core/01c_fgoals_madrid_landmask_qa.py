from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from config import INPUT_EPW_DIR, OUTPUT_DIR, ASSET_TIMEOUT_SECONDS
from src.cmip6_io import open_public_cmip6_zarr
from src.land_fraction import land_fraction_neighborhood
from src.validation import resolve_city_epws, sha256
from src.epw import read_epw

DEFAULT_PROVIDERS=('gcs','aws')


def _select_fgoals_row(manifest: pd.DataFrame) -> pd.Series:
    hit=manifest[(manifest.source_id.astype(str)=='FGOALS-g3')&(manifest.variable_id.astype(str)=='sftlf')]
    if len(hit)!=1: raise RuntimeError(f'Expected exactly one FGOALS-g3 sftlf asset, found {len(hit)}')
    return pd.Series(hit.iloc[0])


def _madrid_location(epw_dir):
    path=resolve_city_epws(epw_dir,['Madrid'])['Madrid']
    epw=read_epw(path)
    return (epw.location.latitude,epw.location.longitude)


def _run_worker(row,location,half_width,timeout,provider):
    with tempfile.TemporaryDirectory(prefix='fgoals_madrid_') as td:
        td=Path(td); job=td/'job.json'; out=td/'out.csv'
        payload={'row':{k:(v.item() if hasattr(v,'item') else v) for k,v in row.to_dict().items()},'location':list(map(float,location)),'half_width':int(half_width),'provider':provider,'output':str(out)}
        job.write_text(json.dumps(payload),encoding='utf-8')
        cmd=[sys.executable,str(Path(__file__).resolve()),'--worker-job',str(job)]
        try: cp=subprocess.run(cmd,timeout=timeout,check=False)
        except subprocess.TimeoutExpired as e: raise TimeoutError(f'{provider} FGOALS Madrid QA exceeded {timeout}s') from e
        if cp.returncode!=0: raise RuntimeError(f'{provider} FGOALS Madrid QA failed rc={cp.returncode}')
        if not out.exists(): raise RuntimeError('QA worker returned success without output')
        return pd.read_csv(out,dtype={'version':str})


def _worker(job_path: Path):
    job=json.loads(job_path.read_text(encoding='utf-8')); row=pd.Series(job['row']); provider=job['provider']
    print(f'    [{provider}] opening FGOALS-g3 sftlf...',flush=True)
    ds=open_public_cmip6_zarr(str(row.zstore),provider=provider)
    try:
        out=land_fraction_neighborhood(ds,row,*map(float,job['location']),half_width=int(job['half_width']))
        out['provider']=provider
        out.to_csv(job['output'],index=False)
        print(f'    [{provider}] neighborhood complete',flush=True)
    finally:
        try: ds.close()
        except Exception: pass
        try: del ds
        except Exception: pass
        gc.collect()
    return 0


def main(argv=None):
    ap=argparse.ArgumentParser(description='Stage 01c: independent FGOALS-g3 land-mask QA around Madrid.')
    ap.add_argument('--manifest',type=Path,default=OUTPUT_DIR/'manifest'/'manifest_sftlf.csv')
    ap.add_argument('--epw-dir',type=Path,default=INPUT_EPW_DIR)
    ap.add_argument('--out-dir',type=Path,default=OUTPUT_DIR/'diagnostics'/'fgoals_madrid_landmask_qa')
    ap.add_argument('--half-width',type=int,default=3,help='Native-grid cells on each side; 3 gives up to 7x7.')
    ap.add_argument('--timeout',type=int,default=ASSET_TIMEOUT_SECONDS)
    ap.add_argument('--providers',nargs='+',choices=DEFAULT_PROVIDERS,default=list(DEFAULT_PROVIDERS))
    ap.add_argument('--worker-job',type=Path,help=argparse.SUPPRESS)
    args=ap.parse_args(argv)
    if args.worker_job is not None: return _worker(args.worker_job)
    manifest=pd.read_csv(args.manifest,dtype={'version':str}); row=_select_fgoals_row(manifest); loc=_madrid_location(args.epw_dir)
    failures=[]; result=None; winner=None
    for provider in args.providers:
        print(f'provider={provider}: start',flush=True)
        try:
            result=_run_worker(row,loc,args.half_width,args.timeout,provider); winner=provider; break
        except Exception as e:
            failures.append(f'{provider}: {e}'); print(f'provider={provider}: failed: {e}',flush=True)
    if result is None: raise RuntimeError('all providers failed; '+' | '.join(failures))
    args.out_dir.mkdir(parents=True,exist_ok=True)
    detail=args.out_dir/'fgoals_madrid_sftlf_neighborhood.csv'; result.to_csv(detail,index=False)
    matrix=result.pivot(index='grid_lat',columns='grid_lon_geographic',values='sftlf_pct').sort_index(ascending=False)
    matrix.to_csv(args.out_dir/'fgoals_madrid_sftlf_matrix.csv')
    support=result[result.is_bilinear_support.astype(bool)].copy().sort_values('support_point')
    support.to_csv(args.out_dir/'fgoals_madrid_bilinear_support.csv',index=False)
    meta={
        'manifest':str(args.manifest),'manifest_sha256':sha256(args.manifest),'provider':winner,
        'target_city':'Madrid','target_lat':float(loc[0]),'target_lon':float(loc[1]),'half_width':int(args.half_width),
        'support_sftlf_pct':{str(r.support_point):float(r.sftlf_pct) for r in support.itertuples(index=False)},
        'diagnostic_only':True,'production_interpolation_changed':False,
    }
    (args.out_dir/'fgoals_madrid_landmask_qa_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    with pd.option_context('display.width',180,'display.max_columns',20):
        print('\nFGOALS-g3 sftlf around Madrid (% land; rows latitude, columns longitude):')
        print(matrix.round(1).to_string())
        print('\nBilinear support cells:')
        print(support[['support_point','grid_lat','grid_lon_geographic','sftlf_pct']].to_string(index=False))
    print(f'\nWrote: {args.out_dir}')
    return 0


if __name__=='__main__': raise SystemExit(main())
