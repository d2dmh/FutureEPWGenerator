"""
v2：在v1基础上做三处升级，全部对照可查证的原始公式实现：

1. 温度: 经典Belcher shift-and-stretch -> BTWS (Bounded Temperature Weighted
   Stretch)，公式取自 Eames, Xie, Mylona, Shilston, Hacker (2024),
   "A revised morphing algorithm for creating future weather for building
   performance evaluation", BSER&T 45(1):5-20, eq. (9)-(16)。
   （已用 web_fetch 核对论文全文，CC-BY开放获取。）

2. 太阳辐射GHI、云量: 经典相对/加性缩放 -> BWS (Bounded Weighted Stretch)，
   同一篇论文 eq. (7)-(8)。

3. 新增 rlds -> Horizontal Infrared Radiation Intensity (IRH) 处理：
   对CMIP6 rlds月异常量做加性偏移(simple shift, Belcher 2005/Eames 2024 eq.1)；
   缺失时按 EnergyPlus Engineering Reference
   "Climate Calculations / Sky Radiation Modeling" 的 Clark & Allen (1978)
   + Walton (1983) 公式重新计算：
       IRH = eps_sky * sigma * Tdb_K^4
       eps_sky_clear = 0.787 + 0.764*ln(Tdp_K/273)
       eps_sky = eps_sky_clear * (1 + 0.0224N - 0.0035N^2 + 0.00028N^3)
       N = 不透明云量（0-10）， sigma = 5.6697e-8 W/m2/K4
   （已用 web_fetch 核对 EnergyPlus 官方文档，公式非本仓库推导。）

其余部分（湿度走比湿反算RH/露点、气压加性偏移、风速比例缩放、四层验收）沿用v1。
对真实EPW新增一条重要约束：若源文件提供DNI/DHI，则不再用BRL重分解短波，而是
保留源EPW的直散射结构，按逐时 GHI_future/GHI_base 同比例缩放DNI/DHI；仅在
源文件缺DNI/DHI时才回退到BRL。Opaque sky cover不作为CMIP6目标，主路径保持源值。注意：CMIP6 psl 的原始单位为 Pa，本脚本统一把气压异常量命名为
d_psl_pa，避免把文献表格中的 hPa 与CMIP6原始数据单位混用。仍然用合成基础天气+
合成CMIP6月因子作占位——真实运行时
把 synth_base_tmyx() 换成真实EPW读取、把 synth_climate_signal() 换成真实
CMIP6抽取结果即可，其余管线不用改。
"""
import numpy as np
import pandas as pd

HOURS = 8760
DAYS_IN_MONTH = [31,28,31,30,31,30,31,31,30,31,30,31]
MONTH_OF_HOUR = np.repeat(np.arange(1,13), [d*24 for d in DAYS_IN_MONTH])
DAY_OF_HOUR = np.repeat(np.arange(1,366), 24)
HOUR_OF_DAY = np.tile(np.arange(1,25), 365)
SIGMA = 5.6697e-8
assert len(MONTH_OF_HOUR) == HOURS

LAT, LON = 39.90, 116.41
STD_MERIDIAN = 120.0

# ---------------------------------------------------------------------------
# 1. 合成基础TMYx（占位，真实运行时替换为读取的EPW DataFrame）
# ---------------------------------------------------------------------------
def extraterrestrial_normal(doy):
    return 1367*(1+0.033*np.cos(2*np.pi*doy/365))

def solar_elevation(doy, hod, lat, lon, std_meridian):
    decl = 23.45*np.sin(np.radians(360*(284+doy)/365))
    B = 360*(doy-81)/364
    eot = 9.87*np.sin(np.radians(2*B)) - 7.53*np.cos(np.radians(B)) - 1.5*np.sin(np.radians(B))
    solar_time = hod - 0.5 + (4*(std_meridian-lon)+eot)/60.0
    hour_angle = 15*(solar_time-12)
    lat_r, decl_r, ha_r = map(np.radians, (lat, decl, hour_angle))
    sin_elev = np.sin(lat_r)*np.sin(decl_r) + np.cos(lat_r)*np.cos(decl_r)*np.cos(ha_r)
    return np.degrees(np.arcsin(np.clip(sin_elev,-1,1)))

def sat_vapor_pressure_pa(T_c):
    return 611.2*np.exp(17.62*T_c/(243.12+T_c))

