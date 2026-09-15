import numpy as np
import pandas as pd
import xarray as xr

from src.cmip6_io import (
    extract_point_series, monthly_climatology_from_series, extract_asset_for_cities,
    cache_is_valid, process_manifest_assets, cache_filename,
)


def test_rectilinear_bilinear_extracts_exact_linear_field():
    lat=np.array([0.0,1.0]); lon=np.array([10.0,11.0]); time=pd.date_range('1985-01-01',periods=24,freq='MS')
    vals=np.empty((24,2,2))
    for t in range(24): vals[t]=lat[:,None]+2*lon[None,:]+t
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':lat,'lon':lon})
    out=extract_point_series(ds,'tas',0.25,10.5)
    np.testing.assert_allclose(out.values[:2],[21.25,22.25],rtol=0,atol=1e-12)
    assert out.attrs['extraction_method']=='rectilinear_linear'


def test_monthly_climatology_rejects_wrong_units_and_missing_months():
    time=pd.date_range('1985-01-01',periods=12,freq='MS')
    bad=xr.DataArray(np.ones(12),coords={'time':time},dims=['time'],attrs={'units':'degC'})
    try:
        monthly_climatology_from_series(bad,'tas',1985,1985)
    except ValueError as e:
        assert 'units' in str(e).lower()
    else:
        raise AssertionError('wrong units must fail')

    time2=pd.date_range('1985-01-01',periods=24,freq='MS').delete(5)
    incomplete=xr.DataArray(np.ones(len(time2)),coords={'time':time2},dims=['time'],attrs={'units':'K'})
    try:
        monthly_climatology_from_series(incomplete,'tas',1985,1986)
    except RuntimeError as e:
        assert 'expected 24 monthly' in str(e).lower()
    else:
        raise AssertionError('incomplete Amon window must fail')


def test_one_open_dataset_can_extract_two_cities_and_two_future_windows():
    time=pd.date_range('2030-01-01',periods=41*12,freq='MS')
    lat=np.array([0.0,2.0]); lon=np.array([100.0,102.0])
    vals=np.empty((len(time),2,2))
    for t in range(len(time)): vals[t]=280+lat[:,None]+lon[None,:]*0.01+(t%12)
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':lat,'lon':lon})
    ds['tas'].attrs['units']='K'
    row=pd.Series(dict(source_id='ACCESS-CM2',experiment_id='ssp245',member_id='r1i1p1f1',grid_label='gn',
                       variable_id='tas',zstore='gs://x',version='v1'))
    locations={'A':(0.5,100.5),'B':(1.5,101.5)}
    out=extract_asset_for_cities(ds,row,locations)
    assert set(out.city)=={'A','B'}
    assert set(out.period)=={'2030-2050','2050-2070'}
    assert len(out)==2*2*12
    assert out.groupby(['city','period']).size().eq(12).all()


def _fake_cache_rows(row, locations):
    periods=['1985-2014'] if row.experiment_id=='historical' else ['2030-2050','2050-2070']
    labels=['1985-2014'] if row.experiment_id=='historical' else ['2040','2060']
    rows=[]
    for city,(lat,lon) in locations.items():
        for period,label in zip(periods,labels):
            for month in range(1,13):
                rows.append(dict(city=city,lat=lat,lon=lon,source_id=row.source_id,model=row.source_id,
                                 member_id=row.member_id,grid_label=row.grid_label,experiment_id=row.experiment_id,
                                 experiment=row.experiment_id,period=period,target_label=label,variable_id=row.variable_id,
                                 variable=row.variable_id,month=month,value=1.0,units='K',zstore=row.zstore,version=row.version,
                                 extraction_method='test',n_time_steps=12))
    return pd.DataFrame(rows)


def test_cache_validation_ties_cache_to_exact_asset_and_expected_cities(tmp_path):
    row=pd.Series(dict(source_id='M',experiment_id='historical',member_id='r1',grid_label='gn',variable_id='tas',
                       zstore='gs://a',version='v1'))
    p=tmp_path/cache_filename(row)
    _fake_cache_rows(row,{'A':(1,2),'B':(3,4)}).to_csv(p,index=False)
    assert cache_is_valid(p,row,['A','B'])
    changed=row.copy(); changed['version']='v2'
    assert not cache_is_valid(p,changed,['A','B'])
    assert not cache_is_valid(p,row,['A','B','C'])


