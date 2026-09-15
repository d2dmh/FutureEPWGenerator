from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path
from typing import Mapping, Callable

import numpy as np
import pandas as pd

EXPECTED_UNITS = {
    'tas': ('K',), 'tasmax': ('K',), 'tasmin': ('K',),
    'huss': ('1','kg kg-1','kg/kg','kg kg**-1'),
    'psl': ('Pa',),
    'sfcWind': ('m s-1','m s**-1','m/s'),
    'clt': ('%','percent'),
    'rsds': ('W m-2','W m**-2','W/m2'),
    'rlds': ('W m-2','W m**-2','W/m2'),
    'pr': ('kg m-2 s-1','kg m**-2 s**-1','kg/m2/s'),
}


def _find_coord_name(obj, candidates):
    for c in candidates:
        if c in obj.coords or c in obj.dims:
            return c
    return None


def _target_lon_for_coord(target_lon: float, lon_values: np.ndarray) -> float:
    finite=np.asarray(lon_values,dtype=float)
    finite=finite[np.isfinite(finite)]
    if finite.size==0:
        return target_lon
    if finite.min()>=0 and finite.max()>180:
        return target_lon % 360.0
    return ((target_lon+180.0)%360.0)-180.0


def _haversine_deg(lat_grid, lon_grid, lat0: float, lon0: float):
    lat1=np.radians(lat_grid); lon1=np.radians(lon_grid)
    lat2=math.radians(lat0); lon2=math.radians(lon0)
    dlat=lat1-lat2; dlon=(lon1-lon2+np.pi)%(2*np.pi)-np.pi
    a=np.sin(dlat/2)**2+np.cos(lat1)*math.cos(lat2)*np.sin(dlon/2)**2
    return 2*np.arctan2(np.sqrt(a),np.sqrt(np.maximum(1-a,0)))


def _bracket_indices(values: np.ndarray, target: float) -> tuple[int,int]:
    values=np.asarray(values,dtype=float)
    if values.ndim!=1 or values.size<2:
        raise RuntimeError('linear interpolation requires at least two 1D coordinate values')
    # Keep v1.1/xarray behavior for non-periodic out-of-range targets: use
    # the boundary support pair and let xarray.interp return NaN rather than
    # silently extrapolating.  Downstream validation will reject that NaN.
    if target<values[0]:
        return 0,1
    if target>values[-1]:
        return values.size-2,values.size-1
    j=int(np.searchsorted(values,target,side='left'))
    if j<=0:
        return 0,1
    if j>=values.size:
        return values.size-2,values.size-1
    if values[j]==target:
        if j==values.size-1:
            return j-1,j
        return j,j+1
    return j-1,j


def _longitude_support(values: np.ndarray, target: float):
    """Return two longitude indices/coordinates that bracket *target*.

    For global rectilinear grids this explicitly wraps the Greenwich seam,
    e.g. 359.55 degrees is bracketed by 358.125 and 360/0 degrees.  The
    returned coordinate values may therefore differ from the stored values by
    +/-360, while the returned indices still point at the original Zarr data.
    """
    values=np.asarray(values,dtype=float)
    if values.ndim!=1 or values.size<2:
        raise RuntimeError('linear interpolation requires at least two 1D longitude values')
    global_grid=float(values[-1]-values[0])>300.0
    if not global_grid:
        i0,i1=_bracket_indices(values,target)
        return (i0,i1),(float(values[i0]),float(values[i1])),False
    if target<values[0]:
        return (values.size-1,0),(float(values[-1]-360.0),float(values[0])),True
    if target>values[-1]:
        return (values.size-1,0),(float(values[-1]),float(values[0]+360.0)),True
    i0,i1=_bracket_indices(values,target)
    return (i0,i1),(float(values[i0]),float(values[i1])),False