def vapor_pressure_from_rh(T_c, RH):
    return sat_vapor_pressure_pa(T_c)*RH/100.0

def specific_humidity(e_pa, P_pa):
    return 0.622*e_pa/np.clip(P_pa-0.378*e_pa, 1, None)

def vapor_pressure_from_q(q, P_pa):
    return q*P_pa/(0.622+0.378*q)

def dew_point_from_e(e_pa):
    ln_ratio = np.log(np.clip(e_pa,1e-6,None)/611.2)
    return 243.12*ln_ratio/(17.62-ln_ratio)

def sky_irh(Tdb_c, Tdp_c, Nopaque_tenths):
    """EnergyPlus Clark & Allen (1978) + Walton (1983)。Tdb/Tdp单位摄氏度，N为0-10。"""
    Tdb_k = Tdb_c + 273.15
    Tdp_k = np.clip(Tdp_c + 273.15, 100, None)  # 避免log(<=0)
    eps_clear = 0.787 + 0.764*np.log(Tdp_k/273.0)
    N = np.clip(Nopaque_tenths, 0, 10)
    eps_sky = eps_clear*(1 + 0.0224*N - 0.0035*N**2 + 0.00028*N**3)
    eps_sky = np.clip(eps_sky, 0.5, 1.0)  # 物理合理范围内的安全夹取
    return eps_sky*SIGMA*Tdb_k**4

def synth_base_tmyx(seed=0):
    rng = np.random.default_rng(seed)
    doy, hod = DAY_OF_HOUR, HOUR_OF_DAY
    T = 12 + 18*(-np.cos(2*np.pi*(doy-15)/365)) + 8*np.sin(2*np.pi*(hod-9)/24) + rng.normal(0,1.0,HOURS)
    RH = np.clip(55 + 20*np.sin(2*np.pi*(doy-200)/365) - 0.4*(T-12) + rng.normal(0,5,HOURS), 5, 100)
    P = 101325 + 300*np.sin(2*np.pi*doy/365) + rng.normal(0,150,HOURS)
    V = np.clip(rng.lognormal(mean=1.0, sigma=0.5, size=HOURS) * (1+0.15*np.cos(2*np.pi*doy/365)), 0, 30)
    wind_dir = rng.uniform(0,360,HOURS)
    Ntotal = np.clip(rng.normal(5 + 1.5*np.sin(2*np.pi*(doy-200)/365), 2.2, HOURS), 0, 10).round()
    Nopaque = np.clip(Ntotal * rng.uniform(0.4,0.9,HOURS), 0, 10).round()
    elev = solar_elevation(doy, hod, LAT, LON, STD_MERIDIAN)
    Iext = extraterrestrial_normal(doy)
    ghi_clear = np.clip(Iext * np.clip(np.sin(np.radians(elev)),0,None) * 0.75, 0, None)
    cloud_atten = np.clip(1 - 0.75*(Ntotal/10)**2, 0.05, 1.0)
    GHI = np.where(elev>0, ghi_clear*cloud_atten, 0.0)
    wet_mask = rng.uniform(0,1,HOURS) < 0.06
    Rain0 = np.where(wet_mask, rng.exponential(1.2, HOURS), 0.0)
    Td0 = dew_point_from_e(vapor_pressure_from_rh(T, RH))
    IRH0 = sky_irh(T, Td0, Nopaque)

    return pd.DataFrame({
        "month": MONTH_OF_HOUR, "day": doy, "hour": hod,
        "T": T, "RH": RH, "P": P, "V": V, "wind_dir": wind_dir,
        "Ntotal": Ntotal, "Nopaque": Nopaque, "GHI": GHI,
        "Rain": Rain0, "elev": elev, "Iext": Iext, "Td": Td0, "IRH": IRH0,
    })

# ---------------------------------------------------------------------------
# 2. 12个月气候因子占位
# ---------------------------------------------------------------------------
def zero_signal():
    return {
        "d_tas": np.zeros(12), "d_tasmax": np.zeros(12), "d_tasmin": np.zeros(12),
        "d_psl_pa": np.zeros(12), "r_huss": np.ones(12), "r_wind": np.ones(12),
        "d_clt": np.zeros(12), "d_rsds": np.zeros(12), "d_rlds": np.zeros(12),
        "r_pr": np.ones(12),
    }

