import numpy as np
import pandas as pd

from config import MODEL_CONFIG, REQUIRED_VARIABLES
from src.factors import build_factors, ensemble_summary, signal_dict_from_factor_table

BASES={
    'tas':280.0,'tasmax':285.0,'tasmin':275.0,'huss':0.01,'psl':101000.0,
    'sfcWind':4.0,'clt':50.0,'rsds':200.0,'rlds':300.0,'pr':1e-5,
}


def make_climatology():
    rows=[]
    for city in ['A','B']:
        for model in MODEL_CONFIG:
            for var in REQUIRED_VARIABLES:
                for month in range(1,13):
                    rows.append(dict(city=city,model=model,source_id=model,experiment='historical',experiment_id='historical',
                                     period='1985-2014',target_label='1985-2014',variable=var,variable_id=var,month=month,value=BASES[var]))
                    for exp in ['ssp126','ssp245','ssp370']:
                        for period,label,scale in [('2030-2050','2040',1),('2050-2070','2060',2)]:
                            if var in {'huss','sfcWind','pr'}:
                                value=BASES[var]*(1+0.1*scale)
                            else:
                                value=BASES[var]+scale
                            rows.append(dict(city=city,model=model,source_id=model,experiment=exp,experiment_id=exp,
                                             period=period,target_label=label,variable=var,variable_id=var,month=month,value=value))
    return pd.DataFrame(rows)


def test_build_factors_generates_all_cities_models_scenarios_periods_months():
    out=build_factors(make_climatology())
    assert len(out)==2*5*3*2*12
    assert set(out.scenario)=={'ssp126','ssp245','ssp370'}
    assert set(out.target_label.astype(str))=={'2040','2060'}
    r=out[(out.city=='A')&(out.model=='ACCESS-CM2')&(out.scenario=='ssp245')&(out.target_label.astype(str)=='2040')].iloc[0]
    assert r.d_tas==1.0 and r.d_tasmax==1.0 and r.d_tasmin==1.0
    assert r.d_psl_pa==1.0 and r.d_clt==1.0 and r.d_rsds==1.0 and r.d_rlds==1.0
    assert np.isclose(r.r_huss,1.1) and np.isclose(r.r_wind,1.1) and np.isclose(r.r_pr,1.1)


def test_ensemble_summary_has_mean_median_std_min_max():
    per=build_factors(make_climatology())
    out=ensemble_summary(per)
    assert set(out.ensemble_stat)=={'mean','median','std','min','max'}
    mean=out[out.ensemble_stat=='mean']
    assert len(mean)==2*3*2*12


def test_signal_dict_selects_exact_12_months():
    per=build_factors(make_climatology())
    d=signal_dict_from_factor_table(per,city='A',scenario='ssp126',target_label='2040',model='ACCESS-CM2')
    assert set(d)=={'d_tas','d_tasmax','d_tasmin','r_huss','d_psl_pa','r_wind','d_clt','d_rsds','d_rlds','r_pr'}
    assert all(v.shape==(12,) for v in d.values())
    np.testing.assert_allclose(d['d_tas'],1.0)


def test_precipitation_dry_baseline_fallback_is_identity_and_audited():
    clim=make_climatology()
    mask=(clim.city=='A')&(clim.model=='ACCESS-CM2')&(clim.experiment=='historical')&(clim.variable=='pr')&(clim.month==8)
    clim.loc[mask,'value']=0.0
    out=build_factors(clim)
    rows=out[(out.city=='A')&(out.model=='ACCESS-CM2')&(out.month==8)]
    assert len(rows)==6
    assert rows.pr_dry_baseline_fallback.astype(bool).all()
    np.testing.assert_allclose(rows.r_pr.to_numpy(float),1.0)


def test_build_factors_can_run_one_model_one_scenario_one_period():
    out=build_factors(
        make_climatology(),
        models=['ACCESS-CM2'], scenarios=['ssp126'], target_labels=['2040'],
    )
    assert len(out)==2*1*1*1*12
    assert set(out.model)=={'ACCESS-CM2'}
    assert set(out.scenario)=={'ssp126'}
    assert set(out.target_label.astype(str))=={'2040'}
    ens=ensemble_summary(out)
    mean=ens[ens.ensemble_stat=='mean']
    assert len(mean)==2*1*1*12
