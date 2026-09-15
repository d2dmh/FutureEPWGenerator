import importlib.util
import json
from pathlib import Path
import pandas as pd

from config import MODEL_CONFIG, REQUIRED_VARIABLES
from src.factors import build_factors, ensemble_summary
from tests.test_epw_morphing import make_full_epw

ROOT=Path(__file__).resolve().parents[1]


def load_stage(name):
    p=ROOT/name
    spec=importlib.util.spec_from_file_location(name.replace('.py',''),p)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def make_full_catalog():
    rows=[]
    for model,(member,grid) in MODEL_CONFIG.items():
        for exp in ['historical','ssp126','ssp245','ssp370']:
            for var in REQUIRED_VARIABLES:
                rows.append(dict(source_id=model,experiment_id=exp,member_id=member,table_id='Amon',
                                 variable_id=var,grid_label=grid,zstore=f'gs://{model}/{exp}/{var}',version='v1'))
        rows.append(dict(source_id=model,experiment_id='historical',member_id=member,table_id='fx',
                         variable_id='sftlf',grid_label=grid,zstore=f'gs://{model}/historical/sftlf',version='v1'))
    return pd.DataFrame(rows)


def make_climatology(city='Beijing'):
    base={'tas':280,'tasmax':285,'tasmin':275,'huss':0.01,'psl':101000,'sfcWind':4,'clt':50,'rsds':200,'rlds':300,'pr':1e-5}
    rows=[]
    for model in MODEL_CONFIG:
        for var in REQUIRED_VARIABLES:
            for month in range(1,13):
                rows.append(dict(city=city,model=model,experiment='historical',period='1985-2014',variable=var,month=month,value=base[var]))
                for exp in ['ssp126','ssp245','ssp370']:
                    for period,label,scale in [('2030-2050','2040',1),('2050-2070','2060',2)]:
                        v=base[var]*(1+0.1*scale) if var in {'huss','sfcWind','pr'} else base[var]+scale
                        rows.append(dict(city=city,model=model,experiment=exp,period=period,variable=var,month=month,value=v))
    return pd.DataFrame(rows)


def test_stage00_validates_baseline_epw_offline(tmp_path):
    epwdir=tmp_path/'epw'; epwdir.mkdir(); make_full_epw(epwdir/'Beijing_545110.epw')
    out=tmp_path/'environment.json'
    mod=load_stage('00_check_environment.py')
    rc=mod.main(['--epw-dir',str(epwdir),'--cities','Beijing','--out',str(out),'--skip-remote-package-check'])
    assert rc==0
    data=json.loads(out.read_text())
    assert data['baseline_epw']['passed'] is True


def test_stage01_writes_frozen_manifests_and_288_case_matrix(tmp_path):
    cat=tmp_path/'catalog.csv'; make_full_catalog().to_csv(cat,index=False)
    out=tmp_path/'manifest'
    mod=load_stage('01_prepare_manifest.py')
    assert mod.main(['--catalog',str(cat),'--out-dir',str(out)])==0
    assert pd.read_csv(out/'manifest_cmip6.csv').shape[0]==200
    assert pd.read_csv(out/'manifest_sftlf.csv').shape[0]==5
    assert pd.read_csv(out/'case_matrix.csv').shape[0]==288


def test_stage01_custom_subset_writes_20_assets(tmp_path):
    cat=tmp_path/'catalog.csv'; make_full_catalog().to_csv(cat,index=False)
    out=tmp_path/'manifest_custom'
    mod=load_stage('01_prepare_manifest.py')
    assert mod.main([
        '--catalog',str(cat),'--out-dir',str(out),
        '--models','ACCESS-CM2','--experiments','historical','ssp126','--periods','2040',
    ])==0
    assert pd.read_csv(out/'manifest_cmip6.csv').shape[0]==20
    metadata=json.loads((out/'manifest_metadata.json').read_text())
    assert metadata['main_assets']==20
    assert metadata['selection']['models']==['ACCESS-CM2']
    assert metadata['selection']['experiments']==['historical','ssp126']
    assert metadata['selection']['periods']==['2040']