def synth_climate_signal():
    month = np.arange(12)
    warm_season_boost = 0.4*np.sin(2*np.pi*(month-5)/12)
    return {
        "d_tas":    2.0 + warm_season_boost,
        "d_tasmax": 2.3 + warm_season_boost,
        "d_tasmin": 1.6 + warm_season_boost,
        "d_psl_pa": -20 + 5*np.cos(2*np.pi*month/12),  # Pa（CMIP6 psl 原始单位）
        "r_huss":   1.0 + 0.06 + 0.02*np.sin(2*np.pi*month/12),
        "r_wind":   1.0 - 0.03*np.ones(12),
        "d_clt":    -1.5*np.ones(12),
        "d_rsds":   6.0*np.ones(12),
        "d_rlds":   4.0*np.ones(12),   # W/m2，长波辐射通常随增温、增湿而增加
        "r_pr":     1.08*np.ones(12),
    }

# ---------------------------------------------------------------------------
# 3a. BTWS —— 温度（Eames et al. 2024, eq. 9-16）
# ---------------------------------------------------------------------------
def btws_temperature(df, d_tas, d_tasmax, d_tasmin, return_diagnostics=False):
    """Eames et al. (2024) BTWS, eqs. (8)-(16), applied day by day.

    Critical detail: eq. (8) is x' = x + S * x_bar * g / g_bar, not
    x' = x + S*g.  The x_bar/g_bar normalization is what guarantees that
    the prescribed change in the mean is conserved together with the daily
    maximum/minimum targets when eq. (16) is used for S.

    This implementation uses the symmetric transfer function m=n=1.  If a
    day is degenerate or the transformed normalized values leave [0, 1], it
    follows the paper's conservative fallback and preserves the mean change
    via a simple shift.
    """
    T = df["T"].values.copy()
    day = df["day"].values
    daily = pd.DataFrame({"day": day, "T": T}).groupby("day")["T"].agg(["max","min","mean"])
    day_to_month = df.groupby("day")["month"].first()

    T1 = np.empty_like(T)
    diag = {
        "days_total": int(len(daily)),
        "fallback_flat_day": 0,
        "fallback_degenerate_target_range": 0,
        "fallback_degenerate_transfer": 0,
        "fallback_out_of_bounds": 0,
    }

    for d, row in daily.iterrows():
        mask = day == d
        Td = T[mask]
        Tmax0, Tmin0, Tmean0 = row["max"], row["min"], row["mean"]
        m = int(day_to_month.loc[d] - 1)

        base_range = Tmax0 - Tmin0
        if base_range < 1e-6:
            diag["fallback_flat_day"] += 1
            T1[mask] = Td + d_tas[m]
            continue

        x = (Td - Tmin0) / base_range                         # eq. (9)
        Tmean1 = Tmean0 + d_tas[m]                            # eq. (10)
        Tmin1  = Tmin0  + d_tasmin[m]                         # eq. (11)
        Tmax1  = Tmax0  + d_tasmax[m]                         # eq. (12)

        target_range = Tmax1 - Tmin1
        if target_range <= 1e-6 or (Tmean0 - Tmin0) <= 1e-9:
            diag["fallback_degenerate_target_range"] += 1
            T1[mask] = Td + d_tas[m]
            continue

        # eq. (16): choose S so the BTWS-transformed daily mean equals Tmean1.
        S = ((Tmean1 - Tmin1) / target_range) * \
            (base_range / (Tmean0 - Tmin0)) - 1.0

        # eqs. (7)-(8), symmetric transfer m=n=1.
        g = x * (1.0 - x)
        x_mean = x.mean()
        g_mean = g.mean()
        if x_mean <= 1e-12 or g_mean <= 1e-12:
            diag["fallback_degenerate_transfer"] += 1
            T1[mask] = Td + d_tas[m]
            continue

        x1 = x + S * x_mean * g / g_mean                      # eq. (8)
        if np.any(x1 < -1e-9) or np.any(x1 > 1.0 + 1e-9):
            # Paper permits a mean-preserving simple-shift fallback when a
            # physically admissible bounded transform cannot be obtained.
            diag["fallback_out_of_bounds"] += 1
            T1[mask] = Td + d_tas[m]
        else:
            x1 = np.clip(x1, 0.0, 1.0)
            T1[mask] = Tmin1 + x1 * target_range              # eq. (13)

    if return_diagnostics:
        diag["fallback_total"] = int(sum(v for k, v in diag.items() if k.startswith("fallback_") and k != "fallback_total"))
        return T1, diag
    return T1

