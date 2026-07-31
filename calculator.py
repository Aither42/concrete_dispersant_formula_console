from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping

D7_RATIO_TO_Q = 0.003
MOTHER_LIQUORS = ("V", "Q", "SE", "M4")

# 比重估算採用的固定值。
# 額外母液 M4 與額外添加劑尚無比重資料，暫不納入比重估算。
SPECIFIC_GRAVITIES: dict[str, float] = {
    "V": 1.078,
    "Q": 1.118,
    "SE": 1.078,
    "G": 1.800,
    "WATER": 1.000,
}


class FormulaError(ValueError):
    """配方輸入不符合計算條件。"""


@dataclass(frozen=True)
class FormulaResult:
    formula_name: str
    unit: str
    target_final_total: float
    g_percent: float
    additive_percent_of_final: float
    additive_solids_percent: float
    pre_g_base_total: float
    concentrations: dict[str, float]
    active_percentages: dict[str, float]
    mother_liquor_amounts: dict[str, float]
    water_amount: float
    g_amount: float
    additive_amount: float
    q_amount: float
    d7_amount: float
    total_before_d7: float
    total_with_d7: float
    solid_mass: float
    solid_content_percent: float
    estimated_specific_gravity: float | None
    specific_gravity_coverage_percent: float

    @property
    def has_negative_water(self) -> bool:
        return self.water_amount < -1e-9

    @property
    def has_complete_density_coverage(self) -> bool:
        return self.specific_gravity_coverage_percent >= 99.995

    def rows(self) -> list[dict[str, float | str | None]]:
        labels = {"V": "V", "Q": "Q", "SE": "SE", "M4": "額外母液"}
        rows: list[dict[str, float | str | None]] = []
        for key in MOTHER_LIQUORS:
            rows.append(
                {
                    "材料": labels[key],
                    "有效比例 (%)": round(self.active_percentages[key], 2),
                    "固成分／母液濃度 (%)": round(
                        self.concentrations[key] * 100, 2
                    ),
                    f"投料量 ({self.unit})": round(
                        self.mother_liquor_amounts[key], 2
                    ),
                    "比重估算": (
                        f"{SPECIFIC_GRAVITIES[key]:.3f}"
                        if key in SPECIFIC_GRAVITIES
                        else "未納入"
                    ),
                    "說明": "依 G 前基準換算",
                }
            )
        rows.extend(
            [
                {
                    "材料": "水",
                    "有效比例 (%)": None,
                    "固成分／母液濃度 (%)": 0.0,
                    f"投料量 ({self.unit})": round(self.water_amount, 2),
                    "比重估算": f"{SPECIFIC_GRAVITIES['WATER']:.3f}",
                    "說明": "補足 G 前基準",
                },
                {
                    "材料": "G",
                    "有效比例 (%)": round(self.g_percent, 2),
                    "固成分／母液濃度 (%)": 100.0,
                    f"投料量 ({self.unit})": round(self.g_amount, 2),
                    "比重估算": f"{SPECIFIC_GRAVITIES['G']:.3f}",
                    "說明": "葡萄糖酸鈉，母液與水完成後添加",
                },
                {
                    "材料": "額外添加劑",
                    "有效比例 (%)": round(
                        self.additive_percent_of_final, 2
                    ),
                    "固成分／母液濃度 (%)": round(
                        self.additive_solids_percent, 2
                    ),
                    f"投料量 ({self.unit})": round(
                        self.additive_amount, 2
                    ),
                    "比重估算": "未納入",
                    "說明": "最終目標總量占比",
                },
                {
                    "材料": "D7",
                    "有效比例 (%)": None,
                    "固成分／母液濃度 (%)": 100.0,
                    f"投料量 ({self.unit})": round(self.d7_amount, 2),
                    "比重估算": "不納入",
                    "說明": "Q 用量 × 0.003；不納入固成分及比重",
                },
            ]
        )
        return rows


@dataclass(frozen=True)
class ReverseFormulaResult:
    unit: str
    amounts: dict[str, float]
    concentrations: dict[str, float]
    base_total: float
    total_with_g: float
    input_percentages: dict[str, float]
    rounded_percentages: dict[str, int]
    formula_name: str
    is_three_digit_name: bool
    max_rounding_difference: float

    @property
    def a_percent(self) -> float:
        return (
            self.input_percentages["V"]
            + self.input_percentages["Q"]
        )

    def rows(self) -> list[dict[str, float | int | str]]:
        return [
            {
                "項目": "V 輸入",
                "精確比例 (%)": round(
                    self.input_percentages["V"], 4
                ),
                "命名數字": self.rounded_percentages["V"],
            },
            {
                "項目": "Q 輸入",
                "精確比例 (%)": round(
                    self.input_percentages["Q"], 4
                ),
                "命名數字": self.rounded_percentages["Q"],
            },
            {
                "項目": "V＋Q",
                "精確比例 (%)": round(self.a_percent, 4),
                "命名數字": self.rounded_percentages["A"],
            },
            {
                "項目": "SE 輸入",
                "精確比例 (%)": round(
                    self.input_percentages["SE"], 4
                ),
                "命名數字": self.rounded_percentages["SE"],
            },
            {
                "項目": "G 輸入",
                "精確比例 (%)": round(
                    self.input_percentages["G"], 4
                ),
                "命名數字": self.rounded_percentages["G"],
            },
        ]


