from __future__ import annotations
import pandas as pd
from config import CITIES, MODEL_CONFIG, SCENARIOS

def build_case_matrix(cities=None, scenarios=None, periods=None, models=None) -> pd.DataFrame:
    cities=list(CITIES) if cities is None else list(cities)
    scenarios=list(SCENARIOS) if scenarios is None else list(scenarios)
    periods=['2040','2060'] if periods is None else [str(x) for x in periods]
    models=list(MODEL_CONFIG) if models is None else list(models)
    rows=[]
    for city in cities:
        for scenario in scenarios:
            for label in periods:
                for model in models:
                    rows.append({'city':city,'scenario':scenario,'target_label':label,
                                 'selector_type':'model','selector':model})
                rows.append({'city':city,'scenario':scenario,'target_label':label,
                             'selector_type':'ensemble_stat','selector':'mean'})
    return pd.DataFrame(rows)
