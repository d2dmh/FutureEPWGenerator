#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd


@dataclass(frozen=True)
class EpwLocation:
    city: str
    state_province: str
    country: str
    data_source: str
    wmo: str
    latitude: float
    longitude: float
    time_zone: float
    elevation_m: float


@dataclass
class EpwFile:
    header_lines: list[str]
    location: EpwLocation
    data: pd.DataFrame


def _parse_location(line: str) -> EpwLocation:
    p = line.rstrip('\n').split(',')
    if len(p) < 10 or p[0].strip().upper() != 'LOCATION':
        raise ValueError('EPW first line must be a LOCATION record with at least 10 fields')
    return EpwLocation(
        city=p[1].strip(),
        state_province=p[2].strip(),
        country=p[3].strip(),
        data_source=p[4].strip(),
        wmo=p[5].strip(),
        latitude=float(p[6]),
        longitude=float(p[7]),
        time_zone=float(p[8]),
        elevation_m=float(p[9]),
    )


def read_epw(path: Path | str) -> EpwFile:
    path = Path(path)
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    if len(lines) < 9:
        raise ValueError('EPW file is too short')
    header = lines[:8]
    loc = _parse_location(header[0])
    rows = [line.split(',') for line in lines[8:] if line.strip()]
    if any(len(r) != 35 for r in rows):
        bad = [i + 9 for i, r in enumerate(rows) if len(r) != 35][:5]
        raise ValueError(f'EPW data rows must have 35 fields; bad line(s): {bad}')
    return EpwFile(header, loc, pd.DataFrame(rows))

import numpy as np
from datetime import date
from src.morphing import extraterrestrial_normal, solar_elevation


def _num_col(epw: EpwFile, idx: int, name: str) -> np.ndarray:
    vals = pd.to_numeric(epw.data.iloc[:, idx], errors='coerce').to_numpy(dtype=float)
    if np.any(~np.isfinite(vals)):
        bad = (np.where(~np.isfinite(vals))[0][:5] + 9).tolist()
        raise ValueError(f'EPW {name} contains non-numeric/missing values at line(s) {bad}')
    return vals


def epw_to_morph_base(epw: EpwFile) -> pd.DataFrame:
    if len(epw.data) != 8760:
        raise ValueError(f'Expected a non-leap 8760-hour EPW, found {len(epw.data)} data rows')

    month = _num_col(epw, 1, 'month').astype(int)
    dom = _num_col(epw, 2, 'day-of-month').astype(int)
    hour = _num_col(epw, 3, 'hour').astype(int)
    doy = np.array([date(2001, int(m), int(d)).timetuple().tm_yday for m, d in zip(month, dom)], dtype=int)

    T = _num_col(epw, 6, 'dry-bulb temperature')
    Td = _num_col(epw, 7, 'dew-point temperature')
    RH = _num_col(epw, 8, 'relative humidity')
    P = _num_col(epw, 9, 'station pressure')
    IRH = _num_col(epw, 12, 'horizontal infrared radiation')
    GHI = _num_col(epw, 13, 'global horizontal radiation')
    DNI = _num_col(epw, 14, 'direct normal radiation')
    DHI = _num_col(epw, 15, 'diffuse horizontal radiation')
    wind_dir = _num_col(epw, 20, 'wind direction')
    V = _num_col(epw, 21, 'wind speed')
    Ntotal = _num_col(epw, 22, 'total sky cover')
    Nopaque = _num_col(epw, 23, 'opaque sky cover')
    Rain = _num_col(epw, 33, 'liquid precipitation depth')

    std_meridian = 15.0 * epw.location.time_zone
    elev = solar_elevation(doy, hour, epw.location.latitude, epw.location.longitude, std_meridian)
    Iext = extraterrestrial_normal(doy)

    return pd.DataFrame({
        'month': month, 'day': doy, 'hour': hour,
        'T': T, 'RH': RH, 'P': P, 'V': V, 'wind_dir': wind_dir,
        'Ntotal': Ntotal, 'Nopaque': Nopaque, 'GHI': GHI, 'DNI': DNI, 'DHI': DHI, 'Rain': Rain,
        'elev': elev, 'Iext': Iext, 'Td': Td, 'IRH': IRH,
    })


def _fmt(value: float, decimals: int = 1) -> str:
    if decimals == 0:
        return str(int(round(float(value))))
    return f'{float(value):.{decimals}f}'