def test_process_manifest_calls_runner_once_per_uncached_asset_and_resumes(tmp_path):
    manifest=pd.DataFrame([
        dict(source_id='M1',experiment_id='historical',member_id='r1',grid_label='gn',variable_id='tas',zstore='gs://1',version='v1'),
        dict(source_id='M1',experiment_id='ssp245',member_id='r1',grid_label='gn',variable_id='tas',zstore='gs://2',version='v1'),
    ])
    locations={'A':(1,2),'B':(3,4),'C':(5,6)}
    calls=[]
    def runner(row, locs):
        calls.append((row.zstore,tuple(locs)))
        return _fake_cache_rows(row,locs)
    summary=process_manifest_assets(manifest,locations,tmp_path,runner,retries=2)
    assert len(calls)==2
    assert summary['completed']==2 and summary['cached']==0
    calls.clear()
    summary2=process_manifest_assets(manifest,locations,tmp_path,runner,retries=2)
    assert calls==[]
    assert summary2['completed']==0 and summary2['cached']==2


def test_process_manifest_retries_transient_failure(tmp_path):
    manifest=pd.DataFrame([dict(source_id='M1',experiment_id='historical',member_id='r1',grid_label='gn',
                                variable_id='tas',zstore='gs://1',version='v1')])
    n={'x':0}
    def flaky(row,locs):
        n['x']+=1
        if n['x']<3: raise RuntimeError('temporary')
        return _fake_cache_rows(row,locs)
    summary=process_manifest_assets(manifest,{'A':(1,2)},tmp_path,flaky,retries=3)
    assert n['x']==3
    assert summary['completed']==1


def test_rectilinear_bilinear_wraps_periodic_longitude_across_greenwich():
    # A 0..360 rectilinear grid whose last centre is west of 360.
    # London-like longitudes must interpolate between the last column and a
    # periodic copy of the 0-degree column, not fall outside the coordinate range.
    time=pd.date_range('1985-01-01',periods=12,freq='MS')
    lat=np.array([50.0,52.0])
    lon=np.array([0.0,2.0,358.0])
    vals=np.empty((12,2,3))
    vals[:,:,0]=14.0   # 0 degrees, also the periodic 360-degree value
    vals[:,:,1]=18.0
    vals[:,:,2]=10.0   # 358 degrees
    ds=xr.Dataset({'clt':(('time','lat','lon'),vals)},coords={'time':time,'lat':lat,'lon':lon})
    ds['clt'].attrs['units']='%'

    out=extract_point_series(ds,'clt',51.0,-1.0)

    # -1 degree -> 359 degrees; midway between 358 (10) and 360/0 (14).
    np.testing.assert_allclose(out.values,12.0,rtol=0,atol=1e-12)
    assert out.attrs['extraction_method']=='rectilinear_linear_periodic_lon'


def test_extract_asset_error_reports_model_experiment_variable_and_city():
    time=pd.date_range('1985-01-01',periods=30*12,freq='MS')
    lat=np.array([50.0,52.0]); lon=np.array([0.0,2.0])
    vals=np.full((len(time),2,2),np.nan)
    ds=xr.Dataset({'clt':(('time','lat','lon'),vals)},coords={'time':time,'lat':lat,'lon':lon})
    ds['clt'].attrs['units']='%'
    row=pd.Series(dict(source_id='ACCESS-CM2',experiment_id='historical',member_id='r1i1p1f1',grid_label='gn',
                       variable_id='clt',zstore='gs://x',version='v1'))

    try:
        extract_asset_for_cities(ds,row,{'London':(51.47,-0.4543)})
    except RuntimeError as e:
        msg=str(e)
        assert 'ACCESS-CM2' in msg
        assert 'historical' in msg
        assert 'clt' in msg
        assert 'London' in msg
        assert 'NaN/Inf' in msg
    else:
        raise AssertionError('non-finite climatology must fail with asset/city context')


def test_aws_mirror_zstore_maps_google_cmip6_path_to_cmip6_pds():
    from src.cmip6_io import aws_mirror_zstore
    gs='gs://cmip6/CMIP6/ScenarioMIP/CSIRO-ARCCSS/ACCESS-CM2/ssp126/r1i1p1f1/Amon/clt/gn/v20210317/'
    assert aws_mirror_zstore(gs)==(
        's3://cmip6-pds/CMIP6/ScenarioMIP/CSIRO-ARCCSS/ACCESS-CM2/'
        'ssp126/r1i1p1f1/Amon/clt/gn/v20210317/'
    )