def test_stage02_status_reports_missing_cache_without_network(tmp_path):
    row=dict(source_id='ACCESS-CM2',experiment_id='historical',member_id='r1i1p1f1',grid_label='gn',
             table_id='Amon',variable_id='tas',zstore='gs://x',version='v1')
    manifest=tmp_path/'manifest.csv'; pd.DataFrame([row]).to_csv(manifest,index=False)
    epwdir=tmp_path/'epw'; epwdir.mkdir(); make_full_epw(epwdir/'Beijing_545110.epw')
    report=tmp_path/'status.json'
    mod=load_stage('02_extract_cmip6.py')
    rc=mod.main(['--manifest',str(manifest),'--epw-dir',str(epwdir),'--cities','Beijing',
                 '--cache-dir',str(tmp_path/'cache'),'--status','--status-out',str(report)])
    assert rc==0
    data=json.loads(report.read_text())
    assert data['total']==1 and data['cached']==0 and data['missing']==1


def test_stage03_builds_factor_files_from_explicit_climatology(tmp_path):
    clim=tmp_path/'clim.csv'; make_climatology().to_csv(clim,index=False)
    out=tmp_path/'factors'
    mod=load_stage('03_build_climate_factors.py')
    assert mod.main(['--climatology',str(clim),'--out-dir',str(out)])==0
    per=pd.read_csv(out/'climate_factors_per_gcm.csv')
    ens=pd.read_csv(out/'climate_factors_ensemble.csv')
    assert len(per)==5*3*2*12
    assert len(ens[ens.ensemble_stat=='mean'])==3*2*12


def test_stage04_and_05_generate_and_validate_one_epw(tmp_path):
    epwdir=tmp_path/'epw'; epwdir.mkdir(); make_full_epw(epwdir/'Beijing_545110.epw')
    clim=make_climatology(); per=build_factors(clim); ens=ensemble_summary(per)
    pf=tmp_path/'per.csv'; ef=tmp_path/'ens.csv'; per.to_csv(pf,index=False); ens.to_csv(ef,index=False)
    out=tmp_path/'future'; audit=tmp_path/'audit'
    s4=load_stage('04_generate_future_epw.py')
    rc=s4.main(['--per-gcm',str(pf),'--ensemble',str(ef),'--epw-dir',str(epwdir),
                '--out-dir',str(out),'--audit-dir',str(audit),'--cities','Beijing',
                '--scenarios','ssp245','--labels','2040','--selectors','ACCESS-CM2'])
    assert rc==0
    epws=list(out.rglob('*.epw')); assert len(epws)==1
    assert len(list(audit.glob('*_audit.csv')))==1
    s5=load_stage('05_validate_outputs.py')
    valout=tmp_path/'validation'
    rc=s5.main(['--epw-dir',str(out),'--audit-dir',str(audit),'--out-dir',str(valout)])
    assert rc==0
    summary=pd.read_csv(valout/'validation_summary.csv')
    assert len(summary)==1 and bool(summary.iloc[0]['passed'])
    assert (valout/'target_vs_achieved_summary.csv').exists()


def test_custom_single_model_single_ssp_single_period_generates_two_epws(tmp_path):
    epwdir=tmp_path/'epw'; epwdir.mkdir(); make_full_epw(epwdir/'Tokyo_476710.epw')
    location_spec=tmp_path/'location_spec.json'
    location_spec.write_text(json.dumps({
        'locations':[{'city':'Tokyo','latitude':35.5533,'longitude':139.7811,
                      'baseline_epw':str((epwdir/'Tokyo_476710.epw').resolve())}]
    }))
    clim=tmp_path/'clim.csv'; make_climatology(city='Tokyo').to_csv(clim,index=False)
    factors=tmp_path/'factors'
    s3=load_stage('03_build_climate_factors.py')
    assert s3.main([
        '--climatology',str(clim),'--out-dir',str(factors),
        '--models','ACCESS-CM2','--scenarios','ssp126','--labels','2040',
    ])==0
    per=pd.read_csv(factors/'climate_factors_per_gcm.csv')
    ens=pd.read_csv(factors/'climate_factors_ensemble.csv')
    assert set(per['model'])=={'ACCESS-CM2'}
    assert set(per['scenario'])=={'ssp126'}
    assert set(per['target_label'].astype(str))=={'2040'}

    out=tmp_path/'future'; audit=tmp_path/'audit'
    s4=load_stage('04_generate_future_epw.py')
    assert s4.main([
        '--per-gcm',str(factors/'climate_factors_per_gcm.csv'),
        '--ensemble',str(factors/'climate_factors_ensemble.csv'),
        '--epw-dir',str(epwdir),'--location-spec',str(location_spec),
        '--out-dir',str(out),'--audit-dir',str(audit),
        '--cities','Tokyo','--scenarios','ssp126','--labels','2040',
        '--selectors','ACCESS-CM2','mean',
    ])==0
    assert len(list(out.rglob('*.epw')))==2
    s5=load_stage('05_validate_outputs.py')
    valout=tmp_path/'validation'
    assert s5.main(['--epw-dir',str(out),'--audit-dir',str(audit),'--out-dir',str(valout)])==0
    summary=pd.read_csv(valout/'validation_summary.csv')
    assert len(summary)==2 and summary['passed'].astype(bool).all()