def bilinear_support_table(da, lat: float, lon: float) -> pd.DataFrame:
    """Return the exact four rectilinear support cells and bilinear weights.

    The coordinate handling intentionally mirrors :func:`extract_point_series`,
    including coordinate sorting and periodic longitude support across the
    Greenwich seam.  This helper is diagnostic only; it does not change the
    production interpolation method.
    """
    lat_name=_find_coord_name(da,('lat','latitude','nav_lat'))
    lon_name=_find_coord_name(da,('lon','longitude','nav_lon'))
    if not lat_name or not lon_name:
        raise RuntimeError('Cannot identify latitude/longitude coordinates')
    if da[lat_name].ndim!=1 or da[lon_name].ndim!=1:
        raise RuntimeError('Bilinear support diagnostics require 1D rectilinear latitude/longitude coordinates')

    work=da
    if np.any(np.diff(np.asarray(work[lat_name].values,float))<0):
        work=work.sortby(lat_name)
    if np.any(np.diff(np.asarray(work[lon_name].values,float))<0):
        work=work.sortby(lon_name)

    lat_values=np.asarray(work[lat_name].values,dtype=float)
    lon_values=np.asarray(work[lon_name].values,dtype=float)
    lon0=float(_target_lon_for_coord(float(lon),lon_values))
    i0,i1=_bracket_indices(lat_values,float(lat))
    (j0,j1),(lonv0,lonv1),periodic_lon=_longitude_support(lon_values,lon0)

    lat0=float(lat_values[i0]); lat1=float(lat_values[i1])
    if lat1==lat0 or lonv1==lonv0:
        raise RuntimeError('Degenerate coordinate pair prevents bilinear-weight calculation')
    wy0=(lat1-float(lat))/(lat1-lat0)
    wy1=(float(lat)-lat0)/(lat1-lat0)
    wx0=(lonv1-lon0)/(lonv1-lonv0)
    wx1=(lon0-lonv0)/(lonv1-lonv0)

    rows=[]
    for label,ii,jj,grid_lon_interp,w in (
        ('SW',i0,j0,lonv0,wy0*wx0),
        ('SE',i0,j1,lonv1,wy0*wx1),
        ('NW',i1,j0,lonv0,wy1*wx0),
        ('NE',i1,j1,lonv1,wy1*wx1),
    ):
        rows.append({
            'support_point':label,
            'lat_index':int(ii),'lon_index':int(jj),
            'grid_lat':float(lat_values[ii]),
            'grid_lon_native':float(lon_values[jj]),
            'grid_lon_interp':float(grid_lon_interp),
            'weight':float(w),
            'periodic_lon':bool(periodic_lon),
            'target_lat':float(lat),'target_lon':float(lon),
            'target_lon_grid':float(lon0),
            'lat_name':lat_name,'lon_name':lon_name,
        })
    out=pd.DataFrame(rows)
    if np.any(~np.isfinite(out['weight'])):
        raise RuntimeError('Non-finite bilinear support weight')
    if not np.isclose(float(out['weight'].sum()),1.0,rtol=0,atol=1e-10):
        raise RuntimeError(f'Bilinear support weights do not sum to 1: {out["weight"].sum()}')
    return out