@dataclass(frozen=True)
class CorrectionResult:
    unit: str
    batch_amount: float
    current_percent: float
    target_percent: float
    correction_material_percent: float
    add_amount: float
    final_amount: float

    @property
    def final_percent(self) -> float:
        active_before = self.batch_amount * self.current_percent / 100
        active_added = (
            self.add_amount * self.correction_material_percent / 100
        )
        return (
            (active_before + active_added)
            / self.final_amount
            * 100
        )


def _percent(value: float, label: str, positive: bool = False) -> float:
    value = float(value)
    if positive:
        if value <= 0 or value > 100:
            raise FormulaError(
                f"{label}必須大於 0% 且不超過 100%。"
            )
    elif value < 0 or value > 100:
        raise FormulaError(f"{label}必須介於 0% 至 100%。")
    return value


def resolve_vq_effective_percentages(
    vq_total: float,
    v_value: float,
    q_value: float,
) -> tuple[float, float, bool]:
    """
    將 V、Q 輸入值解析成實際有效比例。

    當 V + Q 小於「V＋Q」目標且兩者合計大於 0 時，
    V、Q 視為相對比例，按原比例放大到指定的 V＋Q 總值。
    其他情況維持 V、Q 原輸入值。

    回傳：實際 V%、實際 Q%、是否進行比例放大。
    """
    vq_total = _percent(vq_total, "V＋Q")
    v_value = _percent(v_value, "V 設定")
    q_value = _percent(q_value, "Q 設定")

    entered_total = v_value + q_value
    if entered_total > 0 and entered_total < vq_total - 1e-12:
        scale = vq_total / entered_total
        return v_value * scale, q_value * scale, True

    return v_value, q_value, False


def _calculate_solid_properties(
    mother_liquor_amounts: Mapping[str, float],
    concentrations: Mapping[str, float],
    g_amount: float,
    additive_amount: float,
    additive_solids_percent: float,
    total_before_d7: float,
) -> tuple[float, float]:
    solid_mass = sum(
        mother_liquor_amounts[key] * concentrations[key]
        for key in MOTHER_LIQUORS
    )
    solid_mass += g_amount  # G 為 100% 固體葡萄糖酸鈉。
    solid_mass += additive_amount * additive_solids_percent / 100

    solid_content_percent = (
        solid_mass / total_before_d7 * 100
        if total_before_d7 > 0
        else 0.0
    )
    return solid_mass, solid_content_percent


def _calculate_estimated_specific_gravity(
    mother_liquor_amounts: Mapping[str, float],
    water_amount: float,
    g_amount: float,
    total_before_d7: float,
) -> tuple[float | None, float]:
    """
    以可取得比重的材料做質量／體積加總估算。

    納入：V、Q、SE、G、水。
    排除：額外母液、額外添加劑、D7。
    """
    if water_amount < 0:
        return None, 0.0

    known_masses = {
        "V": mother_liquor_amounts["V"],
        "Q": mother_liquor_amounts["Q"],
        "SE": mother_liquor_amounts["SE"],
        "G": g_amount,
        "WATER": water_amount,
    }
    included_mass = sum(known_masses.values())
    coverage_percent = (
        included_mass / total_before_d7 * 100
        if total_before_d7 > 0
        else 0.0
    )

    if included_mass <= 0:
        return None, coverage_percent

    included_volume = sum(
        mass / SPECIFIC_GRAVITIES[key]
        for key, mass in known_masses.items()
    )
    if included_volume <= 0:
        return None, coverage_percent

    return included_mass / included_volume, coverage_percent


