from __future__ import annotations
import pandas as pd
from config import MODEL_CONFIG, REQUIRED_VARIABLES, TABLE_ID

REQUIRED_COLUMNS = {
    'source_id','experiment_id','member_id','table_id','variable_id','grid_label','zstore','version'
}

def _check_columns(catalog: pd.DataFrame) -> None:
    missing=sorted(REQUIRED_COLUMNS-set(catalog.columns))
    if missing:
        raise ValueError(f'Catalog is missing required columns: {missing}')

def select_main_manifest(catalog: pd.DataFrame, experiments, models=None) -> pd.DataFrame:
    _check_columns(catalog)
    rows=[]; problems=[]
    selected_models=list(MODEL_CONFIG) if models is None else list(models)
    unknown=[m for m in selected_models if m not in MODEL_CONFIG]
    if unknown: raise ValueError(f"Unknown model(s): {unknown}")
    for model in selected_models:
        member,grid=MODEL_CONFIG[model]
        for exp in experiments:
            for var in REQUIRED_VARIABLES:
                hit=catalog[(catalog.source_id==model)&(catalog.experiment_id==exp)&
                            (catalog.member_id==member)&(catalog.table_id==TABLE_ID)&
                            (catalog.variable_id==var)&(catalog.grid_label==grid)]
                if len(hit)!=1:
                    problems.append(f'{model}/{member}/{grid}/{exp}/{var}: expected 1, found {len(hit)}')
                else:
                    rows.append(hit.iloc[[0]])
    if problems:
        raise RuntimeError('Catalog manifest is not one-to-one:\n  - '+'\n  - '.join(problems))
    out=pd.concat(rows,ignore_index=True)
    return out.sort_values(['source_id','experiment_id','variable_id']).reset_index(drop=True)

def select_sftlf_manifest(catalog: pd.DataFrame, models=None) -> pd.DataFrame:
    _check_columns(catalog)
    rows=[]; problems=[]
    priority={'historical':0,'ssp126':1,'ssp245':2,'ssp370':3,'piControl':4}
    selected_models=list(MODEL_CONFIG) if models is None else list(models)
    unknown=[m for m in selected_models if m not in MODEL_CONFIG]
    if unknown: raise ValueError(f'Unknown model(s): {unknown}')
    for model in selected_models:
        member,grid=MODEL_CONFIG[model]
        hit=catalog[(catalog.source_id==model)&(catalog.member_id==member)&
                    (catalog.grid_label==grid)&(catalog.table_id=='fx')&
                    (catalog.variable_id=='sftlf')].copy()
        if hit.empty:
            problems.append(f'{model}: no sftlf asset')
            continue
        hit['_p']=hit.experiment_id.map(priority).fillna(99)
        hit['_version']=hit.version.astype(str)
        hit=hit.sort_values(['_p','_version'],ascending=[True,False])
        rows.append(hit.iloc[[0]].drop(columns=['_p','_version']))
    if problems:
        raise RuntimeError('sftlf selection failed:\n  - '+'\n  - '.join(problems))
    return pd.concat(rows,ignore_index=True).sort_values('source_id').reset_index(drop=True)

def audit_manifest(main: pd.DataFrame, experiments, models=None) -> dict:
    selected_models=list(MODEL_CONFIG) if models is None else list(models)
    expected=len(selected_models)*len(tuple(experiments))*len(REQUIRED_VARIABLES)
    dup=int(main.duplicated(['source_id','experiment_id','variable_id']).sum())
    return {'expected_assets':expected,'actual_assets':int(len(main)),'duplicate_keys':dup,
            'passed':bool(len(main)==expected and dup==0)}
