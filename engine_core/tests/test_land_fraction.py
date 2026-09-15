import numpy as np
import pandas as pd
import xarray as xr


def test_bilinear_support_table_matches_expected_weights_and_periodic_longitude():
    from src.cmip6_io import bilinear_support_table

    lat=np.array([0.0,2.0])
    lon=np.array([0.0,2.0,358.0])
    da=xr.DataArray(
        np.zeros((2,3)),
        dims=('lat','lon'),
        coords={'lat':lat,'lon':lon},
        name='sftlf',
    )
    # London-like target: -1 -> 359, halfway between 358 and periodic 360/0;
    # latitude=0.5 gives 75/25 south/north weights.
    out=bilinear_support_table(da,0.5,-1.0)
    assert len(out)==4
    np.testing.assert_allclose(out['weight'].sum(),1.0,rtol=0,atol=1e-12)
    assert out['periodic_lon'].all()
    assert set(np.round(out['grid_lon_interp'],6))=={358.0,360.0}
    expected=sorted([0.375,0.375,0.125,0.125])
    np.testing.assert_allclose(sorted(out['weight'].tolist()),expected,rtol=0,atol=1e-12)


def test_land_fraction_diagnostic_reports_four_support_cells_and_effective_fraction():
    from src.land_fraction import diagnose_land_fraction_dataset

    lat=np.array([0.0,2.0])
    lon=np.array([100.0,102.0])
    # SW=100, SE=0, NW=50, NE=0 percent land.
    vals=np.array([[100.0,0.0],[50.0,0.0]])
    ds=xr.Dataset({'sftlf':(('lat','lon'),vals)},coords={'lat':lat,'lon':lon})
    ds['sftlf'].attrs['units']='%'
    row=pd.Series(dict(
        source_id='M',experiment_id='historical',member_id='r1',grid_label='gn',
        variable_id='sftlf',zstore='gs://x',version='v1'
    ))
    support,summary=diagnose_land_fraction_dataset(ds,row,{'Test City':(1.0,101.0)})
    assert len(support)==4
    np.testing.assert_allclose(sorted(support['bilinear_weight']),[0.25]*4)
    np.testing.assert_allclose(sorted(support['sftlf_pct']),[0.0,0.0,50.0,100.0])
    assert len(summary)==1
    rec=summary.iloc[0]
    np.testing.assert_allclose(rec['effective_land_fraction_pct'],37.5)
    np.testing.assert_allclose(rec['effective_ocean_fraction_pct'],62.5)
    assert rec['land_dominant_support_cells']==2
    assert rec['ocean_dominant_support_cells']==2
    assert bool(rec['weighted_majority_ocean']) is True
    assert bool(rec['has_ocean_dominant_support']) is True
    # Summary must expose the four support-cell values directly for quick review.
    assert {rec['sftlf_SW_pct'],rec['sftlf_SE_pct'],rec['sftlf_NW_pct'],rec['sftlf_NE_pct']}=={0.0,50.0,100.0}
    np.testing.assert_allclose([rec['weight_SW'],rec['weight_SE'],rec['weight_NW'],rec['weight_NE']],[0.25]*4)


def test_land_fraction_fraction_units_are_normalized_to_percent():
    from src.land_fraction import diagnose_land_fraction_dataset

    ds=xr.Dataset(
        {'sftlf':(('lat','lon'),np.array([[1.0,0.5],[0.0,1.0]]))},
        coords={'lat':[0.0,1.0],'lon':[10.0,11.0]},
    )
    ds['sftlf'].attrs['units']='1'
    row=pd.Series(dict(
        source_id='M',experiment_id='historical',member_id='r1',grid_label='gn',
        variable_id='sftlf',zstore='gs://x',version='v1'
    ))
    support,summary=diagnose_land_fraction_dataset(ds,row,{'C':(0.5,10.5)})
    np.testing.assert_allclose(sorted(support['sftlf_pct']),[0.0,50.0,100.0,100.0])
    np.testing.assert_allclose(summary.iloc[0]['effective_land_fraction_pct'],62.5)
    assert set(support['source_units'])=={'1'}
    assert set(support['normalization_note'])=={'fraction_to_percent'}


def test_land_fraction_diagnostic_does_not_change_primary_interpolation_method():
    """The diagnostic is observational only: standard extraction stays bilinear."""
    from src.cmip6_io import extract_point_series

    time=pd.date_range('1985-01-01',periods=12,freq='MS')
    lat=np.array([0.0,1.0]); lon=np.array([10.0,11.0])
    vals=np.empty((12,2,2))
    for t in range(12):
        vals[t]=lat[:,None]+2*lon[None,:]+t
    ds=xr.Dataset({'tas':(('time','lat','lon'),vals)},coords={'time':time,'lat':lat,'lon':lon})
    out=extract_point_series(ds,'tas',0.25,10.5)
    assert out.attrs['extraction_method']=='rectilinear_linear'
