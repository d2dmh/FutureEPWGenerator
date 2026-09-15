from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd
from config import EXPERIMENTS, FROZEN_CATALOG, OUTPUT_DIR, MODEL_CONFIG, SCENARIOS
from src.catalog import select_main_manifest, select_sftlf_manifest, audit_manifest
from src.workflow import build_case_matrix
from src.validation import sha256


def _selection_fingerprint(models, experiments, periods):
    raw=json.dumps({
        'models':list(models),
        'experiments':list(experiments),
        'periods':[str(x) for x in periods],
        'protocol':'R1',
    },sort_keys=True,separators=(',',':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def main(argv=None):
    ap=argparse.ArgumentParser(description='Stage 01: freeze/audit CMIP6 asset manifests.')
    ap.add_argument('--catalog',type=Path,default=FROZEN_CATALOG)
    ap.add_argument('--out-dir',type=Path,default=OUTPUT_DIR/'manifest')
    ap.add_argument('--models',nargs='+',default=list(MODEL_CONFIG))
    ap.add_argument('--experiments',nargs='+',default=list(EXPERIMENTS))
    ap.add_argument('--periods',nargs='+',default=['2040','2060'])
    args=ap.parse_args(argv)
    unknown_models=[m for m in args.models if m not in MODEL_CONFIG]
    if unknown_models: ap.error(f'unsupported models: {unknown_models}')
    allowed_experiments=set(EXPERIMENTS)
    unknown_exp=[e for e in args.experiments if e not in allowed_experiments]
    if unknown_exp: ap.error(f'unsupported experiments: {unknown_exp}')
    if 'historical' not in args.experiments: ap.error('--experiments must include historical')
    unknown_periods=[str(x) for x in args.periods if str(x) not in {'2040','2060'}]
    if unknown_periods: ap.error(f'unsupported periods: {unknown_periods}')

    cat=pd.read_csv(args.catalog,dtype={'version':str})
    main_manifest=select_main_manifest(cat,args.experiments,models=args.models)
    sftlf=select_sftlf_manifest(cat,models=args.models)
    audit=audit_manifest(main_manifest,args.experiments,models=args.models)
    if not audit['passed']: raise RuntimeError(f'Manifest audit failed: {audit}')
    args.out_dir.mkdir(parents=True,exist_ok=True)
    main_manifest.to_csv(args.out_dir/'manifest_cmip6.csv',index=False)
    sftlf.to_csv(args.out_dir/'manifest_sftlf.csv',index=False)
    scenarios=[e for e in args.experiments if e in SCENARIOS]
    cases=build_case_matrix(scenarios=scenarios,periods=args.periods,models=args.models)
    cases.to_csv(args.out_dir/'case_matrix.csv',index=False)
    meta={
        'catalog':str(args.catalog),'catalog_sha256':sha256(args.catalog),
        'main_assets':len(main_manifest),'sftlf_assets':len(sftlf),'case_count':len(cases),'audit':audit,
        'selection':{'models':list(args.models),'experiments':list(args.experiments),'periods':[str(x) for x in args.periods]},
        'selection_fingerprint':_selection_fingerprint(args.models,args.experiments,args.periods),
    }
    (args.out_dir/'manifest_metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(meta,indent=2,ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
