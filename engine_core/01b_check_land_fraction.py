from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from config import CITIES, INPUT_EPW_DIR, OUTPUT_DIR, ASSET_TIMEOUT_SECONDS
from src.cmip6_io import open_public_cmip6_zarr
from src.land_fraction import diagnose_land_fraction_dataset
from src.validation import resolve_city_epws, sha256
from src.epw import read_epw

DEFAULT_PROVIDERS=('gcs','aws')
FOCUS_CITIES=('Singapore','Sydney','Kuwait City')


def _locations(epw_dir, cities):
    files=resolve_city_epws(epw_dir,cities)
    return {
        city:(read_epw(path).location.latitude,read_epw(path).location.longitude)
        for city,path in files.items()
    }


def _run_worker_subprocess(row, locations, timeout, provider):
    """Run one model sftlf diagnostic in an isolated process."""
    with tempfile.TemporaryDirectory(prefix='cmip6_sftlf_') as td:
        td=Path(td); job=td/'job.json'; support=td/'support.csv'; summary=td/'summary.csv'
        payload={
            'row':{k:(v.item() if hasattr(v,'item') else v) for k,v in row.to_dict().items()},
            'locations':{k:[float(v[0]),float(v[1])] for k,v in locations.items()},
            'provider':provider,
            'support_output':str(support),
            'summary_output':str(summary),
        }
        job.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
        cmd=[sys.executable,str(Path(__file__).resolve()),'--worker-job',str(job)]
        try:
            cp=subprocess.run(cmd,timeout=timeout,check=False)
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f'{provider} sftlf worker exceeded {timeout}s') from e
        if cp.returncode!=0:
            raise RuntimeError(f'{provider} sftlf worker failed rc={cp.returncode}')
        if not support.exists() or not summary.exists():
            raise RuntimeError(f'{provider} sftlf worker returned success without output CSVs')
        return pd.read_csv(support,dtype={'version':str}),pd.read_csv(summary,dtype={'version':str})


def _run_with_providers(row, locations, timeout, providers, progress=print):
    failures=[]
    for provider in providers:
        if progress: progress(f'    provider={provider}: start')
        try:
            support,summary=_run_worker_subprocess(row,locations,timeout,provider)
            return support,summary,provider
        except Exception as e:
            failures.append(f'{provider}: {e}')
            if progress: progress(f'    provider={provider}: failed: {e}')
    raise RuntimeError('all providers failed; '+' | '.join(failures))


def _worker(job_path: Path):
    job=json.loads(job_path.read_text(encoding='utf-8'))
    row=pd.Series(job['row'])
    locations={k:(float(v[0]),float(v[1])) for k,v in job['locations'].items()}
    provider=str(job.get('provider','gcs'))
    print(f'        [{provider}] opening sftlf metadata...',flush=True)
    ds=open_public_cmip6_zarr(str(row.zstore),provider=provider)
    print(f'        [{provider}] metadata opened',flush=True)
    try:
        support,summary=diagnose_land_fraction_dataset(ds,row,locations)
        support['provider']=provider; summary['provider']=provider
        Path(job['support_output']).parent.mkdir(parents=True,exist_ok=True)
        support.to_csv(job['support_output'],index=False)
        summary.to_csv(job['summary_output'],index=False)
        print(f'        [{provider}] {row.source_id}: {len(summary)} cities complete',flush=True)
    finally:
        try: ds.close()
        except Exception: pass
        try: del ds
        except Exception: pass
        gc.collect()
    return 0


def _print_summary(summary: pd.DataFrame):
    cols=['model','city','effective_land_fraction_pct',
          'sftlf_SW_pct','sftlf_SE_pct','sftlf_NW_pct','sftlf_NE_pct',
          'land_dominant_support_cells','ocean_dominant_support_cells',
          'weighted_majority_ocean','provider']
    view=summary[cols].copy()
    view['focus']=view['city'].isin(FOCUS_CITIES)
    view=view.sort_values(['focus','city','model'],ascending=[False,True,True]).drop(columns='focus')
    with pd.option_context('display.max_rows',None,'display.width',180,'display.max_colwidth',30):
        print('\nLand-fraction diagnostic summary (diagnostic only; interpolation is unchanged):')
        pct_cols=['effective_land_fraction_pct','sftlf_SW_pct','sftlf_SE_pct','sftlf_NW_pct','sftlf_NE_pct']
        print(view.to_string(index=False,formatters={c:(lambda x:f'{float(x):6.1f}') for c in pct_cols}))