def calculate_formula(
    target_final_total: float,
    active_percentages: Mapping[str, float],
    concentrations: Mapping[str, float],
    g_percent: float,
    additive_percent_of_final: float = 0.0,
    additive_solids_percent: float = 100.0,
    formula_name: str = "未命名配方",
    unit: str = "kg",
) -> FormulaResult:
    """
    額外添加劑量 = 最終目標總量 × 添加劑占比。

    G 為母液與水完成後的後添加：
      pre_g_base = (最終目標總量 - 額外添加劑量) / (1 + G%)
      G量 = pre_g_base × G%

    D7 為主配方之外：Q × 0.003。
    D7 不納入固成分及比重估算。
    """
    target_final_total = float(target_final_total)
    if target_final_total <= 0:
        raise FormulaError("最終目標總量必須大於 0。")

    formula_name = str(formula_name).strip() or "未命名配方"
    g_percent = _percent(g_percent, "G 比例")
    additive_percent_of_final = _percent(
        additive_percent_of_final,
        "額外添加劑比例",
    )
    additive_solids_percent = _percent(
        additive_solids_percent,
        "額外添加劑固成分",
    )
    if additive_percent_of_final >= 100:
        raise FormulaError("額外添加劑比例必須小於 100%。")

    normalized_active: dict[str, float] = {}
    normalized_concentrations: dict[str, float] = {}
    for key in MOTHER_LIQUORS:
        if key not in active_percentages or key not in concentrations:
            raise FormulaError(f"缺少 {key} 的比例或濃度。")
        normalized_active[key] = _percent(
            active_percentages[key],
            f"{key} 有效比例",
        )
        normalized_concentrations[key] = (
            _percent(
                concentrations[key],
                f"{key} 母液濃度",
                positive=True,
            )
            / 100
        )

    additive_amount = (
        target_final_total
        * additive_percent_of_final
        / 100
    )
    g_fraction = g_percent / 100
    pre_g_base_total = (
        target_final_total - additive_amount
    ) / (1 + g_fraction)
    if pre_g_base_total <= 0:
        raise FormulaError(
            "扣除額外添加劑後，母液與水基準必須大於 0。"
        )

    mother_liquor_amounts = {
        key: (
            pre_g_base_total
            * normalized_active[key]
            / 100
            / normalized_concentrations[key]
        )
        for key in MOTHER_LIQUORS
    }
    water_amount = (
        pre_g_base_total
        - sum(mother_liquor_amounts.values())
    )
    g_amount = pre_g_base_total * g_fraction
    q_amount = mother_liquor_amounts["Q"]
    d7_amount = q_amount * D7_RATIO_TO_Q
    total_before_d7 = (
        sum(mother_liquor_amounts.values())
        + water_amount
        + g_amount
        + additive_amount
    )

    solid_mass, solid_content_percent = (
        _calculate_solid_properties(
            mother_liquor_amounts=mother_liquor_amounts,
            concentrations=normalized_concentrations,
            g_amount=g_amount,
            additive_amount=additive_amount,
            additive_solids_percent=additive_solids_percent,
            total_before_d7=total_before_d7,
        )
    )
    (
        estimated_specific_gravity,
        specific_gravity_coverage_percent,
    ) = _calculate_estimated_specific_gravity(
        mother_liquor_amounts=mother_liquor_amounts,
        water_amount=water_amount,
        g_amount=g_amount,
        total_before_d7=total_before_d7,
    )

    return FormulaResult(
        formula_name=formula_name,
        unit=unit,
        target_final_total=target_final_total,
        g_percent=g_percent,
        additive_percent_of_final=additive_percent_of_final,
        additive_solids_percent=additive_solids_percent,
        pre_g_base_total=pre_g_base_total,
        concentrations=normalized_concentrations,
        active_percentages=normalized_active,
        mother_liquor_amounts=mother_liquor_amounts,
        water_amount=water_amount,
        g_amount=g_amount,
        additive_amount=additive_amount,
        q_amount=q_amount,
        d7_amount=d7_amount,
        total_before_d7=total_before_d7,
        total_with_d7=total_before_d7 + d7_amount,
        solid_mass=solid_mass,
        solid_content_percent=solid_content_percent,
        estimated_specific_gravity=estimated_specific_gravity,
        specific_gravity_coverage_percent=(
            specific_gravity_coverage_percent
        ),
    )



