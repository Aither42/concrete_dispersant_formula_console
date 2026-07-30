import unittest

from calculator import (
    PH_VALUES,
    SPECIFIC_GRAVITIES,
    calculate_correction_addition,
    calculate_formula,
)


class FormulaTests(unittest.TestCase):
    def test_additive_final_share_and_g(self):
        result = calculate_formula(
            target_final_total=108,
            active_percentages={"V": 0, "Q": 0, "SE": 0, "M4": 0},
            concentrations={"V": 40, "Q": 60, "SE": 40, "M4": 40},
            g_percent=6,
            additive_percent_of_final=2,
            additive_solids_percent=100,
            formula_name="測試配方",
        )
        self.assertEqual(result.formula_name, "測試配方")
        self.assertAlmostEqual(result.additive_amount, 2.16)
        self.assertAlmostEqual(
            result.pre_g_base_total,
            (108 - 2.16) / 1.06,
        )
        self.assertAlmostEqual(result.total_before_d7, 108)

    def test_q_d7_is_excluded_from_solid_content(self):
        result = calculate_formula(
            target_final_total=100,
            active_percentages={"V": 0, "Q": 12, "SE": 0, "M4": 0},
            concentrations={"V": 40, "Q": 60, "SE": 40, "M4": 40},
            g_percent=0,
        )
        self.assertAlmostEqual(result.q_amount, 20)
        self.assertAlmostEqual(result.d7_amount, 0.06)
        self.assertAlmostEqual(result.solid_mass, 12)
        self.assertAlmostEqual(result.solid_content_percent, 12)

    def test_solid_content_includes_g_and_adjustable_additive(self):
        result = calculate_formula(
            target_final_total=100,
            active_percentages={"V": 0, "Q": 0, "SE": 0, "M4": 0},
            concentrations={"V": 40, "Q": 60, "SE": 40, "M4": 40},
            g_percent=10,
            additive_percent_of_final=10,
            additive_solids_percent=50,
        )
        expected_g = ((100 - 10) / 1.10) * 0.10
        expected_solids = expected_g + 10 * 0.50
        self.assertAlmostEqual(result.solid_mass, expected_solids)
        self.assertAlmostEqual(
            result.solid_content_percent,
            expected_solids,
        )

    def test_specific_gravity_for_q_only_formula(self):
        result = calculate_formula(
            target_final_total=100,
            active_percentages={"V": 0, "Q": 60, "SE": 0, "M4": 0},
            concentrations={"V": 40, "Q": 60, "SE": 40, "M4": 40},
            g_percent=0,
        )
        self.assertAlmostEqual(
            result.estimated_specific_gravity,
            SPECIFIC_GRAVITIES["Q"],
        )
        self.assertAlmostEqual(
            result.specific_gravity_coverage_percent,
            100,
        )

    def test_specific_gravity_excludes_unknown_density_materials(self):
        result = calculate_formula(
            target_final_total=100,
            active_percentages={"V": 0, "Q": 0, "SE": 0, "M4": 20},
            concentrations={"V": 40, "Q": 60, "SE": 40, "M4": 40},
            g_percent=0,
            additive_percent_of_final=10,
        )
        self.assertIsNotNone(result.estimated_specific_gravity)
        self.assertLess(
            result.specific_gravity_coverage_percent,
            100,
        )

    def test_ph_for_v_only_formula(self):
        result = calculate_formula(
            target_final_total=100,
            active_percentages={"V": 40, "Q": 0, "SE": 0, "M4": 0},
            concentrations={"V": 40, "Q": 60, "SE": 40, "M4": 40},
            g_percent=0,
        )
        self.assertAlmostEqual(result.estimated_ph, PH_VALUES["V"], places=6)
        self.assertAlmostEqual(result.ph_coverage_percent, 100)

    def test_ph_uses_hydrogen_ion_volume_weighting(self):
        result = calculate_formula(
            target_final_total=100,
            active_percentages={"V": 20, "Q": 30, "SE": 0, "M4": 0},
            concentrations={"V": 40, "Q": 60, "SE": 40, "M4": 40},
            g_percent=0,
        )
        v_volume = result.mother_liquor_amounts["V"] / SPECIFIC_GRAVITIES["V"]
        q_volume = result.mother_liquor_amounts["Q"] / SPECIFIC_GRAVITIES["Q"]
        water_volume = result.water_amount / SPECIFIC_GRAVITIES["WATER"]
        expected_h = (
            10 ** (-PH_VALUES["V"]) * v_volume
            + 10 ** (-PH_VALUES["Q"]) * q_volume
            + 10 ** (-PH_VALUES["WATER"]) * water_volume
        ) / (v_volume + q_volume + water_volume)
        expected_ph = -__import__("math").log10(expected_h)
        self.assertAlmostEqual(result.estimated_ph, expected_ph, places=9)

    def test_ph_excludes_g_and_unknown_materials(self):
        result = calculate_formula(
            target_final_total=100,
            active_percentages={"V": 0, "Q": 0, "SE": 0, "M4": 10},
            concentrations={"V": 40, "Q": 60, "SE": 40, "M4": 40},
            g_percent=10,
            additive_percent_of_final=10,
        )
        self.assertIsNotNone(result.estimated_ph)
        self.assertLess(result.ph_coverage_percent, 100)

    def test_qc_correction(self):
        result = calculate_correction_addition(
            batch_amount=1000,
            current_percent=5,
            target_percent=6,
            correction_material_percent=40,
        )
        expected = 1000 * (6 - 5) / (40 - 6)
        self.assertAlmostEqual(result.add_amount, expected)
        self.assertAlmostEqual(result.final_percent, 6)


if __name__ == "__main__":
    unittest.main()
