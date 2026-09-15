from __future__ import annotations
import argparse, importlib, json, platform, sys
from pathlib import Path
import numpy as np
import xarray as xr
from config import CITIES, INPUT_EPW_DIR, OUTPUT_DIR
from src.validation import validate_baseline_epws, validate_epw_file
from src.locations import load_location_spec

LOCAL_PACKAGES=('numpy','pandas','xarray','scipy','fsspec')
REMOTE_PACKAGES=('zarr','gcsfs','s3fs','cftime')

def _versions(names):
    out={}; missing=[]
    for name in names:
        try:
            m=importlib.import_module(name); out[name]=getattr(m,'__version__','installed')
        except Exception as e:
            out[name]=None; missing.append(f'{name}: {e}')
    return out,missing

def _interp_smoke():
    a=xr.DataArray(np.array([[0.,2.],[1.,3.]]),dims=('lat','lon'),coords={'lat':[0.,1.],'lon':[10.,11.]})
    v=float(a.interp(lat=0.5,lon=10.5,method='linear').values)
    return abs(v-1.5)<1e-12

def main(argv=None):
    ap=argparse.ArgumentParser(description='Stage 00: validate Python environment and baseline EPWs.')
    ap.add_argument('--epw-dir',type=Path,default=INPUT_EPW_DIR)
    ap.add_argument('--cities',nargs='+',default=None)
    ap.add_argument('--out',type=Path,default=OUTPUT_DIR/'environment_report.json')
    ap.add_argument('--location-spec',type=Path,help='Explicit city/location/baseline mapping for arbitrary-city projects.')
    ap.add_argument('--skip-remote-package-check',action='store_true')
    args=ap.parse_args(argv)
    local,missing_local=_versions(LOCAL_PACKAGES)
    remote,missing_remote=_versions(REMOTE_PACKAGES)
    if args.location_spec:
        files=[]; errors=[]
        for rec in load_location_spec(args.location_spec):
            try:
                r=validate_epw_file(rec.baseline_epw); r['city']=rec.city
                # The production GUI currently locks extraction coordinates to the EPW station.
                if r.get('passed'):
                    if rec.coordinate_source == 'epw':
                        if abs(float(r.get('latitude'))-rec.latitude)>1e-6 or abs(float(r.get('longitude'))-rec.longitude)>1e-6:
                            r['passed']=False; r['location_error']='EPW-coordinate mode requires location spec coordinates to match the baseline EPW'
                    if rec.wmo and str(r.get('wmo','')).zfill(6)!=str(rec.wmo).zfill(6):
                        r['passed']=False; r['wmo_error']='location spec WMO does not match baseline EPW'
                files.append(r)
            except Exception as e:
                errors.append({'city':rec.city,'error':repr(e)})
        baselines={'passed':bool(files and all(r.get('passed',False) for r in files) and not errors),
                   'files':files,'errors':errors}
    else:
        baselines=validate_baseline_epws(args.epw_dir,args.cities or list(CITIES))
    report={'python':sys.version,'platform':platform.platform(),'local_packages':local,'remote_packages':remote,
            'interpolation_smoke_passed':_interp_smoke(),'baseline_epw':baselines,
            'missing_local_packages':missing_local,'missing_remote_packages':missing_remote}
    passed=not missing_local and report['interpolation_smoke_passed'] and baselines['passed']
    if not args.skip_remote_package_check: passed=passed and not missing_remote
    report['passed']=passed
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'passed':passed,'baseline_files':len(baselines['files']),'missing_remote':missing_remote},ensure_ascii=False,indent=2))
    return 0 if passed else 1

if __name__=='__main__': raise SystemExit(main())
