from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from .cmip6_io import _find_coord_name, bilinear_support_table


def _normalize_sftlf(values, units: str):
    arr=np.asarray(values,dtype=float)
    source_units=(units or '').strip()
    note='none'
    if source_units.lower() in {'1','fraction','unitless',''} and np.nanmax(np.abs(arr))<=1.5:
        arr=arr*100.0
        note='fraction_to_percent'
    if np.any(~np.isfinite(arr)):
        raise RuntimeError('sftlf contains NaN/Inf at required support cells')
    if np.nanmin(arr)<-1e-6 or np.nanmax(arr)>100.000001:
        raise RuntimeError(f'sftlf values outside expected 0-100% range: min={np.nanmin(arr)}, max={np.nanmax(arr)}')
    return arr,source_units,note


def diagnose_land_fraction_dataset(ds, row: pd.Series, locations: Mapping[str, tuple[float,float]]):
    """Diagnose land fraction at the four support cells used by bilinear interpolation.

    Returns a detailed support-cell table and one summary row per city.  The
    result is observational only and is not used to alter CMIP6 extraction.
    """
    if 'sftlf' not in ds:
        raise KeyError("Variable 'sftlf' not present in dataset")
    da=ds['sftlf']
    lat_name=_find_coord_name(da,('lat','latitude','nav_lat'))
    lon_name=_find_coord_name(da,('lon','longitude','nav_lon'))
    if not lat_name or not lon_name:
        raise RuntimeError('Cannot identify latitude/longitude coordinates for sftlf')
    if da[lat_name].ndim!=1 or da[lon_name].ndim!=1:
        raise RuntimeError('sftlf diagnostic currently requires a rectilinear 1D lat/lon grid')

    work=da
    if np.any(np.diff(np.asarray(work[lat_name].values,float))<0):
        work=work.sortby(lat_name)
    if np.any(np.diff(np.asarray(work[lon_name].values,float))<0):
        work=work.sortby(lon_name)
    # Fixed fields should be 2-D; tolerate singleton bookkeeping dimensions.
    work=work.squeeze(drop=True)
    extra=[d for d in work.dims if d not in {lat_name,lon_name}]
    if extra:
        raise RuntimeError(f'sftlf has unexpected non-spatial dimensions after squeeze: {extra}')

    detail_rows=[]; summary_rows=[]
    for city,(lat,lon) in locations.items():
        support=bilinear_support_table(work,float(lat),float(lon))
        raw=[]
        for rec in support.itertuples(index=False):
            value=work.isel({lat_name:int(rec.lat_index),lon_name:int(rec.lon_index)}).values
            value=np.asarray(value).squeeze()
            if value.size!=1:
                raise RuntimeError(f'{row.source_id} / {city}: sftlf support lookup was not scalar')
            raw.append(float(value))
        pct,source_units,note=_normalize_sftlf(raw,str(work.attrs.get('units','')))
        support=support.copy()
        support['sftlf_pct']=pct
        support['source_units']=source_units
        support['normalization_note']=note
        support['bilinear_weight']=support.pop('weight')
        support['land_weight_contribution_pct']=support['bilinear_weight']*support['sftlf_pct']
        support['city']=str(city)
        support['source_id']=str(row.source_id)
        support['model']=str(row.source_id)
        support['member_id']=str(row.member_id)
        support['grid_label']=str(row.grid_label)
        support['experiment_id']=str(row.experiment_id)
        support['zstore']=str(row.zstore)
        support['version']=str(row.version)
        detail_rows.append(support)

        active=support[support['bilinear_weight']>1e-12]
        eff=float(support['land_weight_contribution_pct'].sum())
        by_point=support.set_index('support_point')
        summary_rows.append({
            'source_id':str(row.source_id),'model':str(row.source_id),
            'member_id':str(row.member_id),'grid_label':str(row.grid_label),
            'experiment_id':str(row.experiment_id),'city':str(city),
            'target_lat':float(lat),'target_lon':float(lon),
            'effective_land_fraction_pct':eff,
            'effective_ocean_fraction_pct':100.0-eff,
            'min_support_sftlf_pct':float(active['sftlf_pct'].min()),
            'max_support_sftlf_pct':float(active['sftlf_pct'].max()),
            'active_support_cells':int(len(active)),
            'land_dominant_support_cells':int((active['sftlf_pct']>=50.0).sum()),
            'ocean_dominant_support_cells':int((active['sftlf_pct']<50.0).sum()),
            'has_ocean_dominant_support':bool((active['sftlf_pct']<50.0).any()),
            'weighted_majority_ocean':bool(eff<50.0),
            'sftlf_SW_pct':float(by_point.loc['SW','sftlf_pct']),
            'sftlf_SE_pct':float(by_point.loc['SE','sftlf_pct']),
            'sftlf_NW_pct':float(by_point.loc['NW','sftlf_pct']),
            'sftlf_NE_pct':float(by_point.loc['NE','sftlf_pct']),
            'weight_SW':float(by_point.loc['SW','bilinear_weight']),
            'weight_SE':float(by_point.loc['SE','bilinear_weight']),
            'weight_NW':float(by_point.loc['NW','bilinear_weight']),
            'weight_NE':float(by_point.loc['NE','bilinear_weight']),
            'periodic_lon':bool(support['periodic_lon'].any()),
            'zstore':str(row.zstore),'version':str(row.version),
        })
    details=pd.concat(detail_rows,ignore_index=True) if detail_rows else pd.DataFrame()
    summary=pd.DataFrame(summary_rows)
    return details,summary