def extract_point_series(ds, variable: str, lat: float, lon: float, spatial: str='bilinear'):
    if variable not in ds:
        raise KeyError(f'Variable {variable!r} not present in dataset')
    da=ds[variable]
    lat_name=_find_coord_name(da,('lat','latitude','nav_lat'))
    lon_name=_find_coord_name(da,('lon','longitude','nav_lon'))
    if not lat_name or not lon_name:
        raise RuntimeError(f'Cannot identify latitude/longitude coordinates for {variable}')
    lat_coord=da[lat_name]; lon_coord=da[lon_name]
    lon0=_target_lon_for_coord(lon,lon_coord.values)
    if lat_coord.ndim==1 and lon_coord.ndim==1:
        work=da
        if np.any(np.diff(np.asarray(work[lat_name].values,float))<0):
            work=work.sortby(lat_name)
        if np.any(np.diff(np.asarray(work[lon_name].values,float))<0):
            work=work.sortby(lon_name)
        method='linear' if spatial=='bilinear' else 'nearest'
        if method=='nearest':
            out=work.interp({lat_name:lat,lon_name:lon0},method='nearest')
            periodic_lon=False
        else:
            lat_values=np.asarray(work[lat_name].values,dtype=float)
            lon_values=np.asarray(work[lon_name].values,dtype=float)
            i0,i1=_bracket_indices(lat_values,float(lat))
            (j0,j1),(lonv0,lonv1),periodic_lon=_longitude_support(lon_values,float(lon0))
            # Only expose the four support grid cells to xarray.interp.  This
            # preserves the same linear interpolation mathematics as v1.1 but
            # prevents remote backends from considering the whole global field.
            support=work.isel({lat_name:[i0,i1],lon_name:[j0,j1]})
            support=support.assign_coords({lon_name:[lonv0,lonv1]})
            out=support.interp({lat_name:float(lat),lon_name:float(lon0)},method='linear')
        suffix='_periodic_lon' if periodic_lon else ''
        out.attrs['extraction_method']=f'rectilinear_{method}{suffix}'
        out.attrs['target_lat']=float(lat); out.attrs['target_lon']=float(lon)
        return out
    latv=np.asarray(lat_coord.values,dtype=float)
    lonv=np.asarray(lon_coord.values,dtype=float)
    lonv=np.where(lonv>180,lonv-360,lonv)
    lon_for_dist=((lon+180)%360)-180
    dist=_haversine_deg(latv,lonv,lat,lon_for_dist)
    idx=np.unravel_index(int(np.nanargmin(dist)),dist.shape)
    indexers={dim:int(i) for dim,i in zip(lat_coord.dims,idx)}
    out=da.isel(indexers)
    out.attrs['extraction_method']='curvilinear_nearest'
    out.attrs['target_lat']=float(lat); out.attrs['target_lon']=float(lon)
    out.attrs['selected_lat']=float(latv[idx]); out.attrs['selected_lon']=float(lonv[idx])
    return out


def aws_mirror_zstore(zstore: str) -> str:
    """Map the documented GCS CMIP6 Zarr prefix to the AWS cmip6-pds mirror."""
    prefix='gs://cmip6/'
    if not str(zstore).startswith(prefix):
        raise ValueError(f'Cannot derive AWS CMIP6 mirror from {zstore!r}')
    return 's3://cmip6-pds/'+str(zstore)[len(prefix):]


def _open_zarr_with_mapper(mapper):
    import xarray as xr
    try:
        coder=xr.coders.CFDatetimeCoder(use_cftime=True)
        return xr.open_zarr(mapper,consolidated=True,decode_times=coder)
    except Exception:
        # Compatibility with older xarray releases.
        return xr.open_zarr(mapper,consolidated=True,decode_times=True,use_cftime=True)


def open_public_cmip6_zarr(zstore: str, provider: str='gcs'):
    provider=str(provider).lower()
    if provider=='gcs':
        import gcsfs
        fs=gcsfs.GCSFileSystem(token='anon')
        return _open_zarr_with_mapper(fs.get_mapper(zstore))
    if provider=='aws':
        import s3fs
        fs=s3fs.S3FileSystem(anon=True,client_kwargs={'region_name':'us-west-2'})
        return _open_zarr_with_mapper(fs.get_mapper(aws_mirror_zstore(zstore)))
    raise ValueError(f'Unsupported provider {provider!r}; expected gcs or aws')


def open_public_pangeo_zarr(zstore: str):
    """Backward-compatible GCS opener retained for external callers."""
    return open_public_cmip6_zarr(zstore,provider='gcs')