def main(argv=None):
    ap=argparse.ArgumentParser(
        description='Stage 01b: diagnose model-specific sftlf at the four bilinear support cells for each city.'
    )
    ap.add_argument('--manifest',type=Path,default=OUTPUT_DIR/'manifest'/'manifest_sftlf.csv')
    ap.add_argument('--epw-dir',type=Path,default=INPUT_EPW_DIR)
    ap.add_argument('--cities',nargs='+',default=list(CITIES))
    ap.add_argument('--out-dir',type=Path,default=OUTPUT_DIR/'diagnostics'/'land_fraction')
    ap.add_argument('--timeout',type=int,default=ASSET_TIMEOUT_SECONDS,
                    help='Hard timeout in seconds for one provider x model sftlf diagnostic.')
    ap.add_argument('--providers',nargs='+',choices=DEFAULT_PROVIDERS,default=list(DEFAULT_PROVIDERS))
    ap.add_argument('--worker-job',type=Path,help=argparse.SUPPRESS)
    args=ap.parse_args(argv)

    if args.worker_job is not None:
        return _worker(args.worker_job)
    if not args.manifest.exists():
        raise FileNotFoundError(f'sftlf manifest not found: {args.manifest}; run 01_prepare_manifest.py first')

    manifest=pd.read_csv(args.manifest,dtype={'version':str})
    required={'source_id','experiment_id','member_id','grid_label','variable_id','zstore','version'}
    missing=sorted(required-set(manifest.columns))
    if missing:
        raise ValueError(f'sftlf manifest is missing required columns: {missing}')
    if set(manifest['variable_id'].astype(str))!={'sftlf'}:
        raise ValueError('Stage 01b requires a manifest containing only sftlf assets')
    locations=_locations(args.epw_dir,args.cities)

    support_frames=[]; summary_frames=[]
    total=len(manifest)
    for i,row in enumerate(manifest.itertuples(index=False),start=1):
        s=pd.Series(row._asdict())
        print(f'[{i}/{total}] diagnose {s.source_id} {s.experiment_id} sftlf',flush=True)
        support,summary,winner=_run_with_providers(
            s,locations,args.timeout,args.providers,progress=lambda msg:print(msg,flush=True)
        )
        # Keep the provider actually used explicit in both output tables.
        support['provider']=winner; summary['provider']=winner
        support_frames.append(support); summary_frames.append(summary)

    support_all=pd.concat(support_frames,ignore_index=True) if support_frames else pd.DataFrame()
    summary_all=pd.concat(summary_frames,ignore_index=True) if summary_frames else pd.DataFrame()
    support_all=support_all.sort_values(['model','city','support_point']).reset_index(drop=True)
    summary_all=summary_all.sort_values(['model','city']).reset_index(drop=True)

    args.out_dir.mkdir(parents=True,exist_ok=True)
    support_path=args.out_dir/'land_fraction_support_points.csv'
    summary_path=args.out_dir/'land_fraction_summary.csv'
    support_all.to_csv(support_path,index=False)
    summary_all.to_csv(summary_path,index=False)
    metadata={
        'manifest':str(args.manifest),
        'manifest_sha256':sha256(args.manifest),
        'models':int(summary_all['model'].nunique()) if not summary_all.empty else 0,
        'cities':list(locations),
        'summary_rows':int(len(summary_all)),
        'support_rows':int(len(support_all)),
        'focus_cities':list(FOCUS_CITIES),
        'diagnostic_only':True,
        'primary_interpolation_changed':False,
        'weighted_majority_ocean_definition':'effective_land_fraction_pct < 50',
    }
    (args.out_dir/'land_fraction_metadata.json').write_text(
        json.dumps(metadata,indent=2,ensure_ascii=False),encoding='utf-8'
    )
    _print_summary(summary_all)
    print(f'\nWrote: {support_path}')
    print(f'Wrote: {summary_path}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