def land_fraction_neighborhood(ds, row: pd.Series, lat: float, lon: float, half_width: int=3) -> pd.DataFrame:
    """Extract a small native-grid sftlf neighborhood and mark bilinear support cells.

    Intended for QA of suspicious land masks (for example FGOALS-g3 near
    Madrid).  No interpolation or production data are changed.
    """
    from .cmip6_io import _target_lon_for_coord, _haversine_deg

    if 'sftlf' not in ds:
        raise KeyError("Variable 'sftlf' not present in dataset")
    da=ds['sftlf'].squeeze(drop=True)
    lat_name=_find_coord_name(da,('lat','latitude','nav_lat'))
    lon_name=_find_coord_name(da,('lon','longitude','nav_lon'))
    if not lat_name or not lon_name or da[lat_name].ndim!=1 or da[lon_name].ndim!=1:
        raise RuntimeError('land-mask neighborhood QA requires a rectilinear 1D lat/lon grid')
    work=da
    if np.any(np.diff(np.asarray(work[lat_name].values,float))<0): work=work.sortby(lat_name)
    if np.any(np.diff(np.asarray(work[lon_name].values,float))<0): work=work.sortby(lon_name)
    latv=np.asarray(work[lat_name].values,float); lonv=np.asarray(work[lon_name].values,float)
    lon0=float(_target_lon_for_coord(float(lon),lonv))
    ci=int(np.argmin(np.abs(latv-float(lat))))
    # periodic angular distance handles 0/360 correctly
    lon_dist=np.abs(((lonv-lon0+180.0)%360.0)-180.0)
    cj=int(np.argmin(lon_dist))
    iidx=range(max(0,ci-int(half_width)),min(len(latv),ci+int(half_width)+1))
    global_grid=float(lonv[-1]-lonv[0])>300.0
    if global_grid:
        jidx=[j%len(lonv) for j in range(cj-int(half_width),cj+int(half_width)+1)]
    else:
        jidx=list(range(max(0,cj-int(half_width)),min(len(lonv),cj+int(half_width)+1)))

    support=bilinear_support_table(work,float(lat),float(lon))
    support_map={(int(r.lat_index),int(r.lon_index)):str(r.support_point) for r in support.itertuples(index=False)}
    rows=[]
    for i in iidx:
        for j in jidx:
            val=np.asarray(work.isel({lat_name:int(i),lon_name:int(j)}).values).squeeze()
            pct,source_units,note=_normalize_sftlf([float(val)],str(work.attrs.get('units','')))
            native_lon=float(lonv[j])
            lon_geo=((native_lon+180.0)%360.0)-180.0
            dist=float(_haversine_deg(np.asarray([latv[i]]),np.asarray([lon_geo]),float(lat),((float(lon)+180)%360)-180)[0])
            rows.append({
                'source_id':str(row.source_id),'model':str(row.source_id),
                'member_id':str(row.member_id),'grid_label':str(row.grid_label),
                'experiment_id':str(row.experiment_id),'version':str(row.version),
                'target_lat':float(lat),'target_lon':float(lon),
                'lat_index':int(i),'lon_index':int(j),
                'grid_lat':float(latv[i]),'grid_lon_native':native_lon,'grid_lon_geographic':lon_geo,
                'sftlf_pct':float(pct[0]),'source_units':source_units,'normalization_note':note,
                'angular_distance_deg':dist,
                'is_bilinear_support':(int(i),int(j)) in support_map,
                'support_point':support_map.get((int(i),int(j)),''),
            })
    out=pd.DataFrame(rows)
    order=np.argsort(out['angular_distance_deg'].to_numpy(float),kind='stable')
    ranks=np.empty(len(out),dtype=int); ranks[order]=np.arange(1,len(out)+1)
    out['distance_rank']=ranks
    return out.sort_values(['grid_lat','grid_lon_native']).reset_index(drop=True)