def _normalize_units(values: np.ndarray, variable: str, units: str):
    arr=np.asarray(values,dtype=float); u=(units or '').strip(); note=None
    if variable=='psl' and u.lower() in {'hpa','mbar','mb'}:
        arr=arr*100.0; note=f'converted psl from {u} to Pa'; u='Pa'
    elif variable=='clt' and u in {'1','fraction',''} and np.nanmax(np.abs(arr))<=1.5:
        arr=arr*100.0; note=f'converted clt from fraction ({u or "unitless"}) to %'; u='%'
    return arr,u,note


def monthly_climatology_from_series(series, variable: str, start_year: int, end_year: int):
    if 'time' not in series.coords:
        raise RuntimeError(f'{variable}: no time coordinate')
    years=series['time'].dt.year
    sel=series.where((years>=start_year)&(years<=end_year),drop=True)
    n_steps=int(sel.sizes.get('time',0))
    expected=(end_year-start_year+1)*12
    if n_steps!=expected:
        raise RuntimeError(f'{variable}: expected {expected} monthly Amon time steps in {start_year}-{end_year}, found {n_steps}')
    clim=sel.groupby('time.month').mean('time',skipna=True)
    months=np.asarray(clim['month'].values,dtype=int)
    if not np.array_equal(months,np.arange(1,13)):
        raise RuntimeError(f'{variable}: expected all 12 climatological months; got {months.tolist()}')
    vals,units,note=_normalize_units(clim.values,variable,str(series.attrs.get('units','')))
    allowed=EXPECTED_UNITS.get(variable)
    if allowed is not None and units not in allowed:
        raise ValueError(f'{variable}: unexpected units {units!r}; expected one of {allowed}')
    if np.any(~np.isfinite(vals)):
        raise RuntimeError(f'{variable}: monthly climatology contains NaN/Inf')
    return vals, {
        'source_units':str(series.attrs.get('units','')),'normalized_units':units,'unit_note':note,
        'n_time_steps':n_steps,'start_year':int(start_year),'end_year':int(end_year),
        'extraction_method':series.attrs.get('extraction_method','unknown')
    }


def _windows_for_experiment(experiment: str):
    if experiment=='historical':
        return [(1985,2014,'1985-2014')]
    if experiment in {'ssp126','ssp245','ssp370'}:
        return [(2030,2050,'2040'),(2050,2070,'2060')]
    raise ValueError(f'Unsupported experiment {experiment!r}')


def _subset_dataset_for_experiment(ds, variable: str, experiment: str):
    """Lazily restrict the remote dataset to the years needed by one experiment.

    Historical uses 1985-2014. Scenario assets only need 2030-2070 because
    the two 21-year target windows are 2030-2050 and 2050-2070. The slice
    is applied before any spatial data access, reducing remote chunk reads.
    """
    if 'time' not in ds.coords:
        raise RuntimeError(f'{variable}: no time coordinate')
    windows=_windows_for_experiment(experiment)
    start=min(w[0] for w in windows); end=max(w[1] for w in windows)
    years=np.asarray(ds['time'].dt.year.values,dtype=int)
    idx=np.flatnonzero((years>=start)&(years<=end))
    expected=(end-start+1)*12
    if idx.size!=expected:
        raise RuntimeError(
            f'{variable}: expected {expected} Amon time steps in extraction window '
            f'{start}-{end}, found {idx.size}'
        )
    return ds[[variable]].isel(time=idx)


