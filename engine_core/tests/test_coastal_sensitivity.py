import numpy as np
import pandas as pd
import xarray as xr


def _row(model='M', experiment='historical', variable='tas'):
    return pd.Series(dict(
        source_id=model, experiment_id=experiment, member_id='r1', grid_label='gn',
        variable_id=variable, zstore='gs://x', version='v1'
    ))


def _support_df(model='M', city='Singapore'):
    # Grid 0..1 x 10..11, target at the center. East cells are ocean.
    return pd.DataFrame({
        'model':[model]*4,
        'city':[city]*4,
        'support_point':['SW','SE','NW','NE'],
        'grid_lat':[0.0,0.0,1.0,1.0],
        'grid_lon_native':[10.0,11.0,10.0,11.0],
        'grid_lon_interp':[10.0,11.0,10.0,11.0],
        'bilinear_weight':[0.25]*4,
        'sftlf_pct':[100.0,0.0,100.0,0.0],
    })


def test_land_aware_weights_zero_out_ocean_and_renormalize():
    from src.coastal_sensitivity import land_aware_support_table

    time=pd.date_range('1985-01-01',periods=12,freq='MS')
    da=xr.DataArray(
        np.zeros((12,2,2)),dims=('time','lat','lon'),
        coords={'time':time,'lat':[0.0,1.0],'lon':[10.0,11.0]},name='tas'
    )
    out=land_aware_support_table(da,0.5,10.5,_support_df())
    np.testing.assert_allclose(out['standard_weight'],[0.25]*4)
    got=dict(zip(out.support_point,out.land_aware_weight))
    np.testing.assert_allclose([got['SW'],got['NW']],[0.5,0.5])
    np.testing.assert_allclose([got['SE'],got['NE']],[0.0,0.0])
    np.testing.assert_allclose(out['land_aware_weight'].sum(),1.0)


def test_standard_and_land_aware_series_use_same_four_cells_but_different_weights():
    from src.coastal_sensitivity import extract_standard_and_land_aware_series

    time=pd.date_range('1985-01-01',periods=12,freq='MS')
    vals=np.empty((12,2,2),float)
    vals[:,:,0]=10.0  # west = land
    vals[:,:,1]=30.0  # east = ocean
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':[0.0,1.0],'lon':[10.0,11.0]})
    ds['tas'].attrs['units']='K'
    std,land,support=extract_standard_and_land_aware_series(ds,'tas',0.5,10.5,_support_df())
    np.testing.assert_allclose(std.values,20.0)
    np.testing.assert_allclose(land.values,10.0)
    assert std.attrs['extraction_method']=='rectilinear_linear_manual_support'
    assert land.attrs['extraction_method']=='rectilinear_land_fraction_weighted'
    assert set(support.support_point)=={'SW','SE','NW','NE'}


def test_land_aware_support_rejects_grid_mismatch():
    from src.coastal_sensitivity import land_aware_support_table

    da=xr.DataArray(np.zeros((2,2)),dims=('lat','lon'),coords={'lat':[0.0,1.0],'lon':[10.0,11.0]})
    bad=_support_df().copy()
    bad.loc[bad.support_point=='SE','grid_lon_native']=12.0
    try:
        land_aware_support_table(da,0.5,10.5,bad)
    except RuntimeError as e:
        assert 'grid mismatch' in str(e).lower()
    else:
        raise AssertionError('support-grid mismatch must fail')


def test_sensitivity_summary_compares_method_effect_to_gcm_spread():
    from src.coastal_sensitivity import summarize_sensitivity

    rows=[]
    for model,std,land in [('A',2.0,2.4),('B',3.0,3.2),('C',4.0,4.4)]:
        rows.append(dict(
            city='Singapore',model=model,scenario='ssp370',target_label='2060',month=7,
            variable='tas',signal_kind='delta',standard_signal=std,land_aware_signal=land,
            method_difference=land-std,absolute_method_difference=abs(land-std),
        ))
    out=summarize_sensitivity(pd.DataFrame(rows))
    assert len(out)==1
    rec=out.iloc[0]
    np.testing.assert_allclose(rec['standard_gcm_mean'],3.0)
    np.testing.assert_allclose(rec['standard_gcm_std'],1.0)
    np.testing.assert_allclose(rec['mean_method_difference'],(0.4+0.2+0.4)/3)
    np.testing.assert_allclose(rec['mean_abs_method_difference'],(0.4+0.2+0.4)/3)
    np.testing.assert_allclose(rec['method_to_gcm_spread_ratio'],((0.4+0.2+0.4)/3)/1.0)
    assert bool(rec['temperature_0p2C_review_trigger']) is True


def test_fgoals_madrid_neighborhood_marks_bilinear_support_cells():
    from src.land_fraction import land_fraction_neighborhood

    lat=np.arange(0.0,5.0)
    lon=np.arange(350.0,355.0)
    vals=np.arange(25,dtype=float).reshape(5,5)
    ds=xr.Dataset({'sftlf':(('lat','lon'),vals)},coords={'lat':lat,'lon':lon})
    ds['sftlf'].attrs['units']='%'
    out=land_fraction_neighborhood(ds,_row(model='FGOALS-g3',variable='sftlf'),2.2,-7.2,half_width=1)
    assert len(out)==9
    assert out['is_bilinear_support'].sum()==4
    assert set(out.loc[out.is_bilinear_support,'support_point'])=={'SW','SE','NW','NE'}
    assert out['distance_rank'].min()==1


