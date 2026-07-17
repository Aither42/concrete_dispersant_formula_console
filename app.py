from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Paragraph,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from calculator import (
    D7_RATIO_TO_Q,
    FormulaError,
    calculate_correction_addition,
    calculate_formula,
)


def build_formula_text(result) -> str:
    """建立可直接複製到 LINE、Email 或工作群組的配方文字。"""
    items = [
        ("V", result.mother_liquor_amounts["V"]),
        ("Q", result.mother_liquor_amounts["Q"]),
        ("SE", result.mother_liquor_amounts["SE"]),
        ("額外母液", result.mother_liquor_amounts["M4"]),
        ("水", result.water_amount),
        ("G（後添加）", result.g_amount),
        ("額外添加劑", result.additive_amount),
        ("D7（最後添加）", result.d7_amount),
    ]
    lines = [
        "【配方投料結果】",
        f"最終目標量：{result.target_final_total:.2f} {result.unit}",
        "",
    ]
    lines.extend(
        f"{name}：{amount:.2f} {result.unit}"
        for name, amount in items
    )
    lines.extend(
        [
            "",
            f"主配方合計：{result.total_before_d7:.2f} {result.unit}",
            f"含 D7 總量：{result.total_with_d7:.2f} {result.unit}",
        ]
    )
    return "\n".join(lines)


def build_formula_pdf(result, operator: str = "") -> bytes:
    """產生可下載的中文配方單 PDF。"""
    buffer = BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
        title="配方計算結果",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#0B6B61"),
        alignment=1,
        spaceAfter=16,
    )
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=11,
        leading=16,
        textColor=colors.HexColor("#24393A"),
    )

    story = [
        Paragraph("配方計算結果", title_style),
        Paragraph(
            f"日期：{datetime.now():%Y-%m-%d %H:%M}"
            + (f"　操作員：{operator}" if operator.strip() else ""),
            body_style,
        ),
        Paragraph(
            f"最終目標量：{result.target_final_total:.2f} {result.unit}",
            body_style,
        ),
        Spacer(1, 14),
    ]

    rows = [
        ["材料", "添加階段", f"用量 ({result.unit})"],
        ["V", "母液", f"{result.mother_liquor_amounts['V']:.2f}"],
        ["Q", "母液", f"{result.mother_liquor_amounts['Q']:.2f}"],
        ["SE", "母液", f"{result.mother_liquor_amounts['SE']:.2f}"],
        ["額外母液", "母液", f"{result.mother_liquor_amounts['M4']:.2f}"],
        ["水", "母液配製", f"{result.water_amount:.2f}"],
        ["G", "後添加", f"{result.g_amount:.2f}"],
        ["額外添加劑", "後添加", f"{result.additive_amount:.2f}"],
        ["D7", "最後添加", f"{result.d7_amount:.2f}"],
    ]

    table = Table(rows, colWidths=[150, 150, 160], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("FONTSIZE", (0, 1), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B6B61")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F5FAF8")),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#BFD7D1")),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            f"主配方合計：{result.total_before_d7:.2f} {result.unit}　"
            f"含 D7 總量：{result.total_with_d7:.2f} {result.unit}",
            body_style,
        )
    )
    document.build(story)
    return buffer.getvalue()


def render_result_row(
    name: str,
    amount: float,
    unit: str,
    stage: str,
    row_class: str = "",
) -> str:
    return f"""
    <div class="formula-row {row_class}">
      <div class="formula-left">
        <span class="formula-name">{name}</span>
        <span class="formula-stage">{stage}</span>
      </div>
      <div class="formula-amount">{amount:.2f}<span class="formula-unit"> {unit}</span></div>
    </div>
    """



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

.ingredient-title{
  font-size:1.3rem;
  font-weight:800;
  color:var(--ink);
  margin:1.1rem 0 .25rem;
  padding:.58rem .85rem;
  border-radius:13px;
  background:linear-gradient(90deg,rgba(24,165,142,.16),transparent);
}
.ingredient-divider{
  height:1px;
  background:linear-gradient(90deg,var(--line),transparent);
  margin:.35rem 0 .9rem;
}
div[data-testid="stSlider"]{
  padding:.15rem .1rem .4rem;
}
div[data-testid="stSlider"] label{
  font-size:1.06rem!important;
  font-weight:700!important;
}
div[data-testid="stSlider"] [role="slider"]{
  width:23px!important;
  height:23px!important;
}



