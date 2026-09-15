import pandas as pd

from config import MODEL_CONFIG, REQUIRED_VARIABLES
from src.catalog import select_main_manifest, select_sftlf_manifest
from src.workflow import build_case_matrix


def make_catalog():
    rows=[]
    for model,(member,grid) in MODEL_CONFIG.items():
        for exp in ['historical','ssp126','ssp245','ssp370']:
            for var in REQUIRED_VARIABLES:
                rows.append(dict(source_id=model,experiment_id=exp,member_id=member,table_id='Amon',
                                 variable_id=var,grid_label=grid,zstore=f'gs://{model}/{exp}/{var}',version='20260101'))
        rows.append(dict(source_id=model,experiment_id='historical',member_id=member,table_id='fx',
                         variable_id='sftlf',grid_label=grid,zstore=f'gs://{model}/historical/sftlf',version='20260101'))
    return pd.DataFrame(rows)


def test_main_manifest_is_exactly_200_frozen_assets():
    out=select_main_manifest(make_catalog(), ['historical','ssp126','ssp245','ssp370'])
    assert len(out)==200
    assert out[['source_id','experiment_id','variable_id']].duplicated().sum()==0
    assert set(out['source_id'])==set(MODEL_CONFIG)
    assert set(out['variable_id'])==set(REQUIRED_VARIABLES)


def test_sftlf_manifest_has_one_asset_per_model():
    out=select_sftlf_manifest(make_catalog())
    assert len(out)==5
    assert out['source_id'].nunique()==5
    assert set(out['variable_id'])=={'sftlf'}


def test_full_case_matrix_is_8_cities_3_scenarios_2_periods_6_selectors():
    m=build_case_matrix()
    assert len(m)==288
    assert m['city'].nunique()==8
    assert set(m['scenario'])=={'ssp126','ssp245','ssp370'}
    assert set(m['target_label'].astype(str))=={'2040','2060'}
    for (city,scenario,label),sub in m.groupby(['city','scenario','target_label']):
        assert len(sub)==6
        assert (sub['selector_type']=='model').sum()==5
        assert (sub['selector_type']=='ensemble_stat').sum()==1
        assert set(sub.loc[sub.selector_type=='model','selector'])==set(MODEL_CONFIG)
        assert sub.loc[sub.selector_type=='ensemble_stat','selector'].tolist()==['mean']


def test_custom_manifest_can_select_one_model_and_one_ssp():
    out=select_main_manifest(make_catalog(), ['historical','ssp126'], models=['ACCESS-CM2'])
    assert len(out)==20
    assert set(out['source_id'])=={'ACCESS-CM2'}
    assert set(out['experiment_id'])=={'historical','ssp126'}


def test_custom_case_matrix_uses_selected_model_scenario_and_period():
    m=build_case_matrix(cities=['Tokyo'], scenarios=['ssp126'], periods=['2040'], models=['ACCESS-CM2'])
    assert len(m)==2
    assert set(m['selector'])=={'ACCESS-CM2','mean'}
    assert set(m['scenario'])=={'ssp126'}
    assert set(m['target_label'].astype(str))=={'2040'}
