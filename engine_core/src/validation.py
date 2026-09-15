from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from config import CITIES
from src.epw import read_epw, epw_to_morph_base


def sha256(path: Path|str) -> str:
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def find_city_epw(epw_dir: Path|str, city: str) -> Path:
    spec=CITIES[city]
    hits=[]
    for p in Path(epw_dir).rglob('*.epw'):
        try:
            loc=read_epw(p).location
        except Exception:
            continue
        if str(loc.wmo).zfill(6)==str(spec.wmo).zfill(6): hits.append(p)
    if len(hits)!=1:
        raise RuntimeError(f'{city}: expected exactly one EPW with WMO {spec.wmo}, found {len(hits)}')
    return hits[0]


def resolve_city_epws(epw_dir: Path|str, cities) -> dict[str,Path]:
    return {city:find_city_epw(epw_dir,city) for city in cities}


def validate_epw_file(path: Path|str) -> dict:
    p=Path(path)
    try:
        epw=read_epw(p); base=epw_to_morph_base(epw)
        checks={
            'rows_8760':len(base)==8760,
            'T':bool(base['T'].between(-100,70).all()),
            'RH':bool(base['RH'].between(0,110).all()),
            'P':bool(base['P'].between(30000,120000).all()),
            'wind':bool(base['V'].between(0,100).all()),
            'sky_total':bool(base['Ntotal'].between(0,10).all()),
            'sky_opaque':bool(base['Nopaque'].between(0,10).all()),
            'radiation_nonnegative':bool((base[['GHI','DNI','DHI','IRH']]>=0).all().all()),
            'rain_nonnegative':bool((base['Rain']>=0).all()),
            'finite_core':bool(np.isfinite(base[['T','RH','P','V','GHI','DNI','DHI','IRH']]).all().all()),
        }
        return {'file':str(p),'sha256':sha256(p),'wmo':epw.location.wmo,
                'latitude':epw.location.latitude,'longitude':epw.location.longitude,
                'rows':len(base),'passed':all(checks.values()),**checks}
    except Exception as e:
        return {'file':str(p),'sha256':sha256(p) if p.exists() else '', 'passed':False,'error':repr(e)}


def validate_baseline_epws(epw_dir: Path|str, cities) -> dict:
    rows=[]; errors=[]
    for city in cities:
        try:
            p=find_city_epw(epw_dir,city); r=validate_epw_file(p); r['city']=city; rows.append(r)
        except Exception as e:
            errors.append({'city':city,'error':repr(e)})
    return {'passed':bool(len(rows)==len(list(cities)) and all(r.get('passed',False) for r in rows) and not errors),
            'files':rows,'errors':errors}


def summarize_audits(audit_paths) -> pd.DataFrame:
    frames=[]
    for p in audit_paths:
        df=pd.read_csv(p)
        if 'stage' in df.columns: df=df[df.stage=='post_serialization'].copy()
        if df.empty: continue
        if 'abs_error' not in df.columns: df['abs_error']=(df.achieved-df.target).abs()
        frames.append(df)
    if not frames: return pd.DataFrame()
    df=pd.concat(frames,ignore_index=True)
    group=[c for c in ['stage','city','scenario','target_label','model','ensemble_stat','factor'] if c in df.columns]
    return df.groupby(group,dropna=False,as_index=False).agg(max_abs_error=('abs_error','max'),mean_abs_error=('abs_error','mean'),n_months=('month','count'))