# ---------------------------------------------------------------------------
# 3b. BWS —— 通用有界变量（短波辐射、云量）
# ---------------------------------------------------------------------------
def bws_bounded(df, values, month_idx, lo, hi, target_rel_or_abs, is_relative):
    """
    values: 原始序列（如GHI、Ntotal、rlds）
    lo/hi:  物理上下界（如GHI用[0, 逐月观测最大值]，云量用[0,10]）
    target_rel_or_abs: 12个月的目标——若is_relative=True则是相对变化量S(直接用)，
                        若False则是绝对差，会先换算成S = (mean+Δ)/mean - 1
    """
    v = values.astype(float).copy()
    out = np.zeros_like(v)
    for m in range(12):
        mask = month_idx == m
        vm = v[mask]
        lo_m = lo[mask] if np.ndim(lo) else lo
        hi_m = hi[mask] if np.ndim(hi) else hi
        x = np.clip((vm - lo_m) / np.clip(hi_m - lo_m, 1e-9, None), 0, 1)   # eq.(9)-式归一化
        g = x * (1 - x)                                                     # eq.(7), m=n=1
        g_mean = g.mean() if g.mean() > 1e-9 else 1e-9
        x_mean = x.mean()
        if is_relative:
            S = target_rel_or_abs[m]
        else:
            base_mean = vm.mean() if vm.mean() > 1e-9 else 1e-9
            S = (base_mean + target_rel_or_abs[m]) / base_mean - 1
        x1 = x + S * x_mean * g / g_mean                                    # eq.(8)
        x1 = np.clip(x1, 0, 1)
        out[mask] = lo_m + x1 * (hi_m - lo_m)
    return out

def brl_decompose(GHI, elev_deg, Iext, doy, hod):
    b0,b1,b2,b3,b4,b5 = -5.38, 6.63, 0.006, -0.007, 1.75, 1.31
    elev = np.clip(elev_deg, 0.1, 90)
    kt = np.clip(GHI/np.clip(Iext*np.sin(np.radians(elev)),1e-6,None), 0, 1.5)
    AST = hod - 0.5
    day_df = pd.DataFrame({"doy":doy, "kt":kt})
    Kt = day_df.groupby("doy")["kt"].transform("mean").values
    psi = pd.Series(kt).rolling(3, center=True, min_periods=1).mean().values
    d = np.clip(1/(1+np.exp(b0+b1*kt+b2*AST+b3*elev+b4*Kt+b5*psi)), 0, 1)
    DHI = d*GHI
    with np.errstate(divide='ignore', invalid='ignore'):
        DNI = np.where(elev_deg>0.1, np.clip((GHI-DHI)/np.sin(np.radians(elev)), 0, Iext), 0.0)
    DHI = np.clip(GHI - DNI*np.sin(np.radians(np.clip(elev_deg,0,90))), 0, GHI)
    DHI = np.where(elev_deg>0, DHI, 0.0)
    DNI = np.where(elev_deg>0, DNI, 0.0)
    return DHI, DNI