def extract_asset_for_cities(ds, row: pd.Series, locations: Mapping[str, tuple[float,float]], spatial: str='bilinear', progress: Callable[[str],None]|None=None) -> pd.DataFrame:
    variable=str(row.variable_id); experiment=str(row.experiment_id)
    work_ds=_subset_dataset_for_experiment(ds,variable,experiment)
    records=[]
    for city,(lat,lon) in locations.items():
        if progress: progress(f'city {city}: start')
        try:
            point=extract_point_series(work_ds,variable,float(lat),float(lon),spatial=spatial)
            for start,end,label in _windows_for_experiment(experiment):
                clim,meta=monthly_climatology_from_series(point,variable,start,end)
                period=f'{start}-{end}'
                for month,value in enumerate(clim,start=1):
                    records.append({
                        'city':city,'lat':float(lat),'lon':float(lon),
                        'source_id':str(row.source_id),'model':str(row.source_id),
                        'member_id':str(row.member_id),'grid_label':str(row.grid_label),
                        'experiment_id':experiment,'experiment':experiment,'period':period,'target_label':label,
                        'variable_id':variable,'variable':variable,'month':month,'value':float(value),
                        'units':meta['normalized_units'],'zstore':str(row.zstore),'version':str(row.version),
                        'extraction_method':meta['extraction_method'],'n_time_steps':meta['n_time_steps'],
                    })
            if progress: progress(f'city {city}: done')
        except Exception as e:
            raise RuntimeError(
                f'{row.source_id} / {experiment} / {variable} / {city}: {e}'
            ) from e
    return pd.DataFrame(records)


def cache_filename(row: pd.Series) -> str:
    def clean(x): return str(x).replace('/','_').replace('\\','_').replace(' ','_')
    return f"{clean(row.source_id)}__{clean(row.experiment_id)}__{clean(row.variable_id)}.csv"


def _expected_periods(experiment: str):
    return [f'{a}-{b}' for a,b,_ in _windows_for_experiment(experiment)]


def cache_is_valid(path: Path|str, row: pd.Series, expected_cities) -> bool:
    path=Path(path)
    if not path.exists(): return False
    try: df=pd.read_csv(path,dtype={'version':str})
    except Exception: return False
    required={'city','source_id','experiment_id','member_id','grid_label','variable_id','zstore','version','period','month'}
    if not required.issubset(df.columns): return False
    checks={
        'source_id':str(row.source_id),'experiment_id':str(row.experiment_id),'member_id':str(row.member_id),
        'grid_label':str(row.grid_label),'variable_id':str(row.variable_id),'zstore':str(row.zstore),'version':str(row.version)
    }
    for col,val in checks.items():
        if set(df[col].astype(str))!={val}: return False
    if set(df.city.astype(str))!=set(map(str,expected_cities)): return False
    if set(df.period.astype(str))!=set(_expected_periods(str(row.experiment_id))): return False
    sizes=df.groupby(['city','period']).size()
    if sizes.empty or not sizes.eq(12).all(): return False
    if any(sorted(g.month.astype(int).tolist())!=list(range(1,13)) for _,g in df.groupby(['city','period'])): return False
    return True


