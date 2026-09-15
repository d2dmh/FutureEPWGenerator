from datetime import date, timedelta
from pathlib import Path
import numpy as np

from src.epw import read_epw, epw_to_morph_base, write_morphed_epw
from src.morphing import morph, zero_signal, synth_climate_signal, solar_elevation


def make_full_epw(path: Path):
    header=[
        'LOCATION,Beijing,Beijing,CHN,TMYx,545110,40.0800,116.5850,8.0,35.4',
        'DESIGN CONDITIONS,0','TYPICAL/EXTREME PERIODS,0','GROUND TEMPERATURES,0',
        'HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0','COMMENTS 1,synthetic full year',
        'COMMENTS 2,synthetic full year','DATA PERIODS,1,1,Data,Sunday,1/1,12/31',
    ]
    rows=[]; d0=date(2001,1,1)
    for di in range(365):
        cur=d0+timedelta(days=di)
        for h in range(1,25):
            t=10+10*np.sin(2*np.pi*di/365)+3*np.sin(2*np.pi*(h-8)/24)
            elev=float(solar_elevation(di+1,h,40.08,116.585,120.0))
            ghi=max(0.0,500*np.sin(np.radians(elev))) if elev>0 else 0.0
            row=[2001,cur.month,cur.day,h,60,'0',t,t-5,60,101325,0,0,320,ghi,ghi*0.7,ghi*0.3,
                 0,0,0,0,180,2.5,5,4,20,77777,9,999999999,10,0.1,0,99,0.2,1.0 if (di*24+h)%97==0 else 0.0,1]
            rows.append(','.join(map(str,row)))
    path.write_text('\n'.join(header+rows)+'\n',encoding='utf-8')


def test_read_and_convert_full_epw(tmp_path):
    p=tmp_path/'base.epw'; make_full_epw(p)
    epw=read_epw(p); base=epw_to_morph_base(epw)
    assert len(epw.data)==8760
    assert len(base)==8760
    assert epw.location.wmo=='545110'
    assert np.isfinite(base[['elev','Iext']].to_numpy()).all()


def test_zero_signal_is_exact_identity_before_serialization(tmp_path):
    p=tmp_path/'base.epw'; make_full_epw(p)
    base=epw_to_morph_base(read_epw(p))
    out=morph(base,zero_signal())
    mapping={'T1':'T','RH1':'RH','P1':'P','V1':'V','Ntotal1':'Ntotal','Nopaque1':'Nopaque',
             'GHI1':'GHI','DNI1':'DNI','DHI1':'DHI','Rain1':'Rain','IRH1':'IRH'}
    for a,b in mapping.items():
        np.testing.assert_allclose(out[a],base[b],rtol=0,atol=1e-12)
    # Dew point is intentionally recomputed from T/RH/P; source TMYx Td is only diagnostic.
    assert np.isfinite(out['Td1']).all()


def test_btws_targets_monthly_mean_and_daily_extrema(tmp_path):
    p=tmp_path/'base.epw'; make_full_epw(p)
    base=epw_to_morph_base(read_epw(p)); sig=synth_climate_signal(); out=morph(base,sig)
    for m in range(1,13):
        mask=base.month==m
        assert abs((out.loc[mask,'T1'].mean()-base.loc[mask,'T'].mean())-sig['d_tas'][m-1]) < 1e-8
        day=base.loc[mask,'day'].to_numpy()
        import pandas as pd
        d=pd.DataFrame({'day':day,'t0':base.loc[mask,'T'].to_numpy(),'t1':out.loc[mask,'T1'].to_numpy()})
        g=d.groupby('day')
        assert abs((g.t1.max()-g.t0.max()).mean()-sig['d_tasmax'][m-1]) < 1e-8
        assert abs((g.t1.min()-g.t0.min()).mean()-sig['d_tasmin'][m-1]) < 1e-8


def test_shortwave_partition_and_opaque_cover_are_preserved_by_ratio(tmp_path):
    p=tmp_path/'base.epw'; make_full_epw(p)
    base=epw_to_morph_base(read_epw(p)); sig=zero_signal(); sig['d_rsds']=np.full(12,-5.0)
    out=morph(base,sig)
    active=base.GHI.to_numpy()>1e-9
    ratio=out.loc[active,'GHI1'].to_numpy()/base.loc[active,'GHI'].to_numpy()
    np.testing.assert_allclose(out.loc[active,'DNI1'],base.loc[active,'DNI']*ratio,rtol=1e-12,atol=1e-10)
    np.testing.assert_allclose(out.loc[active,'DHI1'],base.loc[active,'DHI']*ratio,rtol=1e-12,atol=1e-10)
    np.testing.assert_allclose(out['Nopaque1'],base['Nopaque'],rtol=0,atol=1e-12)


def test_write_roundtrip_preserves_8760_and_header(tmp_path):
    p=tmp_path/'base.epw'; q=tmp_path/'future.epw'; make_full_epw(p)
    epw=read_epw(p); base=epw_to_morph_base(epw); out=morph(base,zero_signal())
    write_morphed_epw(epw,out,q,provenance='unit-test')
    new=read_epw(q)
    assert len(new.data)==8760
    assert new.header_lines[0]==epw.header_lines[0]
    assert 'unit-test' in new.header_lines[6]