def test_stage02_defaults_to_gcs_then_aws_provider_order():
    mod=load_stage('02_extract_cmip6.py')
    assert tuple(mod.DEFAULT_PROVIDERS)==('gcs','aws')


def test_stage02_provider_fallback_uses_aws_after_gcs_failure(monkeypatch):
    mod=load_stage('02_extract_cmip6.py')
    row=pd.Series(dict(source_id='M',experiment_id='ssp126',variable_id='clt',zstore='gs://cmip6/x'))
    calls=[]
    expected=pd.DataFrame({'x':[1]})
    def fake(row_arg, locations, timeout, provider):
        calls.append(provider)
        if provider=='gcs':
            raise TimeoutError('gcs slow')
        return expected
    monkeypatch.setattr(mod,'_run_worker_subprocess',fake)
    got=mod._run_with_providers(row,{'A':(1,2)},300,['gcs','aws'],progress=lambda _:None)
    assert calls==['gcs','aws']
    assert got.equals(expected)


def test_stage02_city_provider_fallback_returns_provider(monkeypatch):
    mod=load_stage('02_extract_cmip6.py')
    row=pd.Series(dict(source_id='M',experiment_id='ssp126',variable_id='clt',zstore='gs://cmip6/x'))
    calls=[]
    expected=pd.DataFrame({'x':[1]})
    def fake(row_arg, city, location, timeout, provider):
        calls.append((city,provider))
        if provider=='gcs':
            raise TimeoutError('gcs slow')
        return expected
    monkeypatch.setattr(mod,'_run_city_worker_subprocess',fake)
    got,provider=mod._run_city_with_providers(row,'Delhi',(1,2),300,['gcs','aws'],progress=lambda _:None)
    assert calls==[('Delhi','gcs'),('Delhi','aws')]
    assert provider=='aws'
    assert got.equals(expected)


def test_stage01b_defaults_to_gcs_then_aws_provider_order():
    mod=load_stage('01b_check_land_fraction.py')
    assert tuple(mod.DEFAULT_PROVIDERS)==('gcs','aws')


def test_stage01b_provider_fallback_uses_aws(monkeypatch):
    mod=load_stage('01b_check_land_fraction.py')
    row=pd.Series(dict(source_id='M',experiment_id='historical',member_id='r1',grid_label='gn',
                       variable_id='sftlf',zstore='gs://cmip6/x',version='v1'))
    support=pd.DataFrame({'source_id':['M'],'city':['Singapore'],'sftlf_pct':[10.0]})
    summary=pd.DataFrame({'source_id':['M'],'city':['Singapore'],'effective_land_fraction_pct':[10.0]})
    calls=[]
    def fake(row_arg, locations, timeout, provider):
        calls.append(provider)
        if provider=='gcs':
            raise TimeoutError('gcs slow')
        return support.copy(),summary.copy()
    monkeypatch.setattr(mod,'_run_worker_subprocess',fake)
    got_support,got_summary,winner=mod._run_with_providers(
        row,{'Singapore':(1.3,103.9)},300,['gcs','aws'],progress=lambda _:None
    )
    assert calls==['gcs','aws']
    assert winner=='aws'
    assert got_support.equals(support)
    assert got_summary.equals(summary)


