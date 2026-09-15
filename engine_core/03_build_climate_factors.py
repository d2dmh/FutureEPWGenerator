from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
from config import CACHE_DIR, OUTPUT_DIR, CITIES, MODEL_CONFIG, SCENARIOS
from src.cmip6_io import combine_cache
from src.factors import build_factors, ensemble_summary

def main(argv=None):
    ap=argparse.ArgumentParser(description='Stage 03: build monthly climate factors offline.')
    ap.add_argument('--climatology',type=Path)
    ap.add_argument('--manifest',type=Path)
    ap.add_argument('--cache-dir',type=Path,default=CACHE_DIR)
    ap.add_argument('--cities',nargs='+',default=list(CITIES))
    ap.add_argument('--out-dir',type=Path,default=OUTPUT_DIR/'factors')
    ap.add_argument('--models',nargs='+')
    ap.add_argument('--scenarios',nargs='+')
    ap.add_argument('--labels',nargs='+')
    args=ap.parse_args(argv)
    if args.climatology:
        clim=pd.read_csv(args.climatology)
    else:
        if args.manifest is None: ap.error('provide --climatology or --manifest')
        manifest=pd.read_csv(args.manifest,dtype={'version':str})
        clim=combine_cache(args.cache_dir,manifest,args.cities)
    models=list(args.models) if args.models else list(MODEL_CONFIG)
    scenarios=list(args.scenarios) if args.scenarios else list(SCENARIOS)
    labels=[str(x) for x in args.labels] if args.labels else ['2040','2060']
    per=build_factors(clim,models=models,scenarios=scenarios,target_labels=labels); ens=ensemble_summary(per)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    clim.to_csv(args.out_dir/'monthly_climatology_long.csv',index=False)
    per.to_csv(args.out_dir/'climate_factors_per_gcm.csv',index=False)
    ens.to_csv(args.out_dir/'climate_factors_ensemble.csv',index=False)

    fallback_mask=per['pr_dry_baseline_fallback'].astype(bool)
    fallback_cols=[
        'city','model','scenario','future_period','target_label','month',
        'r_pr','pr_dry_baseline_fallback',
    ]
    fallbacks=per.loc[fallback_mask,fallback_cols].copy()
    fallback_path=args.out_dir/'precipitation_dry_baseline_fallbacks.csv'
    fallbacks.to_csv(fallback_path,index=False)

    meta={
        'climatology_rows':len(clim),
        'per_gcm_rows':len(per),
        'ensemble_rows':len(ens),
        'pr_dry_baseline_fallback_rows':int(fallback_mask.sum()),
        'pr_dry_baseline_fallback_file':str(fallback_path),
        'models':models,'scenarios':scenarios,'labels':labels,
    }
    (args.out_dir/'factor_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