# ---------------------------------------------------------------------------
# 4. 主形变函数
# ---------------------------------------------------------------------------
def morph(base: pd.DataFrame, signal: dict) -> pd.DataFrame:
    df = base.copy()
    month_idx = df["month"].values - 1

    # ---- 温度：BTWS ----
    T1, btws_diag = btws_temperature(
        df, signal["d_tas"], signal["d_tasmax"], signal["d_tasmin"],
        return_diagnostics=True,
    )

    # ---- 气压：psl异常量加性偏移 ----
    # CMIP6 Amon psl 的单位是 Pa；EPW Atmospheric Station Pressure 也是 Pa。
    # 新接口显式使用 d_psl_pa。为兼容旧的合成/调用代码，若仅提供 d_psl，
    # 也按 Pa 解释，但正式数据管线应统一改用 d_psl_pa。
    if "d_psl_pa" in signal:
        d_psl_pa = np.asarray(signal["d_psl_pa"], dtype=float)
    elif "d_psl" in signal:
        d_psl_pa = np.asarray(signal["d_psl"], dtype=float)
    else:
        raise KeyError("signal must contain 'd_psl_pa' (12 monthly psl anomalies in Pa)")
    if d_psl_pa.shape != (12,):
        raise ValueError("d_psl_pa must contain exactly 12 monthly anomalies in Pa")
    P1 = df["P"].values + d_psl_pa[month_idx]

    # ---- 湿度：比湿伸缩 -> 反算RH/露点（不变）----
    e0 = vapor_pressure_from_rh(df["T"].values, df["RH"].values)
    q0 = specific_humidity(e0, df["P"].values)
    q1 = np.clip(q0 * signal["r_huss"][month_idx], 0, 0.1)
    e1 = vapor_pressure_from_q(q1, P1)
    RH1 = np.clip(100*e1/sat_vapor_pressure_pa(T1), 1, 100)
    Td1 = dew_point_from_e(vapor_pressure_from_rh(T1, RH1))

    # ---- 风速：比例缩放（不变）----
    V1 = np.clip(df["V"].values * signal["r_wind"][month_idx], 0, None)

    # ---- 云量：BWS，上下界[0,10] ----
    lo10 = np.zeros(HOURS); hi10 = np.full(HOURS, 10.0)
    d_clt_tenths = signal["d_clt"] / 10.0  # 输入是百分点，云量场是0-10
    Ntotal1 = bws_bounded(df, df["Ntotal"].values, month_idx, lo10, hi10,
                           d_clt_tenths, is_relative=False)
    # Opaque sky cover is not directly constrained by a CMIP6 factor in this
    # workflow.  Since rlds is morphed directly, Nopaque is retained from the
    # source EPW rather than reconstructed from Ntotal.  This also guarantees
    # exact zero-signal identity for real TMYx files, including hours where the
    # source product itself has Nopaque > Ntotal.
    Nopaque1 = df["Nopaque"].values.copy()

    # ---- 短波辐射GHI：BWS，上下界[0, 当月观测最大值] ----
    month_max_ghi = df.groupby("month")["GHI"].transform("max").values
    lo0 = np.zeros(HOURS)
    GHI1 = bws_bounded(df, df["GHI"].values, month_idx, lo0, month_max_ghi,
                        signal["d_rsds"], is_relative=False)

    # Preserve the source EPW's DNI/DHI partition whenever those fields are
    # available.  Do NOT zero GHI using independently computed solar geometry:
    # real TMYx timestamps can differ from our internal sun-position convention
    # around sunrise/sunset, and overwriting them breaks identity even for a zero
    # climate signal.  For GHI>0, scale DNI and DHI by the same hourly ratio as
    # GHI.  For source GHI==0, leave source DNI/DHI unchanged (ratio=1) because
    # the source file is the authoritative hourly radiation record.
    if "DNI" in df.columns and "DHI" in df.columns:
        ghi0 = df["GHI"].values.astype(float)
        scale = np.ones_like(ghi0)
        active = ghi0 > 1e-9
        scale[active] = GHI1[active] / ghi0[active]
        DNI1 = np.clip(df["DNI"].values.astype(float) * scale, 0, None)
        DHI1 = np.clip(df["DHI"].values.astype(float) * scale, 0, None)
        shortwave_partition_mode = "source_ratio_scaling"
    else:
        # Backward-compatible fallback for synthetic/legacy inputs that do not
        # carry source direct/diffuse radiation.
        DHI1, DNI1 = brl_decompose(GHI1, df["elev"].values, df["Iext"].values,
                                    df["day"].values, df["hour"].values)
        shortwave_partition_mode = "brl_fallback"

    # ---- 长波辐射：CMIP6 rlds月异常量加性偏移(shift)，缺失时用Clark&Allen+Walton重算 ----
    # 改用加性shift而非BWS：Eames et al. 2024原文只对温度(BTWS)和有明确物理上下界的
    # 辐射/云量(BWS)给出过数学证明和实证验证，未覆盖rlds；rlds虽然也有物理边界（晴空下限、
    # 满云上限），但这对边界本身随逐时气温浮动，不像GHI/云量那样是固定值，直接套BWS的
    # 归一化假设不够严谨。加性偏移是Belcher(2005)/Eames(2024)论文eq.(1)本身就验证过的
    # "simple shift"，更容易在方法学审查中站住脚，之后再做物理范围裁剪兜底。
    d_rlds = signal.get("d_rlds", None)
    if d_rlds is not None:
        d_rlds = np.asarray(d_rlds, dtype=float)
        if d_rlds.shape != (12,):
            raise ValueError("d_rlds must be None (fallback) or exactly 12 monthly anomalies in W/m2")
        IRH1 = df["IRH"].values + d_rlds[month_idx]
        IRH1 = np.clip(IRH1, 100, 600)  # 安全范围兜底；validation_report会检查目标是否仍被实现
        rlds_mode = "cmip6_shift"
    else:
        # 真正缺失 rlds 时才进入后备公式；零异常量是有效信号，不能被当作“缺失”。
        IRH1 = sky_irh(T1, Td1, Nopaque1)
        rlds_mode = "clark_allen_walton_fallback"

    # ---- 降水：只缩放已有湿小时（不变）----
    # 形变核心层不做小数位舍入，否则 r_pr=1 的 identity test 也会产生非零误差。
    # 若EPW输出格式需要固定小数位，应在最终序列化/写文件阶段再统一格式化。
    wet_mask = df["Rain"].values > 0
    Rain1 = np.where(wet_mask, df["Rain"].values * signal["r_pr"][month_idx], 0.0)

    out = df.copy()
    out["T1"]=T1; out["P1"]=P1; out["RH1"]=RH1; out["Td1"]=Td1; out["V1"]=V1
    out["Ntotal1"]=Ntotal1; out["Nopaque1"]=Nopaque1
    out["GHI1"]=GHI1; out["DHI1"]=DHI1; out["DNI1"]=DNI1; out["Rain1"]=Rain1
    out["IRH1"]=IRH1
    out.attrs["btws_diagnostics"] = btws_diag
    out.attrs["rlds_mode"] = rlds_mode
    out.attrs["shortwave_partition_mode"] = shortwave_partition_mode
    return out