def test_stage02b_defaults_to_three_coastal_cities_and_five_surface_variables():
    mod=load_stage('02b_coastal_sensitivity.py')
    assert tuple(mod.FOCUS_CITIES)==('Singapore','Sydney','Kuwait City')
    assert tuple(mod.FOCUS_VARIABLES)==('tas','tasmax','tasmin','huss','sfcWind')
    assert tuple(mod.DEFAULT_PROVIDERS)==('gcs','aws')


def test_stage02b_manifest_filter_keeps_only_requested_assets():
    from src.catalog import select_main_manifest
    mod=load_stage('02b_coastal_sensitivity.py')
    main=select_main_manifest(make_full_catalog(),['historical','ssp126','ssp245','ssp370'])
    sub=mod._filter_manifest(main,['tas','huss'],['ssp370'])
    # 5 models x (historical + ssp370) x 2 variables
    assert len(sub)==5*2*2
    assert set(sub.variable_id)=={'tas','huss'}
    assert set(sub.experiment_id)=={'historical','ssp370'}


def test_stage01c_selects_only_fgoals_sftlf_asset():
    from src.catalog import select_sftlf_manifest
    mod=load_stage('01c_fgoals_madrid_landmask_qa.py')
    fx=select_sftlf_manifest(make_full_catalog())
    row=mod._select_fgoals_row(fx)
    assert row.source_id=='FGOALS-g3'
    assert row.variable_id=='sftlf'


def _rewrite_location(path: Path, *, city: str, wmo: str, lat: float, lon: float, tz: float = 1.0, elev: float = 89.0):
    lines = path.read_text(encoding='utf-8').splitlines()
    lines[0] = f'LOCATION,{city},Region,FRA,TMYx,{wmo},{lat},{lon},{tz},{elev}'
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return path


def _write_location_spec(path: Path, *, city: str, epw: Path, lat: float, lon: float, wmo: str):
    payload = {
        'version': 1,
        'locations': [{
            'city': city,
            'latitude': lat,
            'longitude': lon,
            'wmo': wmo,
            'station': city,
            'baseline_epw': str(epw.resolve()),
        }],
    }
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def test_stage00_accepts_arbitrary_city_from_location_spec(tmp_path):
    epwdir=tmp_path/'epw'; epwdir.mkdir()
    epw=_rewrite_location(epwdir/'Paris_071490.epw' if False else epwdir/'Paris.epw', city='Paris-Orly', wmo='071490', lat=48.7262, lon=2.3652) if False else None
    epw=epwdir/'Paris.epw'; make_full_epw(epw); _rewrite_location(epw, city='Paris-Orly', wmo='071490', lat=48.7262, lon=2.3652)
    spec=_write_location_spec(tmp_path/'location.json', city='Paris', epw=epw, lat=48.7262, lon=2.3652, wmo='071490')
    out=tmp_path/'environment.json'
    mod=load_stage('00_check_environment.py')
    rc=mod.main(['--location-spec',str(spec),'--out',str(out),'--skip-remote-package-check'])
    assert rc==0
    data=json.loads(out.read_text())
    assert data['baseline_epw']['passed'] is True
    assert data['baseline_epw']['files'][0]['city']=='Paris'


def test_stage02_status_uses_arbitrary_city_location_spec_without_registry(tmp_path):
    row=dict(source_id='ACCESS-CM2',experiment_id='historical',member_id='r1i1p1f1',grid_label='gn',
             table_id='Amon',variable_id='tas',zstore='gs://x',version='v1')
    manifest=tmp_path/'manifest.csv'; pd.DataFrame([row]).to_csv(manifest,index=False)
    epw=tmp_path/'Paris.epw'; make_full_epw(epw); _rewrite_location(epw, city='Paris-Orly', wmo='071490', lat=48.7262, lon=2.3652)
    spec=_write_location_spec(tmp_path/'location.json', city='Paris', epw=epw, lat=48.7262, lon=2.3652, wmo='071490')
    report=tmp_path/'status.json'
    mod=load_stage('02_extract_cmip6.py')
    rc=mod.main(['--manifest',str(manifest),'--location-spec',str(spec),
                 '--cache-dir',str(tmp_path/'cache'),'--city-cache-dir',str(tmp_path/'city-cache'),
                 '--status','--status-out',str(report)])
    assert rc==0
    data=json.loads(report.read_text())
    assert data['cities']==['Paris']
    assert data['locations'][0]['latitude']==48.7262
    assert data['current_city_complete']==0
    assert data['current_city_total']==1


