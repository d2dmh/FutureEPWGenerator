from __future__ import annotations

import numpy as np
import pandas as pd

from .cmip6_io import (
    _find_coord_name, bilinear_support_table, _subset_dataset_for_experiment,
    _windows_for_experiment, monthly_climatology_from_series,
)

TEMPERATURE_VARIABLES = {'tas','tasmax','tasmin'}
RATIO_VARIABLES = {'huss','sfcWind'}


def _sorted_rectilinear(da):
    lat_name=_find_coord_name(da,('lat','latitude','nav_lat'))
    lon_name=_find_coord_name(da,('lon','longitude','nav_lon'))
    if not lat_name or not lon_name:
        raise RuntimeError('Cannot identify latitude/longitude coordinates')
    if da[lat_name].ndim!=1 or da[lon_name].ndim!=1:
        raise RuntimeError('Coastal sensitivity currently requires rectilinear 1D latitude/longitude coordinates')
    work=da
    if np.any(np.diff(np.asarray(work[lat_name].values,float))<0):
        work=work.sortby(lat_name)
    if np.any(np.diff(np.asarray(work[lon_name].values,float))<0):
        work=work.sortby(lon_name)
    return work,lat_name,lon_name


def _lon_close(a: float,b: float,tol: float) -> bool:
    d=((float(a)-float(b)+180.0)%360.0)-180.0
    return abs(d)<=tol


def land_aware_support_table(da, lat: float, lon: float, sftlf_support: pd.DataFrame, coordinate_tolerance: float=1e-6) -> pd.DataFrame:
    """Return production bilinear weights plus sftlf-renormalized land-aware weights.

    The CMIP6 variable grid is authoritative.  The supplied sftlf table is
    accepted only if its four support-cell coordinates match the variable's
    support cells.  This prevents silently applying a land mask from a
    different grid.
    """
    work,_,_=_sorted_rectilinear(da)
    support=bilinear_support_table(work,float(lat),float(lon)).copy()
    support=support.rename(columns={'weight':'standard_weight'})
    needed={'support_point','grid_lat','grid_lon_native','sftlf_pct'}
    missing=sorted(needed-set(sftlf_support.columns))
    if missing:
        raise ValueError(f'sftlf support table missing columns: {missing}')
    sf=sftlf_support.copy()
    if len(sf)!=4 or set(sf['support_point'].astype(str))!={'SW','SE','NW','NE'}:
        raise ValueError('sftlf support table must contain exactly SW/SE/NW/NE')
    sf=sf.set_index('support_point')

    pct=[]
    for rec in support.itertuples(index=False):
        s=sf.loc[str(rec.support_point)]
        if abs(float(s['grid_lat'])-float(rec.grid_lat))>coordinate_tolerance or not _lon_close(
            float(s['grid_lon_native']),float(rec.grid_lon_native),coordinate_tolerance
        ):
            raise RuntimeError(
                f'Grid mismatch for {rec.support_point}: variable cell '
                f'({rec.grid_lat},{rec.grid_lon_native}) vs sftlf cell '
                f'({s["grid_lat"]},{s["grid_lon_native"]})'
            )
        val=float(s['sftlf_pct'])
        if not np.isfinite(val) or val<-1e-6 or val>100.000001:
            raise RuntimeError(f'Invalid sftlf_pct={val} for {rec.support_point}')
        pct.append(val)
    support['sftlf_pct']=pct
    raw=support['standard_weight'].to_numpy(float)*(support['sftlf_pct'].to_numpy(float)/100.0)
    denom=float(raw.sum())
    if not np.isfinite(denom) or denom<=1e-12:
        raise RuntimeError('Land-aware interpolation has zero effective land weight across all support cells')
    support['land_aware_weight']=raw/denom
    if not np.isclose(float(support['land_aware_weight'].sum()),1.0,rtol=0,atol=1e-10):
        raise RuntimeError('Land-aware weights do not sum to one')
    return support


def extract_standard_and_land_aware_series(ds, variable: str, lat: float, lon: float, sftlf_support: pd.DataFrame):
    if variable not in ds:
        raise KeyError(f'{variable!r} not present in dataset')
    work,lat_name,lon_name=_sorted_rectilinear(ds[variable])
    support=land_aware_support_table(work,float(lat),float(lon),sftlf_support)
    extra=[d for d in work.dims if d not in {'time',lat_name,lon_name}]
    if extra:
        raise RuntimeError(f'{variable}: unexpected dimensions for coastal sensitivity: {extra}')

    standard=None; land=None
    for rec in support.itertuples(index=False):
        series=work.isel({lat_name:int(rec.lat_index),lon_name:int(rec.lon_index)})
        a=series*float(rec.standard_weight)
        b=series*float(rec.land_aware_weight)
        standard=a if standard is None else standard+a
        land=b if land is None else land+b
    standard.attrs=dict(work.attrs)
    land.attrs=dict(work.attrs)
    standard.attrs['extraction_method']='rectilinear_linear_manual_support'
    land.attrs['extraction_method']='rectilinear_land_fraction_weighted'
    standard.attrs['target_lat']=float(lat); standard.attrs['target_lon']=float(lon)
    land.attrs['target_lat']=float(lat); land.attrs['target_lon']=float(lon)
    return standard,land,support