.result-shell{
  background:linear-gradient(145deg,#0f3533,#0a5d55);
  border-radius:24px;
  padding:1.3rem;
  margin:1.1rem 0;
  box-shadow:0 18px 42px rgba(8,65,59,.18);
}
.result-heading{
  color:white;
  font-size:clamp(1.55rem,4vw,2.15rem);
  font-weight:800;
  margin:0 0 .25rem;
}
.result-subtitle{
  color:rgba(255,255,255,.76);
  font-size:1rem;
  margin-bottom:1rem;
}
.formula-list{
  background:rgba(255,255,255,.98);
  border-radius:18px;
  overflow:hidden;
  border:1px solid rgba(255,255,255,.5);
}
.formula-row{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:1rem;
  min-height:74px;
  padding:.8rem 1.1rem;
  border-bottom:1px solid #dfe9e6;
}
.formula-row:last-child{border-bottom:none}
.formula-row.post{background:#fffaf0}
.formula-row.final{background:#fff5f8}
.formula-row.water-negative{
  background:#ffe9e7;
  border-left:6px solid #c8463d;
}
.formula-left{
  display:flex;
  align-items:center;
  gap:.65rem;
  min-width:0;
  text-align:left;
}
.formula-name{
  color:#163638;
  font-size:clamp(1.18rem,3vw,1.48rem);
  font-weight:800;
  text-align:left;
}
.formula-stage{
  color:#527071;
  background:#e7f2ef;
  border-radius:999px;
  padding:.22rem .55rem;
  font-size:.77rem;
  font-weight:800;
  white-space:nowrap;
}
.formula-row.post .formula-stage{background:#f6e6bd;color:#7e5814}
.formula-row.final .formula-stage{background:#f2dce3;color:#81394d}
.formula-row.water-negative .formula-stage{background:#f4c6c1;color:#8d2c26}
.formula-amount{
  margin-left:auto;
  text-align:right;
  white-space:nowrap;
  color:#08675d;
  font-size:clamp(1.75rem,5vw,2.55rem);
  line-height:1;
  font-weight:800;
  letter-spacing:-.035em;
  font-variant-numeric:tabular-nums;
}
.formula-row.water-negative .formula-amount{color:#b4322b}
.formula-unit{
  font-size:clamp(.98rem,2.5vw,1.2rem);
  letter-spacing:0;
  color:#587172;
}
.result-total{
  display:flex;
  justify-content:space-between;
  flex-wrap:wrap;
  gap:.75rem;
  color:white;
  margin-top:1rem;
  padding:.85rem 1rem;
  border-radius:15px;
  background:rgba(255,255,255,.11);
  font-size:1.04rem;
  font-weight:700;
}
.copy-area textarea{
  font-family:'Noto Sans TC',sans-serif!important;
  font-size:1.05rem!important;
  line-height:1.65!important;
}
@media(max-width:700px){
 .block-container{padding:.8rem .75rem 3rem}
 .hero{padding:1.35rem;border-radius:21px}
 .result-shell{padding:.85rem;border-radius:20px}
 .formula-row{min-height:68px;padding:.75rem .85rem}
 .formula-left{gap:.45rem}
 .formula-stage{font-size:.7rem}
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
        st.markdown(
            '<div class="notice"><b>直接輸入：</b>請分別輸入每種母液的有效比例與母液濃度，'
            '數值可精確至小數點後 2 位。</div>',
            unsafe_allow_html=True,
        )

        defaults = [
            ("V", "V", 20.0, 40.0),
            ("Q", "Q", 20.0, 60.0),
            ("SE", "SE", 20.0, 40.0),
            ("M4", "額外母液", 0.0, 40.0),
        ]
        active, concentrations = {}, {}

        for key, label, default_ratio, default_concentration in defaults:
            st.markdown(
                f'<div class="ingredient-title">{label}</div>',
                unsafe_allow_html=True,
            )
            cols = st.columns(2)
            active[key] = cols[0].number_input(
                f"{label} 有效比例 (%)",
                min_value=0.0,
                max_value=100.0,
                value=default_ratio,
                step=0.1,
                format="%.2f",
                key=f"{key}_ratio_input",
            )
            concentrations[key] = cols[1].number_input(
                f"{label} 母液濃度 (%)",
                min_value=0.1,
                max_value=100.0,
                value=default_concentration,
                step=0.1,
                format="%.2f",
                key=f"{key}_concentration_input",
            )
            st.markdown(
                '<div class="ingredient-divider"></div>',
                unsafe_allow_html=True,
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

        rows = [
            render_result_row(
                "V", result.mother_liquor_amounts["V"], result.unit, "母液"
            ),
            render_result_row(
                "Q", result.mother_liquor_amounts["Q"], result.unit, "母液"
            ),
            render_result_row(
                "SE", result.mother_liquor_amounts["SE"], result.unit, "母液"
            ),
            render_result_row(
                "額外母液",
                result.mother_liquor_amounts["M4"],
                result.unit,
                "母液",
            ),
            render_result_row(
                "水",
                result.water_amount,
                result.unit,
                "補水" if not result.has_negative_water else "水量不足",
                "water-negative" if result.has_negative_water else "",
            ),
            render_result_row(
                "G", result.g_amount, result.unit, "後添加", "post"
            ),
            render_result_row(
                "額外添加劑",
                result.additive_amount,
                result.unit,
                "後添加",
                "post",
            ),
            render_result_row(
                "D7", result.d7_amount, result.unit, "最後添加", "final"
            ),
        ]

        st.markdown(
            f"""
            <div class="result-shell">
              <div class="result-heading">最終投料結果</div>
              <div class="result-subtitle">
                配方成分靠左，用量與單位靠右
              </div>
              <div class="formula-list">
                {''.join(rows)}
              </div>
              <div class="result-total">
                <span>主配方合計：{result.total_before_d7:.2f} {result.unit}</span>
                <span>含 D7 總量：{result.total_with_d7:.2f} {result.unit}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        formula_text = build_formula_text(result)
        st.markdown("### 複製與下載")
        st.markdown('<div class="copy-area">', unsafe_allow_html=True)
        st.text_area(
            "配方文字",
            formula_text,
            height=285,
            help="點入文字框後可全選並複製到 LINE、Email 或工作群組。",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        operator = st.text_input(
            "PDF 配方單操作員（選填）",
            placeholder="例如：王小明",
        )
        df = pd.DataFrame(result.rows())

        download_cols = st.columns(3)
        download_cols[0].download_button(
            "下載 CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"formula_{datetime.now():%Y%m%d_%H%M%S}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        download_cols[1].download_button(
            "下載文字配方",
            formula_text.encode("utf-8"),
            file_name=f"formula_{datetime.now():%Y%m%d_%H%M%S}.txt",
            mime="text/plain",
            use_container_width=True,
        )
        download_cols[2].download_button(
            "下載 PDF 配方單",
            build_formula_pdf(result, operator),
            file_name=f"formula_{datetime.now():%Y%m%d_%H%M%S}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        with st.expander("查看詳細計算表"):
            st.dataframe(df, use_container_width=True, hide_index=True)

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
