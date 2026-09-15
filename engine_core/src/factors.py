from __future__ import annotations
import numpy as np
import pandas as pd
from config import MODEL_CONFIG, SCENARIOS

SIGNAL_SPEC = {
    'd_tas': ('tas','delta'),
    'd_tasmax': ('tasmax','delta'),
    'd_tasmin': ('tasmin','delta'),
    'r_huss': ('huss','ratio'),
    'd_psl_pa': ('psl','delta'),
    'r_wind': ('sfcWind','ratio'),
    'd_clt': ('clt','delta'),
    'd_rsds': ('rsds','delta'),
    'd_rlds': ('rlds','delta'),
    'r_pr': ('pr','ratio'),
}
SIGNAL_FIELDS = tuple(SIGNAL_SPEC)


def _safe_ratio(future: float, historical: float, variable: str, month: int) -> float:
    if abs(historical) < 1e-12:
        raise ZeroDivisionError(f'{variable}: historical monthly mean is ~0 for month {month}')
    return future / historical


def build_factors(climatology: pd.DataFrame, models=None, scenarios=None, target_labels=None) -> pd.DataFrame:
    required={'city','model','experiment','period','variable','month','value'}
    missing=sorted(required-set(climatology.columns))
    if missing: raise ValueError(f'Climatology table missing columns: {missing}')
    selected_models=list(MODEL_CONFIG) if models is None else list(models)
    selected_scenarios=list(SCENARIOS) if scenarios is None else list(scenarios)
    selected_labels=['2040','2060'] if target_labels is None else [str(x) for x in target_labels]
    period_map={'2040':'2030-2050','2060':'2050-2070'}
    unknown_models=[m for m in selected_models if m not in MODEL_CONFIG]
    if unknown_models: raise ValueError(f'Unknown model(s): {unknown_models}')
    unknown_scenarios=[x for x in selected_scenarios if x not in SCENARIOS]
    if unknown_scenarios: raise ValueError(f'Unknown scenario(s): {unknown_scenarios}')
    unknown_labels=[x for x in selected_labels if x not in period_map]
    if unknown_labels: raise ValueError(f'Unknown target label(s): {unknown_labels}')
    rows=[]
    for city in sorted(climatology.city.astype(str).unique()):
        c=climatology[climatology.city.astype(str)==city]
        for model in selected_models:
            sub=c[c.model==model]
            if sub.empty: raise RuntimeError(f'No climatology for {city}/{model}')
            for scenario in selected_scenarios:
                for label in selected_labels:
                    period=period_map[label]
                    for month in range(1,13):
                        r={'city':city,'model':model,'scenario':scenario,'future_period':period,'target_label':label,'month':month,
                           'pr_dry_baseline_fallback':False}
                        for signal,(var,kind) in SIGNAL_SPEC.items():
                            h=sub[(sub.experiment=='historical')&(sub.period=='1985-2014')&(sub.variable==var)&(sub.month==month)]
                            f=sub[(sub.experiment==scenario)&(sub.period==period)&(sub.variable==var)&(sub.month==month)]
                            if len(h)!=1 or len(f)!=1:
                                raise RuntimeError(f'Need one historical/future value for {city}/{model}/{scenario}/{var}/month={month}; hist={len(h)} future={len(f)}')
                            hv=float(h.iloc[0].value); fv=float(f.iloc[0].value)
                            if kind=='delta':
                                r[signal]=fv-hv
                            elif var=='pr' and hv <= 1e-12:
                                # A multiplicative precipitation factor is undefined for a dry
                                # historical month. The EPW morphing step only rescales existing
                                # wet hours, so it cannot defensibly create new rain events from a
                                # zero-rain baseline. Preserve the baseline precipitation structure
                                # with an identity ratio and make the fallback explicit for audit.
                                r[signal]=1.0
                                r['pr_dry_baseline_fallback']=True
                            else:
                                r[signal]=_safe_ratio(fv,hv,var,month)
                        rows.append(r)
    return pd.DataFrame(rows)


def ensemble_summary(per_gcm: pd.DataFrame) -> pd.DataFrame:
    group=['city','scenario','future_period','target_label','month']
    frames=[]
    for stat in ('mean','median','std','min','max'):
        g=per_gcm.groupby(group,as_index=False)[list(SIGNAL_FIELDS)]
        if stat=='mean': df=g.mean()
        elif stat=='median': df=g.median()
        elif stat=='std': df=g.std(ddof=1)
        elif stat=='min': df=g.min()
        else: df=g.max()
        df.insert(len(group),'ensemble_stat',stat)
        frames.append(df)
    return pd.concat(frames,ignore_index=True)


def signal_dict_from_factor_table(
    factor_table: pd.DataFrame, *, city: str, scenario: str, target_label: str,
    model: str|None=None, ensemble_stat: str|None=None,
):
    if (model is None)==(ensemble_stat is None):
        raise ValueError('Specify exactly one of model= or ensemble_stat=')
    df=factor_table[(factor_table.city==city)&(factor_table.scenario==scenario)&
                    (factor_table.target_label.astype(str)==str(target_label))].copy()
    if model is not None:
        if 'model' not in df.columns: raise ValueError("factor table has no 'model' column")
        df=df[df.model==model]
    else:
        if 'ensemble_stat' not in df.columns: raise ValueError("factor table has no 'ensemble_stat' column")
        df=df[df.ensemble_stat==ensemble_stat]
    df=df.sort_values('month')
    if df.month.astype(int).tolist()!=list(range(1,13)):
        raise ValueError('Need exactly months 1..12 after filtering')
    return {field:df[field].to_numpy(dtype=float) for field in SIGNAL_FIELDS}