# ---------------------------------------------------------------------------
# 5. 验收 + 验证（目标Δ vs 实际达成Δ）
# ---------------------------------------------------------------------------
def run_acceptance(out, base, tag=""):
    checks = []
    def check(name, cond):
        checks.append((name, bool(np.all(cond))))

    check("8760行", len(out)==8760)
    for col in ["T1","P1","RH1","Td1","V1","Ntotal1","Nopaque1","GHI1","DHI1","DNI1","Rain1","IRH1"]:
        check(f"{col} 无NaN/Inf", np.all(np.isfinite(out[col].values)))
    check("RH 1-100%", (out["RH1"]>=1).all() and (out["RH1"]<=100).all())
    check("露点<=干球(+1e-6)", (out["Td1"] <= out["T1"]+1e-6).all())
    check("气压 70000-110000 Pa", (out["P1"]>=70000).all() and (out["P1"]<=110000).all())
    check("风速 0-75 m/s", (out["V1"]>=0).all() and (out["V1"]<=75).all())
    check("云量 0-10", (out["Ntotal1"]>=0).all() and (out["Ntotal1"]<=10).all())
    check("DHI<=GHI", (out["DHI1"] <= out["GHI1"]+1e-6).all())
    closure_err = np.abs(out["GHI1"] - out["DHI1"] - out["DNI1"]*np.sin(np.radians(np.clip(out["elev"],0,90))))
    check(f"辐射闭合<=1.1 W/m2 (max={closure_err.max():.3f})", closure_err.max()<=1.1)
    check("IRH 100-600 W/m2 合理范围", (out["IRH1"]>=100).all() and (out["IRH1"]<=600).all())
    check("降水非负", (out["Rain1"]>=0).all())
    check("湿小时集合不变", ((base["Rain"]>0) == (out["Rain1"]>0)).all())

    print(f"\n==== 验收结果 [{tag}] ====")
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