def write_morphed_epw(epw: EpwFile, out: pd.DataFrame, path: Path | str, provenance: str = '') -> Path:
    if len(out) != len(epw.data):
        raise ValueError(f'Morphed weather has {len(out)} rows but source EPW has {len(epw.data)}')
    required = ['T1','Td1','RH1','P1','IRH1','GHI1','DNI1','DHI1','V1','Ntotal1','Nopaque1','Rain1']
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f'Morphed weather is missing output columns: {missing}')

    data = epw.data.copy()
    mappings = {
        6: ('T1', 1),
        7: ('Td1', 1),
        8: ('RH1', 0),
        9: ('P1', 0),
        12: ('IRH1', 0),
        13: ('GHI1', 0),
        14: ('DNI1', 0),
        15: ('DHI1', 0),
        21: ('V1', 1),
        22: ('Ntotal1', 0),
        23: ('Nopaque1', 0),
        33: ('Rain1', 1),
    }
    for idx, (col, dec) in mappings.items():
        data.iloc[:, idx] = [_fmt(v, dec) for v in out[col].to_numpy(dtype=float)]

    header = list(epw.header_lines)
    if provenance:
        prefix = 'COMMENTS 2,'
        existing = header[6][len(prefix):] if header[6].upper().startswith(prefix) else header[6]
        header[6] = f'{prefix}{existing}; {provenance}'

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as f:
        for line in header:
            f.write(line.rstrip('\n') + '\n')
        for row in data.itertuples(index=False, name=None):
            f.write(','.join(map(str, row)) + '\n')
    return path

from src.morphing import (
    specific_humidity, vapor_pressure_from_rh,
)


def compute_target_achieved(base: pd.DataFrame, out: pd.DataFrame, signal: dict) -> pd.DataFrame:
    """Return month-by-month target-versus-achieved factors before EPW serialization."""
    month = base['month'].to_numpy(dtype=int)
    rows = []

    q0 = specific_humidity(
        vapor_pressure_from_rh(base['T'].to_numpy(float), base['RH'].to_numpy(float)),
        base['P'].to_numpy(float),
    )
    q1 = specific_humidity(
        vapor_pressure_from_rh(out['T1'].to_numpy(float), out['RH1'].to_numpy(float)),
        out['P1'].to_numpy(float),
    )

    for m in range(1, 13):
        mask = month == m
        bm = base.loc[mask]
        om = out.loc[mask]

        # tas: CMIP6 monthly mean temperature anomaly.
        achieved = float(om['T1'].mean() - bm['T'].mean())
        target = float(np.asarray(signal['d_tas'])[m-1])
        rows.append((m, 'd_tas', target, achieved, 'degC'))

        # tasmax / tasmin: monthly mean of daily extrema.
        tmp = pd.DataFrame({
            'day': bm['day'].to_numpy(),
            't0': bm['T'].to_numpy(),
            't1': om['T1'].to_numpy(),
        })
        g = tmp.groupby('day')
        achieved_max = float((g['t1'].max() - g['t0'].max()).mean())
        achieved_min = float((g['t1'].min() - g['t0'].min()).mean())
        for factor, target_arr, value in (
            ('d_tasmax', signal['d_tasmax'], achieved_max),
            ('d_tasmin', signal['d_tasmin'], achieved_min),
        ):
            target = float(np.asarray(target_arr)[m-1])
            rows.append((m, factor, target, value, 'degC'))

        ratio_huss = float(np.mean(q1[mask]) / np.mean(q0[mask]))
        rows.append((m, 'r_huss', float(np.asarray(signal['r_huss'])[m-1]), ratio_huss, 'ratio'))

        d_p = float(om['P1'].mean() - bm['P'].mean())
        rows.append((m, 'd_psl_pa', float(np.asarray(signal['d_psl_pa'])[m-1]), d_p, 'Pa'))

        v0 = float(bm['V'].mean())
        ratio_v = float(om['V1'].mean() / v0) if abs(v0) > 1e-12 else np.nan
        rows.append((m, 'r_wind', float(np.asarray(signal['r_wind'])[m-1]), ratio_v, 'ratio'))

        d_clt = float((om['Ntotal1'].mean() - bm['Ntotal'].mean()) * 10.0)
        rows.append((m, 'd_clt', float(np.asarray(signal['d_clt'])[m-1]), d_clt, 'percentage_point'))

        d_rsds = float(om['GHI1'].mean() - bm['GHI'].mean())
        rows.append((m, 'd_rsds', float(np.asarray(signal['d_rsds'])[m-1]), d_rsds, 'W m-2'))

        d_rlds = float(om['IRH1'].mean() - bm['IRH'].mean())
        target_rlds = signal.get('d_rlds', None)
        target_rlds_val = np.nan if target_rlds is None else float(np.asarray(target_rlds)[m-1])
        rows.append((m, 'd_rlds', target_rlds_val, d_rlds, 'W m-2'))

        p0 = float(bm['Rain'].sum())
        ratio_pr = float(om['Rain1'].sum() / p0) if abs(p0) > 1e-12 else np.nan
        rows.append((m, 'r_pr', float(np.asarray(signal['r_pr'])[m-1]), ratio_pr, 'ratio'))

    df = pd.DataFrame(rows, columns=['month','factor','target','achieved','units'])
    df['error'] = df['achieved'] - df['target']
    df['abs_error'] = df['error'].abs()
    return df

