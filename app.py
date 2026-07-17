from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

from calculator import (
    D7_RATIO_TO_Q,
    FormulaError,
    calculate_correction_addition,
    calculate_formula,
)

st.set_page_config(
    page_title="配方中控台",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@500;600;700;800&display=swap');
:root{
  --ink:#102a2b; --muted:#5e7374; --brand:#0b6b61; --brand2:#18a58e;
  --cream:#f7f4ed; --card:#ffffff; --line:#dce7e3; --amber:#d58a16;
}
html,body,[class*="css"]{font-family:'Noto Sans TC',sans-serif}
.stApp{background:
  radial-gradient(circle at 5% 0%,rgba(24,165,142,.12),transparent 28%),
  radial-gradient(circle at 100% 12%,rgba(213,138,22,.10),transparent 24%),
  var(--cream);
}
.block-container{max-width:1120px;padding-top:1.4rem;padding-bottom:4rem}
h1{font-size:clamp(2rem,5vw,3.35rem)!important;font-weight:800!important;letter-spacing:-.04em!important}
h2{font-size:clamp(1.5rem,3.5vw,2.05rem)!important;font-weight:800!important}
h3{font-size:clamp(1.18rem,3vw,1.48rem)!important;font-weight:700!important}
p,label,.stMarkdown,.stCaption{font-size:1.04rem}
.hero{background:linear-gradient(135deg,#123f3b,#0b6b61 58%,#159a85);color:white;
  padding:2rem;border-radius:28px;box-shadow:0 18px 45px rgba(13,70,63,.18);margin-bottom:1.25rem}
.hero h1{margin:0!important;color:white!important}
.hero p{font-size:1.14rem;margin:.65rem 0 0;opacity:.9;max-width:760px}
.badge{display:inline-block;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.25);
  padding:.4rem .75rem;border-radius:999px;margin:.8rem .35rem 0 0;font-weight:700}
.section-card{background:rgba(255,255,255,.86);border:1px solid var(--line);border-radius:22px;
  padding:1.15rem 1.2rem;margin:.75rem 0;box-shadow:0 8px 26px rgba(31,65,60,.06)}
.notice{background:#e7f6f2;border-left:6px solid var(--brand2);padding:1rem 1.1rem;border-radius:14px;
  font-size:1.04rem;margin:.75rem 0}
.warning{background:#fff3df;border-left:6px solid var(--amber);padding:1rem 1.1rem;border-radius:14px}
.danger{background:#fdebea;border-left:6px solid #c84b42;padding:1rem 1.1rem;border-radius:14px}
div[data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:18px;padding:1rem;
  box-shadow:0 8px 22px rgba(31,65,60,.055)}
div[data-testid="stMetricLabel"]{font-size:1rem}
div[data-testid="stMetricValue"]{font-size:clamp(1.45rem,4vw,2.1rem);font-weight:800;color:var(--brand)}
input,select,textarea{font-size:18px!important}
div[data-baseweb="input"]{border-radius:12px}
.stButton button,.stDownloadButton button,.stFormSubmitButton button{min-height:52px;border-radius:14px;font-size:1.08rem;font-weight:800}
div[data-testid="stDataFrame"]{border-radius:16px;overflow:hidden}
.small{color:var(--muted);font-size:.92rem}
@media(max-width:700px){
 .block-container{padding:.8rem .75rem 3rem}
 .hero{padding:1.35rem;border-radius:21px}
 p,label,.stMarkdown,.stCaption{font-size:1rem}
}
</style>
""", unsafe_allow_html=True)

st.session_state.setdefault("history", [])
st.session_state.setdefault("last_result", None)
st.session_state.setdefault("last_correction", None)

st.markdown("""
<div class="hero">
  <h1>◈ 配方中控台</h1>
  <p>母液濃度彈性設定、G 後添加、額外添加劑與品管補加，一個畫面完成現場配方換算。</p>
  <span class="badge">用量顯示 2 位小數</span>
  <span class="badge">D7 = Q × 0.003</span>
  <span class="badge">手機友善</span>
</div>
""", unsafe_allow_html=True)

tab_formula, tab_qc, tab_history, tab_rules = st.tabs(
    ["配方設計", "品管補加", "紀錄", "規則"]
)

with tab_formula:
    st.markdown("## 配方設計")
    with st.form("formula_form"):
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        top = st.columns(2)
        target_total = top[0].number_input(
            "最終目標總量", min_value=0.01, value=100.0, step=1.0, format="%.2f"
        )
        unit = top[1].selectbox("單位", ["kg", "g", "L", "噸"])
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### 母液設定")
        defaults = [
            ("V", "V", 20.0, 40.0),
            ("Q", "Q", 20.0, 60.0),
            ("SE", "SE", 20.0, 40.0),
            ("M4", "額外母液", 0.0, 40.0),
        ]
        active, concentrations = {}, {}
        for key, label, p, c in defaults:
            cols = st.columns([1, 1])
            active[key] = cols[0].number_input(
                f"{label} 有效比例 (%)", 0.0, 100.0, p, .1, format="%.2f"
            )
            concentrations[key] = cols[1].number_input(
                f"{label} 母液濃度 (%)", .01, 100.0, c, .1, format="%.2f"
            )

        st.markdown("### 後添加")
        post = st.columns(2)
        g_percent = post[0].number_input(
            "G 後添加比例 (%)", 0.0, 100.0, 6.0, .1, format="%.2f"
        )
        additive_percent = post[1].number_input(
            "額外添加劑占最終總量 (%)", 0.0, 99.99, 0.0, .1, format="%.2f",
            help="例如 2%，用量就是最終目標總量的 2%。"
        )
        st.markdown(
            '<div class="notice"><b>計算順序：</b>先保留額外添加劑的最終占比，再將剩餘量除以 '
            '<b>(1 + G比例)</b>，得到母液與水的配製基準。</div>',
            unsafe_allow_html=True,
        )
        submitted = st.form_submit_button("開始計算", type="primary", use_container_width=True)

    if submitted:
        try:
            result = calculate_formula(
                target_final_total=target_total,
                active_percentages=active,
                concentrations=concentrations,
                g_percent=g_percent,
                additive_percent_of_final=additive_percent,
                unit=unit,
            )
        except FormulaError as exc:
            st.error(str(exc))
        else:
            st.session_state.last_result = result
            st.session_state.history.insert(0, {
                "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "最終目標量": round(result.target_final_total, 2),
                "單位": result.unit,
                "V": round(result.mother_liquor_amounts["V"], 2),
                "Q": round(result.mother_liquor_amounts["Q"], 2),
                "SE": round(result.mother_liquor_amounts["SE"], 2),
                "額外母液": round(result.mother_liquor_amounts["M4"], 2),
                "水": round(result.water_amount, 2),
                "G": round(result.g_amount, 2),
                "額外添加劑": round(result.additive_amount, 2),
                "D7": round(result.d7_amount, 2),
            })
            st.session_state.history = st.session_state.history[:50]

    result = st.session_state.last_result
    if result:
        if result.has_negative_water:
            st.markdown(
                f'<div class="danger"><b>水量為負值：{result.water_amount:.2f} {result.unit}</b><br>'
                '母液換算總量超過目前可用的母液＋水基準，請調整有效比例或母液濃度。</div>',
                unsafe_allow_html=True
            )

        m = st.columns(4)
        m[0].metric("母液＋水基準", f"{result.pre_g_base_total:.2f} {result.unit}")
        m[1].metric("G", f"{result.g_amount:.2f} {result.unit}")
        m[2].metric("額外添加劑", f"{result.additive_amount:.2f} {result.unit}")
        m[3].metric("D7", f"{result.d7_amount:.2f} {result.unit}")

        st.markdown("### 投料表")
        df = pd.DataFrame(result.rows())
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "下載投料表 CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"formula_{datetime.now():%Y%m%d_%H%M%S}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tab_qc:
    st.markdown("## 品管補加計算")
    st.markdown(
        '<div class="notice">適用情境：大體積配製完成後，實測某一成分濃度不足，'
        '計算要補加多少 V、Q、SE、額外母液或 G 才能達標。補加後總量會增加。</div>',
        unsafe_allow_html=True,
    )

    with st.form("qc_form"):
        q1, q2 = st.columns(2)
        material = q1.selectbox("要補加的材料", ["V", "Q", "SE", "額外母液", "G"])
        batch_amount = q2.number_input(
            "目前批次總量", min_value=.01, value=1000.0, step=10.0, format="%.2f"
        )
        q3, q4, q5 = st.columns(3)
        current_percent = q3.number_input(
            "目前實測濃度 (%)", 0.0, 100.0, 5.0, .01, format="%.2f"
        )
        target_percent = q4.number_input(
            "品管目標濃度 (%)", 0.0, 100.0, 6.0, .01, format="%.2f"
        )
        default_stock = 100.0 if material == "G" else 40.0
        stock_percent = q5.number_input(
            "補加原料濃度 (%)", .01, 100.0, default_stock, .1, format="%.2f"
        )
        qc_unit = st.selectbox("補加計算單位", ["kg", "g", "L", "噸"])
        qc_submit = st.form_submit_button("計算應補加量", type="primary", use_container_width=True)

    if qc_submit:
        try:
            correction = calculate_correction_addition(
                batch_amount=batch_amount,
                current_percent=current_percent,
                target_percent=target_percent,
                correction_material_percent=stock_percent,
                unit=qc_unit,
            )
        except FormulaError as exc:
            st.error(str(exc))
        else:
            st.session_state.last_correction = (material, correction)

    correction_data = st.session_state.last_correction
    if correction_data:
        material_name, correction = correction_data
        st.markdown(
            f'<div class="section-card"><div class="small">建議補加</div>'
            f'<div style="font-size:2.35rem;font-weight:800;color:#0b6b61">'
            f'{correction.add_amount:.2f} {correction.unit}</div>'
            f'<div style="font-size:1.08rem;margin-top:.35rem">材料：<b>{material_name}</b>｜'
            f'補加後總量：<b>{correction.final_amount:.2f} {correction.unit}</b>｜'
            f'驗算濃度：<b>{correction.final_percent:.2f}%</b></div></div>',
            unsafe_allow_html=True,
        )
        st.caption("公式已將補加後總量增加造成的稀釋效果納入計算。")

with tab_history:
    st.markdown("## 計算紀錄")
    if st.session_state.history:
        hdf = pd.DataFrame(st.session_state.history)
        st.dataframe(hdf, use_container_width=True, hide_index=True)
        st.download_button(
            "下載紀錄 CSV",
            hdf.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"history_{datetime.now():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("尚無配方紀錄。")
    if st.button("清除紀錄", use_container_width=True):
        st.session_state.history = []
        st.session_state.last_result = None
        st.session_state.last_correction = None
        st.rerun()

with tab_rules:
    st.markdown("""
    ## 計算規則

    **額外添加劑**

    `添加劑量 = 最終目標總量 × 添加劑占比`

    **G 後添加與配製基準**

    `母液＋水基準 = (最終目標總量 − 額外添加劑量) ÷ (1 + G比例)`

    **母液**

    `母液用量 = 母液＋水基準 × 有效比例 ÷ 母液濃度`

    **水**

    `水量 = 母液＋水基準 − V − Q − SE − 額外母液`

    **D7**

    `D7 = Q 用量 × 0.003`

    **品管補加**

    補加後總量會增加，因此採質量平衡計算：

    `補加量 = 批次量 × (目標濃度 − 實測濃度) ÷ (補加原料濃度 − 目標濃度)`
    """)

st.markdown(
    '<p class="small">配方中控台｜不含成本｜不含圓餅圖｜所有用量顯示至小數點後 2 位</p>',
    unsafe_allow_html=True,
)