def test_stage04_generates_arbitrary_city_using_exact_baseline_from_location_spec(tmp_path):
    epwdir=tmp_path/'epw'; epwdir.mkdir()
    epw=epwdir/'Paris.epw'; make_full_epw(epw); _rewrite_location(epw, city='Paris-Orly', wmo='071490', lat=48.7262, lon=2.3652)
    spec=_write_location_spec(tmp_path/'location.json', city='Paris', epw=epw, lat=48.7262, lon=2.3652, wmo='071490')
    clim=make_climatology('Paris'); per=build_factors(clim); ens=ensemble_summary(per)
    pf=tmp_path/'per.csv'; ef=tmp_path/'ens.csv'; per.to_csv(pf,index=False); ens.to_csv(ef,index=False)
    out=tmp_path/'future'; audit=tmp_path/'audit'
    s4=load_stage('04_generate_future_epw.py')
    rc=s4.main(['--per-gcm',str(pf),'--ensemble',str(ef),'--location-spec',str(spec),
                '--out-dir',str(out),'--audit-dir',str(audit),'--cities','Paris',
                '--scenarios','ssp245','--labels','2040','--selectors','ACCESS-CM2'])
    assert rc==0
    epws=list(out.rglob('*.epw'))
    assert len(epws)==1
    rec=pd.read_csv(out/'generation_records.csv')
    assert rec.iloc[0].city=='Paris'
    assert Path(rec.iloc[0].base_epw).resolve()==epw.resolve()


def test_stage02_can_seed_location_cache_from_legacy_multicity_asset(tmp_path):
    row=dict(source_id='ACCESS-CM2',experiment_id='historical',member_id='r1i1p1f1',grid_label='gn',
             table_id='Amon',variable_id='tas',zstore='gs://x',version='v1')
    manifest=tmp_path/'manifest.csv'; pd.DataFrame([row]).to_csv(manifest,index=False)
    epw=tmp_path/'Singapore.epw'; make_full_epw(epw)
    spec=_write_location_spec(tmp_path/'location.json', city='Singapore', epw=epw, lat=40.08, lon=116.585, wmo='545110')
    legacy=tmp_path/'legacy'; legacy.mkdir()
    from src.cmip6_io import cache_filename
    s=pd.Series(row)
    rows=[]
    for city in ['Singapore','Beijing']:
        for month in range(1,13):
            rows.append({
                'city':city,'source_id':row['source_id'],'experiment_id':row['experiment_id'],
                'member_id':row['member_id'],'grid_label':row['grid_label'],'variable_id':row['variable_id'],
                'zstore':row['zstore'],'version':row['version'],'model':row['source_id'],'experiment':row['experiment_id'],
                'period':'1985-2014','variable':row['variable_id'],'month':month,'value':280.0,
            })
    pd.DataFrame(rows).to_csv(legacy/cache_filename(s),index=False)
    report=tmp_path/'status.json'; cache=tmp_path/'new-cache'; city_cache=tmp_path/'new-city-cache'
    mod=load_stage('02_extract_cmip6.py')
    rc=mod.main(['--manifest',str(manifest),'--location-spec',str(spec),'--cities','Singapore',
                 '--cache-dir',str(cache),'--city-cache-dir',str(city_cache),
                 '--legacy-cache-dir',str(legacy),'--status','--status-out',str(report)])
    assert rc==0
    data=json.loads(report.read_text())
    assert data['current_city_complete']==1
    assert len(list(city_cache.glob('*.csv')))==1


def test_stage02_frozen_worker_reenters_engine_dispatch(monkeypatch, tmp_path):
    mod=load_stage('02_extract_cmip6.py')
    monkeypatch.setattr(mod.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(mod.sys, 'executable', 'FutureEPWEngine.exe', raising=False)
    cmd=mod._worker_command(tmp_path/'job.json')
    assert cmd == ['FutureEPWEngine.exe','--engine-stage','02_extract_cmip6.py','--worker-job',str(tmp_path/'job.json')]