def signal_kind(variable: str) -> str:
    if variable in TEMPERATURE_VARIABLES:
        return 'delta'
    if variable in RATIO_VARIABLES:
        return 'ratio'
    raise ValueError(f'Unsupported coastal sensitivity variable {variable!r}')


def climate_signal(future: float, historical: float, variable: str) -> float:
    kind=signal_kind(variable)
    if kind=='delta':
        return float(future)-float(historical)
    if abs(float(historical))<1e-12:
        raise ZeroDivisionError(f'{variable}: historical climatology is ~0')
    return float(future)/float(historical)


def summarize_sensitivity(per_model: pd.DataFrame) -> pd.DataFrame:
    required={
        'city','model','scenario','target_label','month','variable','signal_kind',
        'standard_signal','land_aware_signal','method_difference','absolute_method_difference'
    }
    missing=sorted(required-set(per_model.columns))
    if missing:
        raise ValueError(f'Sensitivity table missing columns: {missing}')
    group=['city','scenario','target_label','month','variable','signal_kind']
    rows=[]
    for keys,g in per_model.groupby(group,sort=True):
        rec=dict(zip(group,keys))
        std=g['standard_signal'].astype(float)
        land=g['land_aware_signal'].astype(float)
        diff=g['method_difference'].astype(float)
        absdiff=g['absolute_method_difference'].astype(float)
        spread=float(std.std(ddof=1)) if len(std)>1 else float('nan')
        mean_abs=float(absdiff.mean())
        if np.isfinite(spread) and spread>1e-12:
            ratio=mean_abs/spread
        elif mean_abs<=1e-12:
            ratio=0.0
        else:
            ratio=float('inf')
        rec.update({
            'model_count':int(len(g)),
            'standard_gcm_mean':float(std.mean()),
            'standard_gcm_std':spread,
            'land_aware_gcm_mean':float(land.mean()),
            'mean_method_difference':float(diff.mean()),
            'mean_abs_method_difference':mean_abs,
            'max_abs_method_difference':float(absdiff.max()),
            'method_to_gcm_spread_ratio':ratio,
            # Engineering review trigger only, not a scientific universal threshold.
            'temperature_0p2C_review_trigger':bool(
                rec['variable'] in TEMPERATURE_VARIABLES and float(absdiff.max())>=0.2
            ),
        })
        rows.append(rec)
    return pd.DataFrame(rows)


def build_per_model_sensitivity(paired_climatology: pd.DataFrame, scenarios=('ssp126','ssp245','ssp370')) -> pd.DataFrame:
    required={'city','model','experiment','period','target_label','variable','month','standard_value','land_aware_value','units'}
    missing=sorted(required-set(paired_climatology.columns))
    if missing:
        raise ValueError(f'Paired climatology missing columns: {missing}')
    rows=[]
    for city in sorted(paired_climatology.city.astype(str).unique()):
        c=paired_climatology[paired_climatology.city.astype(str)==city]
        for model in sorted(c.model.astype(str).unique()):
            m=c[c.model.astype(str)==model]
            for var in sorted(m.variable.astype(str).unique()):
                kind=signal_kind(var)
                for scenario in scenarios:
                    for period,label in [('2030-2050','2040'),('2050-2070','2060')]:
                        for month in sorted(m.month.astype(int).unique()):
                            h=m[(m.experiment=='historical')&(m.period=='1985-2014')&(m.variable==var)&(m.month.astype(int)==int(month))]
                            f=m[(m.experiment==scenario)&(m.period==period)&(m.variable==var)&(m.month.astype(int)==int(month))]
                            if len(h)!=1 or len(f)!=1:
                                continue
                            hs=float(h.iloc[0].standard_value); fs=float(f.iloc[0].standard_value)
                            hl=float(h.iloc[0].land_aware_value); fl=float(f.iloc[0].land_aware_value)
                            std_signal=climate_signal(fs,hs,var)
                            land_signal=climate_signal(fl,hl,var)
                            dstd=fs-hs; dland=fl-hl
                            rec={
                                'city':city,'model':model,'scenario':scenario,'future_period':period,
                                'target_label':label,'month':int(month),'variable':var,'units':str(f.iloc[0].units),
                                'signal_kind':kind,
                                'standard_historical':hs,'standard_future':fs,
                                'land_aware_historical':hl,'land_aware_future':fl,
                                'delta_change_standard':dstd,'delta_change_land_aware':dland,
                                'delta_change_method_difference':dland-dstd,
                                'standard_signal':std_signal,'land_aware_signal':land_signal,
                                'method_difference':land_signal-std_signal,
                                'absolute_method_difference':abs(land_signal-std_signal),
                                'relative_method_difference_pct':((land_signal-std_signal)/abs(std_signal)*100.0) if abs(std_signal)>1e-12 else np.nan,
                                'method_difference_percent_points':(land_signal-std_signal)*100.0 if kind=='ratio' else np.nan,
                            }
                            rows.append(rec)
    return pd.DataFrame(rows)


