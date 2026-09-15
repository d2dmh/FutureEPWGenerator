from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
from config import CITIES, SCENARIOS, MODEL_CONFIG, INPUT_EPW_DIR, OUTPUT_DIR
from src.workflow import build_case_matrix
from src.validation import find_city_epw, sha256
from src.locations import baselines_from_spec
from src.epw import generate_future_epw

def main(argv=None):
    ap=argparse.ArgumentParser(description='Stage 04: generate future EPWs offline from climate factors.')
    ap.add_argument('--per-gcm',type=Path,required=True)
    ap.add_argument('--ensemble',type=Path,required=True)
    ap.add_argument('--epw-dir',type=Path,default=INPUT_EPW_DIR)
    ap.add_argument('--location-spec',type=Path,help='Explicit city/baseline mapping for arbitrary-city projects.')
    ap.add_argument('--out-dir',type=Path,default=OUTPUT_DIR/'epw')
    ap.add_argument('--audit-dir',type=Path,default=OUTPUT_DIR/'audit')
    ap.add_argument('--cities',nargs='+',default=None)
    ap.add_argument('--scenarios',nargs='+',default=list(SCENARIOS))
    ap.add_argument('--labels',nargs='+',default=['2040','2060'])
    ap.add_argument('--selectors',nargs='+')
    args=ap.parse_args(argv)
    if args.location_spec is not None:
        spec_baselines=baselines_from_spec(args.location_spec,args.cities)
        args.cities=list(spec_baselines)
    else:
        spec_baselines=None
        args.cities=args.cities or list(CITIES)
    cases=build_case_matrix(args.cities)
    cases=cases[cases.scenario.isin(args.scenarios)&cases.target_label.astype(str).isin(list(map(str,args.labels)))]
    if args.selectors: cases=cases[cases.selector.isin(args.selectors)]
    records=[]; args.out_dir.mkdir(parents=True,exist_ok=True); args.audit_dir.mkdir(parents=True,exist_ok=True)
    baseline_map=spec_baselines
    total_cases=len(cases)
    for idx,r in enumerate(cases.itertuples(index=False),start=1):
        selector_name=r.selector if r.selector_type=='model' else f'ensemble-{r.selector}'
        print(f'[{idx}/{total_cases}] generate {r.city} {r.scenario} {r.target_label} {selector_name}',flush=True)
        base=baseline_map[r.city] if baseline_map is not None else find_city_epw(args.epw_dir,r.city)
        stem=f'{r.city}_{r.target_label}_{r.scenario}_{selector_name}'.replace(' ','_')
        out=args.out_dir/r.city/f'{stem}.epw'; audit=args.audit_dir/f'{stem}_audit.csv'
        factor=args.per_gcm if r.selector_type=='model' else args.ensemble
        kwargs={'model':r.selector,'ensemble_stat':None} if r.selector_type=='model' else {'model':None,'ensemble_stat':r.selector}
        result=generate_future_epw(base_epw=base,factor_csv=factor,output_epw=out,city=r.city,
                                   scenario=r.scenario,target_label=str(r.target_label),audit_csv=audit,**kwargs)
        records.append({'city':r.city,'scenario':r.scenario,'target_label':str(r.target_label),
                        'selector_type':r.selector_type,'selector':r.selector,'base_epw':str(base),
                        'base_sha256':sha256(base),**result})
    rec=pd.DataFrame(records); rec.to_csv(args.out_dir/'generation_records.csv',index=False)
    print(json.dumps({'generated':len(rec),'out_dir':str(args.out_dir)},indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
