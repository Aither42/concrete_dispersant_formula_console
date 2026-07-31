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
    SPECIFIC_GRAVITIES,
    FormulaError,
    calculate_correction_addition,
    calculate_formula,
    calculate_reverse_formula,
    resolve_vq_effective_percentages,
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
    specific_gravity_text = (
        f"{result.estimated_specific_gravity:.3f}"
        if result.estimated_specific_gravity is not None
        else "無法估算"
    )
    lines = [
        f"【{result.formula_name}】",
        f"最終目標量：{result.target_final_total:.2f} {result.unit}",
        f"配方固成分：{result.solid_content_percent:.2f}%",
        f"估算比重：{specific_gravity_text}",
        (
            "比重估算涵蓋率："
            f"{result.specific_gravity_coverage_percent:.2f}%"
        ),
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


def build_formula_pdf(result) -> bytes:
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
        title=result.formula_name,
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
        Paragraph(result.formula_name, title_style),
        Paragraph(
            f"日期：{datetime.now():%Y-%m-%d %H:%M}",
            body_style,
        ),
        Paragraph(
            f"最終目標量：{result.target_final_total:.2f} {result.unit}",
            body_style,
        ),
        Paragraph(
            f"配方固成分：{result.solid_content_percent:.2f}%",
            body_style,
        ),
        Paragraph(
            (
                "估算比重："
                + (
                    f"{result.estimated_specific_gravity:.3f}"
                    if result.estimated_specific_gravity is not None
                    else "無法估算"
                )
                + "　涵蓋率："
                + f"{result.specific_gravity_coverage_percent:.2f}%"
            ),
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
    story.extend(
        [
            Paragraph(
                f"主配方合計：{result.total_before_d7:.2f} {result.unit}　"
                f"含 D7 總量：{result.total_with_d7:.2f} {result.unit}",
                body_style,
            ),
            Spacer(1, 8),
            Paragraph(
                "比重估算未納入額外母液、額外添加劑與 D7；"
                "D7 亦未納入配方固成分。",
                body_style,
            ),
        ]
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


def render_reverse_row(
    label: str,
    exact_percent: float,
    naming_value: int,
) -> str:
    return f"""
    <div class="reverse-row">
      <div class="reverse-label">{label}</div>
      <div class="reverse-values">
        <span class="reverse-exact">{exact_percent:.4f}%</span>
        <span class="reverse-arrow">→</span>
        <span class="reverse-rounded">{naming_value}</span>
      </div>
    </div>
    """


def build_reverse_text(result) -> str:
    return "\n".join(
        [
            "【反推配方結果】",
            f"配方名稱：{result.formula_name}",
            f"母液＋水基準：{result.base_total:.2f} {result.unit}",
            f"含 G 總量：{result.total_with_g:.2f} {result.unit}",
            "",
            (
                "V 輸入："
                f"{result.input_percentages['V']:.4f}%"
                f" → {result.rounded_percentages['V']}"
            ),
            (
                "Q 輸入："
                f"{result.input_percentages['Q']:.4f}%"
                f" → {result.rounded_percentages['Q']}"
            ),
            (
                "V＋Q 輸入："
                f"{result.a_percent:.4f}%"
                f" → {result.rounded_percentages['A']}"
            ),
            (
                "SE 輸入："
                f"{result.input_percentages['SE']:.4f}%"
                f" → {result.rounded_percentages['SE']}"
            ),
            (
                "G 輸入："
                f"{result.input_percentages['G']:.4f}%"
                f" → {result.rounded_percentages['G']}"
            ),
            "",
            "命名採四捨五入（0.5 進位）。",
        ]
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




.quick-code-preview{
  background:linear-gradient(145deg,#123f3b,#0b6b61);
  color:white;border-radius:16px;padding:.85rem 1rem;
  text-align:center;margin:.65rem 0 1rem;
  font-size:clamp(1.8rem,6vw,2.8rem);font-weight:800;
}
.property-panel{
  display:grid;
  grid-template-columns:minmax(0,1.5fr) repeat(2,minmax(0,1fr));
  gap:.8rem;
  margin:1rem 0;
}
.property-item{
  background:white;
  border:1px solid var(--line);
  border-radius:17px;
  padding:.95rem 1rem;
  box-shadow:0 7px 20px rgba(31,65,60,.055);
}
.property-label{
  color:var(--muted);
  font-size:.9rem;
  font-weight:700;
  margin-bottom:.3rem;
}
.property-value{
  color:var(--brand);
  font-size:clamp(1.4rem,4vw,2rem);
  font-weight:800;
  line-height:1.2;
  overflow-wrap:anywhere;
}
.property-note{
  color:var(--muted);
  font-size:.82rem;
  margin-top:.25rem;
}


.reverse-name-card{
  background:linear-gradient(145deg,#123f3b,#0b6b61);
  border-radius:24px;
  padding:1.35rem;
  margin:1rem 0;
  color:white;
  box-shadow:0 18px 42px rgba(8,65,59,.18);
  text-align:center;
}
.reverse-name-label{
  font-size:1rem;
  font-weight:700;
  opacity:.8;
}
.reverse-name-value{
  font-size:clamp(2.35rem,8vw,4.25rem);
  line-height:1.12;
  font-weight:800;
  letter-spacing:-.045em;
  margin-top:.35rem;
}
.reverse-name-note{
  font-size:.9rem;
  opacity:.78;
  margin-top:.5rem;
}
.reverse-list{
  background:white;
  border:1px solid var(--line);
  border-radius:18px;
  overflow:hidden;
  margin:.9rem 0;
}
.reverse-row{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:1rem;
  min-height:68px;
  padding:.75rem 1rem;
  border-bottom:1px solid var(--line);
}
.reverse-row:last-child{border-bottom:none}
.reverse-label{
  font-size:1.12rem;
  font-weight:800;
  color:var(--ink);
  text-align:left;
}
.reverse-values{
  margin-left:auto;
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap:.7rem;
  white-space:nowrap;
  text-align:right;
}
.reverse-exact{
  color:var(--muted);
  font-size:1.05rem;
  font-variant-numeric:tabular-nums;
}
.reverse-arrow{
  color:#8aa09f;
  font-size:1.15rem;
}
.reverse-rounded{
  min-width:42px;
  color:var(--brand);
  font-size:1.75rem;
  font-weight:800;
  text-align:right;
  font-variant-numeric:tabular-nums;
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
 .property-panel{grid-template-columns:1fr}
 .reverse-row{padding:.7rem .8rem;min-height:62px}
 .reverse-values{gap:.45rem}
 .reverse-exact{font-size:.92rem}
 .reverse-rounded{font-size:1.5rem;min-width:34px}
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
st.session_state.setdefault("last_reverse", None)

st.markdown("""
<div class="hero">
  <h1>◈ 配方中控台</h1>
  <p>母液濃度彈性設定、G 後添加、額外添加劑與品管補加，一個畫面完成現場配方換算。</p>
  <span class="badge">用量顯示 2 位小數</span>
  <span class="badge">D7 = Q × 0.003</span>
  <span class="badge">手機友善</span>
</div>
""", unsafe_allow_html=True)

tab_formula, tab_reverse, tab_qc, tab_history, tab_rules = st.tabs(
    ["配方設計", "反推配方", "品管補加", "紀錄", "規則"]
)

with tab_formula:
    st.markdown("## 配方設計")
    with st.form("formula_form"):
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### 配方代碼快速輸入")
        st.caption(
            "前三個欄位依序為 V＋Q、SE、G；V、Q 欄位代表分配權重。"
            "例如 389(V8Q1) 會把 V＋Q 的 3% 按 8:1 分配。"
        )
        code_cols = st.columns(3)
        code_vq_total = code_cols[0].number_input(
            "V＋Q", 0, 99, 9, 1, key="formula_code_vq_total"
        )
        code_se = code_cols[1].number_input(
            "SE", 0, 99, 4, 1, key="formula_code_se"
        )
        code_g = code_cols[2].number_input(
            "G", 0, 99, 6, 1, key="formula_code_g"
        )
        vq_cols = st.columns(2)
        code_v = vq_cols[0].number_input(
            "V 設定", 0, 99, 8, 1, key="formula_code_v"
        )
        code_q = vq_cols[1].number_input(
            "Q 設定", 0, 99, 1, 1, key="formula_code_q"
        )

        effective_v, effective_q, vq_ratio_scaled = (
            resolve_vq_effective_percentages(
                code_vq_total,
                code_v,
                code_q,
            )
        )
        entered_vq_total = float(code_v) + float(code_q)

        formula_name = (
            f"{int(code_vq_total)}{int(code_se)}{int(code_g)}"
            f"(V{int(code_v)}Q{int(code_q)})"
        )
        st.markdown(
            f'<div class="quick-code-preview">{formula_name}</div>',
            unsafe_allow_html=True,
        )

        if entered_vq_total == 0 and float(code_vq_total) > 0:
            st.warning(
                "V＋Q 大於 0，但 V、Q 權重都是 0，無法分配。"
            )
        elif entered_vq_total > 0:
            st.info(
                f"V＋Q 的 {float(code_vq_total):.2f}% "
                f"按 V:Q = {int(code_v)}:{int(code_q)} 分配："
                f"V={effective_v:.4f}%、Q={effective_q:.4f}%。"
            )
        top = st.columns(2)
        target_total = top[0].number_input(
            "最終目標總量",
            min_value=0.01,
            value=100.0,
            step=1.0,
            format="%.2f",
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
            ("V", "V", float(effective_v), 40.0),
            ("Q", "Q", float(effective_q), 60.0),
            ("SE", "SE", float(code_se), 40.0),
            ("M4", "額外母液", 0.0, 40.0),
        ]
        active, concentrations = {}, {}

        code_signature = (round(effective_v, 8), round(effective_q, 8), int(code_se))
        previous_signature = st.session_state.get("formula_code_signature")
        for key, label, default_ratio, default_concentration in defaults:
            ratio_key = f"{key}_ratio_input"
            concentration_key = f"{key}_concentration_input"
            if previous_signature != code_signature and key in ("V", "Q", "SE"):
                st.session_state[ratio_key] = default_ratio
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
                key=ratio_key,
            )
            concentrations[key] = cols[1].number_input(
                f"{label} 固成分／母液濃度 (%)",
                min_value=0.1,
                max_value=100.0,
                value=default_concentration,
                step=0.1,
                format="%.2f",
                key=concentration_key,
            )
            st.markdown(
                '<div class="ingredient-divider"></div>',
                unsafe_allow_html=True,
            )

        st.session_state["formula_code_signature"] = code_signature

        st.markdown("### 後添加")
        post = st.columns(3)
        if st.session_state.get("formula_code_g_previous") != int(code_g):
            st.session_state["g_percent_input"] = float(code_g)
        st.session_state["formula_code_g_previous"] = int(code_g)
        g_percent = post[0].number_input(
            "G 後添加比例 (%)",
            0.0,
            100.0,
            float(code_g),
            .1,
            format="%.2f",
            help="由上方 G 欄位自動帶入，也可手動微調。",
            key="g_percent_input",
        )
        additive_percent = post[1].number_input(
            "額外添加劑占最終總量 (%)",
            0.0,
            99.99,
            0.0,
            .1,
            format="%.2f",
            help="例如 2%，用量就是最終目標總量的 2%。",
        )
        additive_solids = post[2].number_input(
            "額外添加劑固成分 (%)",
            0.0,
            100.0,
            100.0,
            .1,
            format="%.2f",
            help="預設 100%，可依實際產品規格調整。",
        )
        st.markdown(
            '<div class="notice"><b>計算順序：</b>先保留額外添加劑的最終占比，再將剩餘量除以 '
            '<b>(1 + G比例)</b>，得到母液與水的配製基準。</div>',
            unsafe_allow_html=True,
        )
        with st.expander("查看固成分與比重計算設定"):
            st.markdown(
                f"""
                **固成分**

                - V、Q、SE、額外母液：使用各自輸入的固成分／母液濃度
                - G（葡萄糖酸鈉）：100%
                - 額外添加劑：預設 100%，可調整
                - 水：0%
                - D7：不納入固成分

                **比重估算**

                - V：{SPECIFIC_GRAVITIES['V']:.3f}
                - Q：{SPECIFIC_GRAVITIES['Q']:.3f}
                - SE：{SPECIFIC_GRAVITIES['SE']:.3f}
                - G（葡萄糖酸鈉）：{SPECIFIC_GRAVITIES['G']:.3f}
                - 水：{SPECIFIC_GRAVITIES['WATER']:.3f}
                - 額外母液、額外添加劑、D7：暫不納入
                """
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
                additive_solids_percent=additive_solids,
                formula_name=formula_name,
                unit=unit,
            )
        except FormulaError as exc:
            st.error(str(exc))
        else:
            st.session_state.last_result = result
            st.session_state.history.insert(0, {
                "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "配方名稱": result.formula_name,
                "固成分 (%)": round(result.solid_content_percent, 2),
                "估算比重": (
                    round(result.estimated_specific_gravity, 3)
                    if result.estimated_specific_gravity is not None
                    else None
                ),
                "比重涵蓋率 (%)": round(
                    result.specific_gravity_coverage_percent, 2
                ),
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

        specific_gravity_text = (
            f"{result.estimated_specific_gravity:.3f}"
            if result.estimated_specific_gravity is not None
            else "無法估算"
        )
        st.markdown(
            f"""
            <div class="property-panel">
              <div class="property-item">
                <div class="property-label">配方名稱</div>
                <div class="property-value">{result.formula_name}</div>
              </div>
              <div class="property-item">
                <div class="property-label">配方固成分</div>
                <div class="property-value">{result.solid_content_percent:.2f}%</div>
                <div class="property-note">D7 不納入</div>
              </div>
              <div class="property-item">
                <div class="property-label">估算比重</div>
                <div class="property-value">{specific_gravity_text}</div>
                <div class="property-note">
                  涵蓋 {result.specific_gravity_coverage_percent:.2f}% 配方質量
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not result.has_complete_density_coverage:
            st.markdown(
                '<div class="warning"><b>比重為估算值：</b>'
                '額外母液與額外添加劑因尚無比重資料，暫未納入。'
                '畫面已顯示本次估算涵蓋率。</div>',
                unsafe_allow_html=True,
            )

        if unit == "L":
            st.markdown(
                '<div class="warning"><b>單位提醒：</b>'
                '固成分與比重公式以投料量視為重量為前提；'
                '使用 L 時請將結果視為暫估。</div>',
                unsafe_allow_html=True,
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
              <div class="result-heading">{result.formula_name}｜最終投料結果</div>
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

        df = pd.DataFrame(result.rows())
        df.insert(0, "配方名稱", result.formula_name)
        df["配方固成分 (%)"] = round(
            result.solid_content_percent, 2
        )
        df["估算比重"] = (
            round(result.estimated_specific_gravity, 3)
            if result.estimated_specific_gravity is not None
            else None
        )
        df["比重估算涵蓋率 (%)"] = round(
            result.specific_gravity_coverage_percent, 2
        )

        safe_formula_name = "".join(
            char
            for char in result.formula_name
            if char.isalnum() or char in ("-", "_")
        ) or "formula"
        download_cols = st.columns(3)
        download_cols[0].download_button(
            "下載 CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{safe_formula_name}_{datetime.now():%Y%m%d_%H%M%S}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        download_cols[1].download_button(
            "下載文字配方",
            formula_text.encode("utf-8"),
            file_name=f"{safe_formula_name}_{datetime.now():%Y%m%d_%H%M%S}.txt",
            mime="text/plain",
            use_container_width=True,
        )
        download_cols[2].download_button(
            "下載 PDF 配方單",
            build_formula_pdf(result),
            file_name=f"{safe_formula_name}_{datetime.now():%Y%m%d_%H%M%S}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        with st.expander("查看詳細計算表"):
            st.dataframe(df, use_container_width=True, hide_index=True)


with tab_reverse:
    st.markdown("## 反推配方")
    st.markdown(
        '<div class="notice"><b>使用方式：</b>'
        '輸入 V、Q、SE、G 與水的實際公斤數，系統會以母液＋水總量作為配製基準，'
        '反推出各成分的輸入比例與配方名稱。</div>',
        unsafe_allow_html=True,
    )

    with st.form("reverse_formula_form"):
        amount_cols_1 = st.columns(3)
        reverse_v = amount_cols_1[0].number_input(
            "V 用量 (kg)",
            min_value=0.0,
            value=20.0,
            step=0.01,
            format="%.2f",
            key="reverse_v_amount",
        )
        reverse_q = amount_cols_1[1].number_input(
            "Q 用量 (kg)",
            min_value=0.0,
            value=1.67,
            step=0.01,
            format="%.2f",
            key="reverse_q_amount",
        )
        reverse_se = amount_cols_1[2].number_input(
            "SE 用量 (kg)",
            min_value=0.0,
            value=12.5,
            step=0.01,
            format="%.2f",
            key="reverse_se_amount",
        )

        amount_cols_2 = st.columns(2)
        reverse_g = amount_cols_2[0].number_input(
            "G 用量 (kg)",
            min_value=0.0,
            value=6.0,
            step=0.01,
            format="%.2f",
            key="reverse_g_amount",
        )
        reverse_water = amount_cols_2[1].number_input(
            "水用量 (kg)",
            min_value=0.0,
            value=65.83,
            step=0.01,
            format="%.2f",
            key="reverse_water_amount",
        )

        with st.expander("母液濃度設定（通常不需修改）"):
            concentration_cols = st.columns(3)
            reverse_v_conc = concentration_cols[0].number_input(
                "V 母液濃度 (%)",
                min_value=0.01,
                max_value=100.0,
                value=40.0,
                step=0.1,
                format="%.2f",
                key="reverse_v_concentration",
            )
            reverse_q_conc = concentration_cols[1].number_input(
                "Q 母液濃度 (%)",
                min_value=0.01,
                max_value=100.0,
                value=60.0,
                step=0.1,
                format="%.2f",
                key="reverse_q_concentration",
            )
            reverse_se_conc = concentration_cols[2].number_input(
                "SE 母液濃度 (%)",
                min_value=0.01,
                max_value=100.0,
                value=40.0,
                step=0.1,
                format="%.2f",
                key="reverse_se_concentration",
            )

        reverse_submit = st.form_submit_button(
            "反推配方名稱",
            type="primary",
            use_container_width=True,
        )

    if reverse_submit:
        try:
            reverse_result = calculate_reverse_formula(
                v_amount=reverse_v,
                q_amount=reverse_q,
                se_amount=reverse_se,
                g_amount=reverse_g,
                water_amount=reverse_water,
                v_concentration=reverse_v_conc,
                q_concentration=reverse_q_conc,
                se_concentration=reverse_se_conc,
                unit="kg",
            )
        except FormulaError as exc:
            st.error(str(exc))
        else:
            st.session_state.last_reverse = reverse_result

    reverse_result = st.session_state.last_reverse
    if reverse_result:
        st.markdown(
            f"""
            <div class="reverse-name-card">
              <div class="reverse-name-label">反推配方名稱</div>
              <div class="reverse-name-value">{reverse_result.formula_name}</div>
              <div class="reverse-name-note">
                命名數字採四捨五入（0.5 進位）
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        metric_cols = st.columns(3)
        metric_cols[0].metric(
            "母液＋水基準",
            f"{reverse_result.base_total:.2f} kg",
        )
        metric_cols[1].metric(
            "含 G 總量",
            f"{reverse_result.total_with_g:.2f} kg",
        )
        metric_cols[2].metric(
            "最大取整差距",
            f"{reverse_result.max_rounding_difference:.4f}%",
        )

        reverse_rows = [
            render_reverse_row(
                "V 輸入%",
                reverse_result.input_percentages["V"],
                reverse_result.rounded_percentages["V"],
            ),
            render_reverse_row(
                "Q 輸入%",
                reverse_result.input_percentages["Q"],
                reverse_result.rounded_percentages["Q"],
            ),
            render_reverse_row(
                "V＋Q",
                reverse_result.a_percent,
                reverse_result.rounded_percentages["A"],
            ),
            render_reverse_row(
                "SE 輸入%",
                reverse_result.input_percentages["SE"],
                reverse_result.rounded_percentages["SE"],
            ),
            render_reverse_row(
                "G 輸入%",
                reverse_result.input_percentages["G"],
                reverse_result.rounded_percentages["G"],
            ),
        ]
        st.markdown(
            f"""
            <div class="reverse-list">
              {''.join(reverse_rows)}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not reverse_result.is_three_digit_name:
            st.markdown(
                '<div class="warning"><b>名稱格式提醒：</b>'
                '取整後至少有一個命名數字超過 9，'
                '因此產生的名稱不再是標準前三段數字格式。</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div class="notice"><b>命名規則：</b>'
            '前三段依序為 V＋Q、SE、G；'
            '括號內顯示 V 與 Q 的取整數字。</div>',
            unsafe_allow_html=True,
        )

        reverse_text = build_reverse_text(reverse_result)
        st.text_area(
            "反推結果文字",
            reverse_text,
            height=250,
            help="可直接全選複製。",
        )
        reverse_df = pd.DataFrame(reverse_result.rows())
        reverse_download_cols = st.columns(2)
        reverse_download_cols[0].download_button(
            "下載反推結果 CSV",
            reverse_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=(
                f"reverse_{reverse_result.formula_name}_"
                f"{datetime.now():%Y%m%d_%H%M%S}.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )
        reverse_download_cols[1].download_button(
            "下載反推結果文字",
            reverse_text.encode("utf-8"),
            file_name=(
                f"reverse_{reverse_result.formula_name}_"
                f"{datetime.now():%Y%m%d_%H%M%S}.txt"
            ),
            mime="text/plain",
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
        st.session_state.last_reverse = None
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

    D7 用量極少，因此不納入配方固成分與比重估算。

    **配方固成分**

    `固成分 = 各材料固體重量合計 ÷ 主配方總量 × 100%`

    G 固成分固定為 100%；額外添加劑預設 100%，可調整。

    **估算比重**

    `估算比重 = 已知比重材料總重量 ÷ Σ(材料重量 ÷ 材料比重)`

    目前納入 V、Q、SE、G 與水；額外母液、額外添加劑及 D7 暫不納入。

    **反推配方名稱**

    `配製基準 = V + Q + SE + 水`

    `V輸入% = V用量 × V母液濃度 ÷ 配製基準`

    `Q輸入% = Q用量 × Q母液濃度 ÷ 配製基準`

    `SE輸入% = SE用量 × SE母液濃度 ÷ 配製基準`

    `G輸入% = G用量 ÷ 配製基準 × 100`

    命名時先將 V、Q、SE、G 四捨五入為整數：

    `前三段依序為 V＋Q、SE、G`

    `名稱 = [V＋Q][SE][G](VＤQＥ)`

    例如 V=8、Q=1、SE=5、G=6，名稱為 `956(V8Q1)`。

    **品管補加**

    補加後總量會增加，因此採質量平衡計算：

    `補加量 = 批次量 × (目標濃度 − 實測濃度) ÷ (補加原料濃度 − 目標濃度)`
    """)

st.markdown(
    '<p class="small">配方中控台｜不含成本｜不含圓餅圖｜所有用量顯示至小數點後 2 位</p>',
    unsafe_allow_html=True,
)
