import hashlib
import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class ReproductionTests(unittest.TestCase):
    def test_source_hashes_match_metadata(self):
        metadata = json.loads((ROOT / "outputs" / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(
            sha256(ROOT / "data_raw" / "divulgacao_anos_finais_municipios_2023.xlsx"),
            metadata["sha256_historical"],
        )
        self.assertEqual(
            sha256(ROOT / "data_raw" / "saeb_2025_brasil_estados_municipios_censitario.xlsx"),
            metadata["sha256_saeb_2025"],
        )

    def test_published_estimates_are_reproduced(self):
        results = pd.read_csv(ROOT / "outputs" / "tables" / "resultados_modelos.csv")
        main = results[results["model"] == "Principal: DiD 2023-2025"].set_index("subject")
        self.assertAlmostEqual(main.loc["Matemática", "estimate"], 2.0469329896934187, places=8)
        self.assertAlmostEqual(main.loc["Língua Portuguesa", "estimate"], 2.412055791390383, places=8)
        self.assertTrue((main["n"] == 948).all())

    def test_panel_contains_only_municipal_aggregates(self):
        panel = pd.read_csv(ROOT / "outputs" / "painel_analitico.csv")
        self.assertEqual(set(panel["subject"].unique()), {"Matemática", "Língua Portuguesa"})
        self.assertEqual(panel.loc[panel["year"] == 2025, "code"].nunique(), 496)
        self.assertNotIn("student_id", panel.columns)
        self.assertNotIn("school_id", panel.columns)


if __name__ == "__main__":
    unittest.main()