def validation_report(out, base, signal):
    """目标Δ/R vs 实际达成的Δ/R —— 就是之前建议加的那张1:1图背后的数字版"""
    print("\n==== 验证：目标 vs 实际达成（按月，逐项列出最大偏差）====")
    month_idx = out["month"].values - 1

    for name, target, col_before, col_after, kind in [
        ("Δtas (月均温)",    signal["d_tas"],    "T",  "T1",  "mean_diff"),
        ("Δtasmax (月均日最高)", signal["d_tasmax"], "T", "T1", "max_diff"),
        ("Δtasmin (月均日最低)", signal["d_tasmin"], "T", "T1", "min_diff"),
    ]:
        achieved = np.zeros(12)
        for m in range(12):
            mask = (month_idx == m)
            days = out.loc[mask, "day"].values
            df_m = pd.DataFrame({"day": days, "before": out.loc[mask, col_before].values,
                                  "after": out.loc[mask, col_after].values})
            daily = df_m.groupby("day").agg(before_stat=("before", "mean" if "mean" in kind else ("max" if "max" in kind else "min")),
                                             after_stat=("after", "mean" if "mean" in kind else ("max" if "max" in kind else "min")))
            achieved[m] = (daily["after_stat"] - daily["before_stat"]).mean()
        err = np.abs(achieved - target)
        print(f"  {name}: 目标范围[{target.min():.2f},{target.max():.2f}]  "
              f"最大偏差={err.max():.4f}°C  平均偏差={err.mean():.4f}°C")

    # 气压：CMIP6 psl月异常（Pa）是否被精确实现
    d_psl_pa = np.asarray(signal.get("d_psl_pa", signal.get("d_psl")), dtype=float)
    p_before_m = out.groupby("month")["P"].mean().values
    p_after_m = out.groupby("month")["P1"].mean().values
    p_err = np.abs((p_after_m - p_before_m) - d_psl_pa)
    print(f"  Δpsl→station pressure: 最大偏差={p_err.max():.6f} Pa")

    # 短波辐射：月均相对变化
    ghi_before_m = out.groupby("month")["GHI"].mean().values
    ghi_after_m  = out.groupby("month")["GHI1"].mean().values
    target_rel = signal["d_rsds"] / np.clip(ghi_before_m, 1e-6, None)
    achieved_rel = (ghi_after_m - ghi_before_m) / np.clip(ghi_before_m, 1e-6, None)
    print(f"  ΔGHI (相对): 目标最大偏差={np.abs(achieved_rel-target_rel).max():.4f}  "
          f"（目标范围[{target_rel.min():.3f},{target_rel.max():.3f}]）")

    irh_before_m = out.groupby("month")["IRH"].mean().values
    irh_after_m  = out.groupby("month")["IRH1"].mean().values
    achieved_irh = irh_after_m - irh_before_m
    if signal.get("d_rlds", None) is not None:
        target_irh = np.asarray(signal["d_rlds"], dtype=float)
        err_irh = np.abs(achieved_irh - target_irh)
        print(f"  ΔIRH (绝对, W/m2): 最大偏差={err_irh.max():.4f}  "
              f"实际达成范围=[{achieved_irh.min():.2f},{achieved_irh.max():.2f}]")
    else:
        print("  ΔIRH: 未提供CMIP6 rlds，使用Clark&Allen+Walton后备重算（无目标Δ可比较）")

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    base = synth_base_tmyx(seed=42)

    print("==== Identity test (signal=0, 应精确复现基础TMYx) ====")
    out0 = morph(base, zero_signal())
    for col, base_col in [("T1","T"), ("RH1","RH"), ("GHI1","GHI"), ("IRH1","IRH"), ("Rain1","Rain")]:
        diff = np.abs(out0[col]-base[base_col]).max()
        print(f"  max|Δ{col}| = {diff:.6f}")
    run_acceptance(out0, base, tag="identity")

    print("\n\n==== 施加合成气候信号（含新增rlds） ====")
    sig = synth_climate_signal()
    out1 = morph(base, sig)
    run_acceptance(out1, base, tag="synthetic signal (BTWS+BWS+rlds)")
    validation_report(out1, base, sig)
    print(f"  BTWS fallback diagnostics: {out1.attrs.get('btws_diagnostics', {})}")
    print(f"  rlds mode: {out1.attrs.get('rlds_mode')}")

    # 明确测试 rlds 缺失分支，防止后备逻辑因条件判断错误而永远不可达。
    sig_no_rlds = dict(sig)
    sig_no_rlds["d_rlds"] = None
    out_fallback = morph(base, sig_no_rlds)
    assert out_fallback.attrs.get("rlds_mode") == "clark_allen_walton_fallback"
    assert np.isfinite(out_fallback["IRH1"]).all()
    print("  rlds missing-signal fallback test: PASS")

    print("\n==== 摘要 ====")
    print(f"年均温: {base['T'].mean():.2f}C -> {out1['T1'].mean():.2f}C")
    print(f"年均IRH: {base['IRH'].mean():.1f} W/m2 -> {out1['IRH1'].mean():.1f} W/m2")