def _atomic_write_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.stem+'.',suffix='.tmp',dir=path.parent)
    os.close(fd)
    try:
        df.to_csv(tmp,index=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def process_manifest_assets(
    manifest: pd.DataFrame,
    locations: Mapping[str, tuple[float,float]],
    cache_dir: Path|str,
    asset_runner: Callable[[pd.Series, Mapping[str, tuple[float,float]]], pd.DataFrame],
    retries: int=3,
    progress: Callable[[str],None]|None=None,
    should_stop: Callable[[], bool]|None=None,
):
    cache_dir=Path(cache_dir); cache_dir.mkdir(parents=True,exist_ok=True)
    completed=0; cached=0; failed=0; errors=[]; total=len(manifest)
    for i,row in enumerate(manifest.itertuples(index=False),start=1):
        # itertuples is faster, convert to Series for stable API.
        s=pd.Series(row._asdict())
        path=cache_dir/cache_filename(s)
        if cache_is_valid(path,s,locations.keys()):
            cached+=1
            if progress: progress(f'[{i}/{total}] cached  {s.source_id} {s.experiment_id} {s.variable_id}')
            continue
        last=None
        for attempt in range(1,retries+1):
            try:
                if progress: progress(f'[{i}/{total}] extract {s.source_id} {s.experiment_id} {s.variable_id} attempt {attempt}/{retries}')
                df=asset_runner(s,locations)
                _atomic_write_csv(df,path)
                if not cache_is_valid(path,s,locations.keys()):
                    raise RuntimeError(f'runner produced invalid cache for {path.name}')
                completed+=1; last=None; break
            except Exception as e:
                last=e
        if last is not None:
            failed+=1; errors.append({'asset':path.name,'error':repr(last)})
            raise RuntimeError(f'Failed asset after {retries} attempts: {path.name}: {last}') from last
    return {'total':total,'completed':completed,'cached':cached,'failed':failed,'errors':errors}



def city_cache_filename(row: pd.Series, city: str) -> str:
    def clean(x): return str(x).replace('/','_').replace('\\','_').replace(' ','_')
    return (
        f"{clean(row.source_id)}__{clean(row.experiment_id)}__"
        f"{clean(row.variable_id)}__{clean(city)}.csv"
    )


def city_cache_is_valid(path: Path|str, row: pd.Series, city: str) -> bool:
    return cache_is_valid(path,row,[city])


def merge_city_caches(row: pd.Series, locations: Mapping[str, tuple[float,float]], city_cache_dir: Path|str) -> pd.DataFrame:
    frames=[]; city_cache_dir=Path(city_cache_dir)
    for city in locations:
        path=city_cache_dir/city_cache_filename(row,city)
        if not city_cache_is_valid(path,row,city):
            raise RuntimeError(f'Missing or invalid city cache: {path}')
        frames.append(pd.read_csv(path,dtype={'version':str}))
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()


def process_manifest_assets_by_city(
    manifest: pd.DataFrame,
    locations: Mapping[str, tuple[float,float]],
    cache_dir: Path|str,
    city_cache_dir: Path|str,
    city_runner: Callable[[pd.Series, str, tuple[float,float]], pd.DataFrame],
    retries: int=3,
    progress: Callable[[str],None]|None=None,
    should_stop: Callable[[], bool]|None=None,
):
    """Resumable asset extraction with city-level checkpoints.

    A completed legacy/full asset cache is reused immediately. Otherwise each
    city is processed and atomically cached independently. If a later city
    fails, earlier city caches remain valid and are skipped on the next run.
    Once every city cache is valid, they are merged into the unchanged v1.x
    asset-cache schema consumed by Stages 03-05.
    """
    cache_dir=Path(cache_dir); city_cache_dir=Path(city_cache_dir)
    cache_dir.mkdir(parents=True,exist_ok=True); city_cache_dir.mkdir(parents=True,exist_ok=True)
    completed=0; cached=0; city_completed=0; city_cached=0; total=len(manifest)
    errors=[]; stopped=False
    for i,row in enumerate(manifest.itertuples(index=False),start=1):
        if should_stop is not None and should_stop():
            stopped=True
            if progress: progress('pause requested; stopping before next asset')
            break
        s=pd.Series(row._asdict())
        asset_path=cache_dir/cache_filename(s)
        if cache_is_valid(asset_path,s,locations.keys()):
            cached+=1
            if progress: progress(f'[{i}/{total}] cached  {s.source_id} {s.experiment_id} {s.variable_id}')
            continue

        for city,location in locations.items():
            if should_stop is not None and should_stop():
                stopped=True
                if progress: progress(f'    pause requested; preserving completed city caches before {city}')
                break
            cpath=city_cache_dir/city_cache_filename(s,city)
            if city_cache_is_valid(cpath,s,city):
                city_cached+=1
                if progress: progress(f'    city {city}: cached')
                continue
            last=None
            for attempt in range(1,retries+1):
                try:
                    if progress:
                        progress(
                            f'[{i}/{total}] extract {s.source_id} {s.experiment_id} '
                            f'{s.variable_id} | city {city} | attempt {attempt}/{retries}'
                        )
                    df=city_runner(s,city,location)
                    _atomic_write_csv(df,cpath)
                    if not city_cache_is_valid(cpath,s,city):
                        raise RuntimeError(f'runner produced invalid city cache for {cpath.name}')
                    city_completed+=1; last=None; break
                except Exception as e:
                    last=e
            if last is not None:
                errors.append({'asset':asset_path.name,'city':city,'error':repr(last)})
                raise RuntimeError(
                    f'Failed city after {retries} attempts: {asset_path.name} / {city}: {last}'
                ) from last

        if stopped:
            break
        merged=merge_city_caches(s,locations,city_cache_dir)
        _atomic_write_csv(merged,asset_path)
        if not cache_is_valid(asset_path,s,locations.keys()):
            raise RuntimeError(f'assembled invalid asset cache for {asset_path.name}')
        completed+=1
        if progress: progress(f'[{i}/{total}] asset complete {s.source_id} {s.experiment_id} {s.variable_id}')
    return {
        'total':total,'completed':completed,'cached':cached,'failed':len(errors),
        'city_completed':city_completed,'city_cached':city_cached,'errors':errors,'stopped':stopped,
    }

def combine_cache(cache_dir: Path|str, manifest: pd.DataFrame, locations) -> pd.DataFrame:
    frames=[]
    for row in manifest.itertuples(index=False):
        s=pd.Series(row._asdict()); p=Path(cache_dir)/cache_filename(s)
        if not cache_is_valid(p,s,locations):
            raise RuntimeError(f'Missing or invalid cache: {p}')
        frames.append(pd.read_csv(p,dtype={'version':str}))
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()


def city_frame_from_asset_cache(path: Path|str, row: pd.Series, city: str) -> pd.DataFrame|None:
    """Return a validated single-city slice from a legacy multi-city asset cache."""
    path=Path(path)
    if not path.exists(): return None
    try: df=pd.read_csv(path,dtype={'version':str})
    except Exception: return None
    required={'city','source_id','experiment_id','member_id','grid_label','variable_id','zstore','version','period','month'}
    if not required.issubset(df.columns): return None
    checks={
        'source_id':str(row.source_id),'experiment_id':str(row.experiment_id),'member_id':str(row.member_id),
        'grid_label':str(row.grid_label),'variable_id':str(row.variable_id),'zstore':str(row.zstore),'version':str(row.version)
    }
    for col,val in checks.items():
        if set(df[col].astype(str))!={val}: return None
    sub=df[df.city.astype(str)==str(city)].copy()
    if sub.empty: return None
    if set(sub.period.astype(str))!=set(_expected_periods(str(row.experiment_id))): return None
    sizes=sub.groupby(['city','period']).size()
    if sizes.empty or not sizes.eq(12).all(): return None
    if any(sorted(g.month.astype(int).tolist())!=list(range(1,13)) for _,g in sub.groupby(['city','period'])): return None
    return sub.reset_index(drop=True)


def seed_city_cache_from_legacy(
    row: pd.Series,
    city: str,
    target_path: Path|str,
    *,
    legacy_asset_dir: Path|str|None=None,
    legacy_city_dir: Path|str|None=None,
) -> bool:
    """Seed a new location-namespaced city checkpoint from read-only legacy caches."""
    target=Path(target_path)
    if city_cache_is_valid(target,row,city): return True
    if legacy_city_dir is not None:
        source=Path(legacy_city_dir)/city_cache_filename(row,city)
        if city_cache_is_valid(source,row,city):
            _atomic_write_csv(pd.read_csv(source,dtype={'version':str}),target)
            return city_cache_is_valid(target,row,city)
    if legacy_asset_dir is not None:
        source=Path(legacy_asset_dir)/cache_filename(row)
        sub=city_frame_from_asset_cache(source,row,city)
        if sub is not None:
            _atomic_write_csv(sub,target)
            return city_cache_is_valid(target,row,city)
    return False