def test_rectilinear_bilinear_limits_interp_to_two_by_two_support(monkeypatch):
    lat=np.array([0.0,1.0,2.0,3.0])
    lon=np.array([10.0,11.0,12.0,13.0,14.0])
    time=pd.date_range('1985-01-01',periods=12,freq='MS')
    vals=np.empty((12,len(lat),len(lon)))
    for t in range(12):
        vals[t]=lat[:,None]+2*lon[None,:]+t
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':lat,'lon':lon})
    ds['tas'].attrs['units']='K'

    original=xr.DataArray.interp
    seen=[]
    def wrapped(self,*args,**kwargs):
        seen.append((self.sizes.get('lat'),self.sizes.get('lon')))
        return original(self,*args,**kwargs)
    monkeypatch.setattr(xr.DataArray,'interp',wrapped)

    out=extract_point_series(ds,'tas',1.25,12.4)
    np.testing.assert_allclose(out.values[0],1.25+2*12.4,rtol=0,atol=1e-12)
    assert seen
    assert all(a<=2 and b<=2 for a,b in seen)


def test_extract_asset_progress_reports_city_boundaries():
    time=pd.date_range('2030-01-01',periods=41*12,freq='MS')
    lat=np.array([0.0,2.0]); lon=np.array([100.0,102.0])
    vals=np.full((len(time),2,2),280.0)
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':lat,'lon':lon})
    ds['tas'].attrs['units']='K'
    row=pd.Series(dict(source_id='ACCESS-CM2',experiment_id='ssp126',member_id='r1i1p1f1',grid_label='gn',
                       variable_id='tas',zstore='gs://x',version='v1'))
    events=[]
    extract_asset_for_cities(ds,row,{'A':(0.5,100.5),'B':(1.5,101.5)},progress=events.append)
    assert 'city A: start' in events
    assert 'city A: done' in events
    assert 'city B: start' in events
    assert 'city B: done' in events


def test_city_cache_resume_preserves_completed_cities_after_partial_asset_failure(tmp_path):
    from src.cmip6_io import process_manifest_assets_by_city, city_cache_filename

    manifest=pd.DataFrame([dict(source_id='M1',experiment_id='historical',member_id='r1',grid_label='gn',
                                variable_id='tas',zstore='gs://1',version='v1')])
    locations={'A':(1,2),'B':(3,4),'C':(5,6)}
    calls=[]

    def first_runner(row, city, location):
        calls.append(city)
        if city=='C':
            raise RuntimeError('C temporarily unavailable')
        return _fake_cache_rows(row,{city:location})

    try:
        process_manifest_assets_by_city(
            manifest,locations,tmp_path/'asset',tmp_path/'city',first_runner,retries=1
        )
    except RuntimeError as e:
        assert 'C' in str(e)
    else:
        raise AssertionError('partial asset failure must propagate')

    row=pd.Series(manifest.iloc[0])
    assert (tmp_path/'city'/city_cache_filename(row,'A')).exists()
    assert (tmp_path/'city'/city_cache_filename(row,'B')).exists()
    assert not (tmp_path/'city'/city_cache_filename(row,'C')).exists()
    assert not (tmp_path/'asset'/cache_filename(row)).exists()

    calls.clear()
    def second_runner(row, city, location):
        calls.append(city)
        return _fake_cache_rows(row,{city:location})

    summary=process_manifest_assets_by_city(
        manifest,locations,tmp_path/'asset',tmp_path/'city',second_runner,retries=1
    )
    assert calls==['C']
    assert summary['completed']==1
    assert cache_is_valid(tmp_path/'asset'/cache_filename(row),row,locations.keys())


def test_city_cache_filename_is_asset_and_city_specific():
    from src.cmip6_io import city_cache_filename
    row=pd.Series(dict(source_id='ACCESS-CM2',experiment_id='ssp126',variable_id='huss'))
    assert city_cache_filename(row,'Kuwait City')=='ACCESS-CM2__ssp126__huss__Kuwait_City.csv'


def test_extract_asset_slices_future_time_before_spatial_extraction(monkeypatch):
    import src.cmip6_io as cio
    time=pd.date_range('2015-01-01',periods=(2100-2015+1)*12,freq='MS')
    lat=np.array([0.0,2.0]); lon=np.array([100.0,102.0])
    vals=np.full((len(time),2,2),280.0)
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':lat,'lon':lon})
    ds['tas'].attrs['units']='K'
    row=pd.Series(dict(source_id='ACCESS-CM2',experiment_id='ssp126',member_id='r1i1p1f1',grid_label='gn',
                       variable_id='tas',zstore='gs://x',version='v1'))
    seen=[]
    original=cio.extract_point_series
    def wrapped(ds_arg,*args,**kwargs):
        seen.append(int(ds_arg.sizes['time']))
        return original(ds_arg,*args,**kwargs)
    monkeypatch.setattr(cio,'extract_point_series',wrapped)
    out=cio.extract_asset_for_cities(ds,row,{'A':(0.5,100.5)})
    assert len(out)==24
    assert seen==[41*12]
