from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
from config import OUTPUT_DIR
from src.validation import validate_epw_file, summarize_audits

def main(argv=None):
    ap=argparse.ArgumentParser(description='Stage 05: validate generated EPWs and target-vs-achieved audits.')
    ap.add_argument('--epw-dir',type=Path,default=OUTPUT_DIR/'epw')
    ap.add_argument('--audit-dir',type=Path,default=OUTPUT_DIR/'audit')
    ap.add_argument('--out-dir',type=Path,default=OUTPUT_DIR/'validation')
    args=ap.parse_args(argv)
    epws=sorted(args.epw_dir.rglob('*.epw'))
    rows=[validate_epw_file(p) for p in epws]
    summary=pd.DataFrame(rows)
    audits=summarize_audits(sorted(args.audit_dir.glob('*_audit.csv')))
    args.out_dir.mkdir(parents=True,exist_ok=True)
    summary.to_csv(args.out_dir/'validation_summary.csv',index=False)
    audits.to_csv(args.out_dir/'target_vs_achieved_summary.csv',index=False)
    passed=bool(len(summary)>0 and summary.passed.fillna(False).all())
    meta={'epw_count':len(summary),'audit_groups':len(audits),'passed':passed}
    (args.out_dir/'validation_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta,indent=2)); return 0 if passed else 1

if __name__=='__main__': raise SystemExit(main())