def decision_table_from_monthly_summary(monthly_summary: pd.DataFrame) -> pd.DataFrame:
    required={'city','scenario','target_label','month','variable','signal_kind','mean_abs_method_difference','max_abs_method_difference','method_to_gcm_spread_ratio','temperature_0p2C_review_trigger'}
    missing=sorted(required-set(monthly_summary.columns))
    if missing:
        raise ValueError(f'Monthly sensitivity summary missing columns: {missing}')
    group=['city','scenario','target_label','variable','signal_kind']
    rows=[]
    for keys,g in monthly_summary.groupby(group,sort=True):
        rec=dict(zip(group,keys))
        ratios=pd.to_numeric(g['method_to_gcm_spread_ratio'],errors='coerce').to_numpy(float)
        finite=ratios[np.isfinite(ratios)]
        max_ratio=float(np.max(finite)) if finite.size else (float('inf') if np.isinf(ratios).any() else np.nan)
        trigger_count=int(pd.Series(g['temperature_0p2C_review_trigger']).astype(bool).sum())
        rec.update({
            'max_mean_abs_method_difference':float(pd.to_numeric(g['mean_abs_method_difference']).max()),
            'max_abs_model_method_difference':float(pd.to_numeric(g['max_abs_method_difference']).max()),
            'max_method_to_gcm_spread_ratio':max_ratio,
            'temperature_review_trigger_months':trigger_count,
            # Only a weather-level screening flag. Final method choice still
            # requires the downstream EPW/EnergyPlus/SET sensitivity layer.
            'weather_level_review_required':bool(trigger_count>0 or (np.isfinite(max_ratio) and max_ratio>=0.5) or np.isinf(max_ratio)),
        })
        rows.append(rec)
    return pd.DataFrame(rows)


def paired_climatology_for_asset_city(ds, row: pd.Series, city: str, location, sftlf_support: pd.DataFrame) -> pd.DataFrame:
    variable=str(row.variable_id); experiment=str(row.experiment_id)
    lat,lon=map(float,location)
    work_ds=_subset_dataset_for_experiment(ds,variable,experiment)
    standard,land,support=extract_standard_and_land_aware_series(
        work_ds,variable,lat,lon,sftlf_support
    )
    eff=float((support['standard_weight']*support['sftlf_pct']).sum())
    rows=[]
    for start,end,label in _windows_for_experiment(experiment):
        std_vals,std_meta=monthly_climatology_from_series(standard,variable,start,end)
        land_vals,land_meta=monthly_climatology_from_series(land,variable,start,end)
        if std_meta['normalized_units']!=land_meta['normalized_units']:
            raise RuntimeError(f'{variable}: standard/land-aware unit mismatch')
        for month,(sv,lv) in enumerate(zip(std_vals,land_vals),start=1):
            rows.append({
                'city':str(city),'lat':lat,'lon':lon,
                'source_id':str(row.source_id),'model':str(row.source_id),
                'member_id':str(row.member_id),'grid_label':str(row.grid_label),
                'experiment_id':experiment,'experiment':experiment,
                'period':f'{start}-{end}','target_label':label,
                'variable_id':variable,'variable':variable,'month':int(month),
                'standard_value':float(sv),'land_aware_value':float(lv),
                'units':std_meta['normalized_units'],
                'effective_land_fraction_pct':eff,
                'standard_extraction_method':std_meta['extraction_method'],
                'land_aware_extraction_method':land_meta['extraction_method'],
                'zstore':str(row.zstore),'version':str(row.version),
            })
    return pd.DataFrame(rows)