def test_build_per_model_sensitivity_preserves_raw_delta_and_pipeline_factor():
    from src.coastal_sensitivity import build_per_model_sensitivity

    rows=[]
    for model in ['A','B']:
        for month in [1,2]:
            # temperature: land-aware future warms more than standard
            rows.append(dict(city='Singapore',model=model,experiment='historical',period='1985-2014',target_label='1985-2014',variable='tas',month=month,standard_value=300.0,land_aware_value=301.0,units='K'))
            rows.append(dict(city='Singapore',model=model,experiment='ssp370',period='2050-2070',target_label='2060',variable='tas',month=month,standard_value=303.0,land_aware_value=304.5,units='K'))
            # huss: pipeline uses ratio, but raw delta is also retained
            rows.append(dict(city='Singapore',model=model,experiment='historical',period='1985-2014',target_label='1985-2014',variable='huss',month=month,standard_value=0.010,land_aware_value=0.012,units='1'))
            rows.append(dict(city='Singapore',model=model,experiment='ssp370',period='2050-2070',target_label='2060',variable='huss',month=month,standard_value=0.011,land_aware_value=0.0144,units='1'))
    out=build_per_model_sensitivity(pd.DataFrame(rows),scenarios=['ssp370'])
    t=out[(out.model=='A')&(out.variable=='tas')&(out.month==1)].iloc[0]
    np.testing.assert_allclose(t.standard_signal,3.0)
    np.testing.assert_allclose(t.land_aware_signal,3.5)
    np.testing.assert_allclose(t.delta_change_method_difference,0.5)
    h=out[(out.model=='A')&(out.variable=='huss')&(out.month==1)].iloc[0]
    np.testing.assert_allclose(h.standard_signal,1.1)
    np.testing.assert_allclose(h.land_aware_signal,1.2)
    np.testing.assert_allclose(h.delta_change_standard,0.001)
    np.testing.assert_allclose(h.delta_change_land_aware,0.0024)
    np.testing.assert_allclose(h.method_difference_percent_points,10.0)


def test_decision_table_aggregates_monthly_review_triggers():
    from src.coastal_sensitivity import decision_table_from_monthly_summary

    monthly=pd.DataFrame([
        dict(city='Singapore',scenario='ssp370',target_label='2060',month=1,variable='tas',signal_kind='delta',
             mean_abs_method_difference=0.10,max_abs_method_difference=0.15,method_to_gcm_spread_ratio=0.2,temperature_0p2C_review_trigger=False),
        dict(city='Singapore',scenario='ssp370',target_label='2060',month=7,variable='tas',signal_kind='delta',
             mean_abs_method_difference=0.25,max_abs_method_difference=0.35,method_to_gcm_spread_ratio=0.8,temperature_0p2C_review_trigger=True),
    ])
    out=decision_table_from_monthly_summary(monthly)
    assert len(out)==1
    rec=out.iloc[0]
    np.testing.assert_allclose(rec.max_mean_abs_method_difference,0.25)
    np.testing.assert_allclose(rec.max_method_to_gcm_spread_ratio,0.8)
    assert rec.temperature_review_trigger_months==1
    assert bool(rec.weather_level_review_required) is True


def test_paired_climatology_for_asset_city_produces_two_future_windows():
    from src.coastal_sensitivity import paired_climatology_for_asset_city

    time=pd.date_range('2030-01-01',periods=41*12,freq='MS')
    vals=np.empty((len(time),2,2),float)
    for t in range(len(time)):
        vals[t,:,0]=280+(t%12)   # land/west
        vals[t,:,1]=300+(t%12)   # ocean/east
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':[0.0,1.0],'lon':[10.0,11.0]})
    ds['tas'].attrs['units']='K'
    row=_row(model='M',experiment='ssp370',variable='tas')
    out=paired_climatology_for_asset_city(ds,row,'Singapore',(0.5,10.5),_support_df())
    assert len(out)==24
    assert set(out.period)=={'2030-2050','2050-2070'}
    assert set(out.month)==set(range(1,13))
    jan=out[(out.period=='2030-2050')&(out.month==1)].iloc[0]
    np.testing.assert_allclose(jan.standard_value,290.0)
    np.testing.assert_allclose(jan.land_aware_value,280.0)
    assert jan.units=='K'


def test_manual_standard_matches_production_bilinear_on_same_support_cells():
    from src.coastal_sensitivity import extract_standard_and_land_aware_series
    from src.cmip6_io import extract_point_series

    time=pd.date_range('1985-01-01',periods=12,freq='MS')
    vals=np.arange(12*2*2,dtype=float).reshape(12,2,2)
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':[0.0,1.0],'lon':[10.0,11.0]})
    ds['tas'].attrs['units']='K'
    standard,_,_=extract_standard_and_land_aware_series(ds,'tas',0.25,10.6,_support_df().assign(
        bilinear_weight=[0.3,0.45,0.1,0.15]
    ))
    production=extract_point_series(ds,'tas',0.25,10.6)
    np.testing.assert_allclose(standard.values,production.values,rtol=0,atol=1e-12)


def test_per_model_sensitivity_reports_relative_method_difference_when_defined():
    from src.coastal_sensitivity import build_per_model_sensitivity
    rows=[]
    for month in [1]:
        rows += [
            dict(city='Singapore',model='A',experiment='historical',period='1985-2014',target_label='1985-2014',variable='tas',month=month,standard_value=300.0,land_aware_value=301.0,units='K'),
            dict(city='Singapore',model='A',experiment='ssp370',period='2050-2070',target_label='2060',variable='tas',month=month,standard_value=303.0,land_aware_value=304.5,units='K'),
        ]
    out=build_per_model_sensitivity(pd.DataFrame(rows),scenarios=['ssp370'])
    rec=out.iloc[0]
    np.testing.assert_allclose(rec.relative_method_difference_pct,(3.5-3.0)/3.0*100.0)