SIGNAL_FIELDS = [
    'd_tas','d_tasmax','d_tasmin','r_huss','d_psl_pa',
    'r_wind','d_clt','d_rsds','d_rlds','r_pr',
]


def load_signal_from_factor_csv(
    path: Path | str,
    *,
    city: str,
    scenario: str,
    target_label: str,
    model: str | None = None,
    ensemble_stat: str | None = None,
) -> dict[str, np.ndarray]:
    df = pd.read_csv(path)
    required = {'city','scenario','target_label','month',*SIGNAL_FIELDS}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f'Factor CSV is missing required columns: {missing}')

    sel = df[(df['city'] == city) & (df['scenario'] == scenario) & (df['target_label'].astype(str) == str(target_label))].copy()
    if model is not None:
        if 'model' not in sel.columns:
            raise ValueError("Requested model selection but factor CSV has no 'model' column")
        sel = sel[sel['model'] == model]
    if ensemble_stat is not None:
        if 'ensemble_stat' not in sel.columns:
            raise ValueError("Requested ensemble_stat selection but factor CSV has no 'ensemble_stat' column")
        sel = sel[sel['ensemble_stat'] == ensemble_stat]
    if (model is None) == (ensemble_stat is None):
        raise ValueError('Specify exactly one of model= or ensemble_stat=')

    sel = sel.sort_values('month')
    months = sel['month'].astype(int).tolist()
    if months != list(range(1, 13)):
        raise ValueError(f'Factor selection must contain exactly months 1..12 once each; got {months}')
    return {field: sel[field].to_numpy(dtype=float) for field in SIGNAL_FIELDS}

from src.morphing import morph


def _future_base_to_out(future: pd.DataFrame) -> pd.DataFrame:
    out = future.copy()
    for src, dst in {
        'T':'T1','RH':'RH1','P':'P1','V':'V1','Ntotal':'Ntotal1','Nopaque':'Nopaque1',
        'GHI':'GHI1','DNI':'DNI1','DHI':'DHI1','Rain':'Rain1','Td':'Td1','IRH':'IRH1',
    }.items():
        out[dst] = future[src].to_numpy()
    return out


def generate_future_epw(
    *,
    base_epw: Path | str,
    factor_csv: Path | str,
    output_epw: Path | str,
    city: str,
    scenario: str,
    target_label: str,
    model: str | None = None,
    ensemble_stat: str | None = None,
    audit_csv: Path | str | None = None,
) -> dict:
    epw = read_epw(base_epw)
    base = epw_to_morph_base(epw)
    signal = load_signal_from_factor_csv(
        factor_csv, city=city, scenario=scenario, target_label=target_label,
        model=model, ensemble_stat=ensemble_stat,
    )
    out = morph(base, signal)

    selector = f'model={model}' if model is not None else f'ensemble_stat={ensemble_stat}'
    provenance = f'CMIP6 morphed weather; {city}; {scenario}; target={target_label}; {selector}'
    write_morphed_epw(epw, out, output_epw, provenance=provenance)

    pre = compute_target_achieved(base, out, signal)
    pre.insert(0, 'stage', 'pre_serialization')

    reread = epw_to_morph_base(read_epw(output_epw))
    post_out = _future_base_to_out(reread)
    post = compute_target_achieved(base, post_out, signal)
    post.insert(0, 'stage', 'post_serialization')
    audit = pd.concat([pre, post], ignore_index=True)
    audit.insert(1, 'city', city)
    audit.insert(2, 'scenario', scenario)
    audit.insert(3, 'target_label', str(target_label))
    audit.insert(4, 'model', model if model is not None else '')
    audit.insert(5, 'ensemble_stat', ensemble_stat if ensemble_stat is not None else '')
    if audit_csv is not None:
        audit_path = Path(audit_csv)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit.to_csv(audit_path, index=False)

    btws = out.attrs.get('btws_diagnostics', {})
    return {
        'output_epw': str(output_epw),
        'audit_csv': str(audit_csv) if audit_csv is not None else None,
        'btws_fallback_total': int(btws.get('fallback_total', 0)),
        'rlds_mode': out.attrs.get('rlds_mode', 'unknown'),
        'shortwave_partition_mode': out.attrs.get('shortwave_partition_mode', 'unknown'),
        'max_abs_error_pre': float(pre['abs_error'].max(skipna=True)),
        'max_abs_error_post': float(post['abs_error'].max(skipna=True)),
    }

import argparse
import hashlib
import json


def _sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