def _round_half_up(value: float) -> int:
    """以一般認知的四捨五入（0.5 進位）轉為整數。"""
    return int(
        Decimal(str(float(value))).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def calculate_reverse_formula(
    v_amount: float,
    q_amount: float,
    se_amount: float,
    g_amount: float,
    water_amount: float,
    v_concentration: float = 40.0,
    q_concentration: float = 60.0,
    se_concentration: float = 40.0,
    unit: str = "kg",
) -> ReverseFormulaResult:
    """
    由實際投料量反推配方輸入比例與名稱。

    配製基準：
      base = V + Q + SE + 水

    反推輸入比例：
      V%  = V量  × V母液濃度  ÷ base
      Q%  = Q量  × Q母液濃度  ÷ base
      SE% = SE量 × SE母液濃度 ÷ base
      G%  = G量 ÷ base × 100

    名稱：
      第一段 = 四捨五入後的 V 數字 + Q 數字
      第二段 = 四捨五入後的 SE 數字
      第三段 = 四捨五入後的 G 數字
      配方名稱 = [V＋Q][SE][G](VＤQＥ)

    例如 V=8、Q=1、SE=5、G=6，名稱為 956(V8Q1)。
    """
    amounts = {
        "V": float(v_amount),
        "Q": float(q_amount),
        "SE": float(se_amount),
        "G": float(g_amount),
        "WATER": float(water_amount),
    }
    for key, amount in amounts.items():
        if amount < 0:
            label = "水" if key == "WATER" else key
            raise FormulaError(f"{label} 用量不可小於 0。")

    concentrations = {
        "V": _percent(
            v_concentration,
            "V 母液濃度",
            positive=True,
        ),
        "Q": _percent(
            q_concentration,
            "Q 母液濃度",
            positive=True,
        ),
        "SE": _percent(
            se_concentration,
            "SE 母液濃度",
            positive=True,
        ),
    }

    base_total = (
        amounts["V"]
        + amounts["Q"]
        + amounts["SE"]
        + amounts["WATER"]
    )
    if base_total <= 0:
        raise FormulaError(
            "V、Q、SE 與水的合計必須大於 0。"
        )

    input_percentages = {
        "V": amounts["V"] * concentrations["V"] / base_total,
        "Q": amounts["Q"] * concentrations["Q"] / base_total,
        "SE": (
            amounts["SE"]
            * concentrations["SE"]
            / base_total
        ),
        "G": amounts["G"] / base_total * 100,
    }

    rounded_v = _round_half_up(input_percentages["V"])
    rounded_q = _round_half_up(input_percentages["Q"])
    rounded_se = _round_half_up(input_percentages["SE"])
    rounded_g = _round_half_up(input_percentages["G"])
    rounded_a = rounded_v + rounded_q

    rounded_percentages = {
        "V": rounded_v,
        "Q": rounded_q,
        "A": rounded_a,
        "SE": rounded_se,
        "G": rounded_g,
    }
    formula_name = (
        f"{rounded_a}{rounded_se}{rounded_g}"
        f"(V{rounded_v}Q{rounded_q})"
    )

    naming_values = [
        rounded_a,
        rounded_se,
        rounded_g,
        rounded_v,
        rounded_q,
    ]
    is_three_digit_name = all(
        0 <= value <= 9
        for value in naming_values
    )
    max_rounding_difference = max(
        abs(
            input_percentages[key]
            - rounded_percentages[key]
        )
        for key in ("V", "Q", "SE", "G")
    )

    return ReverseFormulaResult(
        unit=unit,
        amounts=amounts,
        concentrations=concentrations,
        base_total=base_total,
        total_with_g=base_total + amounts["G"],
        input_percentages=input_percentages,
        rounded_percentages=rounded_percentages,
        formula_name=formula_name,
        is_three_digit_name=is_three_digit_name,
        max_rounding_difference=max_rounding_difference,
    )

def calculate_correction_addition(
    batch_amount: float,
    current_percent: float,
    target_percent: float,
    correction_material_percent: float,
    unit: str = "kg",
) -> CorrectionResult:
    """
    品管補加公式，補加後總量會增加：
      (M*C_current + x*C_stock) / (M+x) = C_target
      x = M*(C_target-C_current)/(C_stock-C_target)

    可用於 V、Q、SE、額外母液或 G。
    """
    batch_amount = float(batch_amount)
    if batch_amount <= 0:
        raise FormulaError("目前批次總量必須大於 0。")

    current_percent = _percent(
        current_percent,
        "目前實測濃度",
    )
    target_percent = _percent(
        target_percent,
        "品管目標濃度",
    )
    correction_material_percent = _percent(
        correction_material_percent,
        "補加原料濃度",
        positive=True,
    )

    if target_percent <= current_percent:
        raise FormulaError(
            "品管目標濃度必須高於目前實測濃度。"
        )
    if correction_material_percent <= target_percent:
        raise FormulaError(
            "補加原料濃度必須高於品管目標濃度。"
        )

    add_amount = (
        batch_amount
        * (target_percent - current_percent)
        / (correction_material_percent - target_percent)
    )

    return CorrectionResult(
        unit=unit,
        batch_amount=batch_amount,
        current_percent=current_percent,
        target_percent=target_percent,
        correction_material_percent=correction_material_percent,
        add_amount=add_amount,
        final_amount=batch_amount + add_amount,
    )
