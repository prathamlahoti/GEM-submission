"""Assemble the completed Objective 1 tables and figures into one LaTeX PDF.

This only combines existing outputs and does not run or fit any models.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = Path(os.environ.get("GEM_REPORT_OUTPUT", ROOT / "reporting" / "generated")).resolve()
TABLES = OUT_BASE / "objective1_tables" / "Objective1_Tables.tex"
FIGURES = OUT_BASE / "objective1_figures"
OUT = OUT_BASE / "objective1_complete"

FIGURE_FILES = (
    ("Figure 1: ROC curves", "Figure_1_ROC_IV_CV.pdf"),
    ("Figure 2: Precision-recall curves", "Figure_2_Precision_Recall_IV_CV.pdf"),
    ("Figure 3: Random-forest feature importance", "Figure_3_RF_Feature_Importance_IV_CV.pdf"),
    ("Figure 4: Change after adding controls", "Figure_4_Control_Increment_PR_AUC.pdf"),
)


def main() -> None:
    source = TABLES.read_text(encoding="utf-8")
    for _, filename in FIGURE_FILES:
        if not (FIGURES / filename).is_file():
            raise FileNotFoundError(FIGURES / filename)

    source = source.replace(
        r"\usepackage{booktabs,longtable,array,ragged2e,pdflscape}",
        r"\usepackage{booktabs,longtable,array,ragged2e,pdflscape,graphicx}",
        1,
    )
    source = source.replace(
        r"{\LARGE\bfseries Objective 1: tables}\par",
        r"{\LARGE\bfseries Objective 1: tables and figures}\par",
        1,
    )
    source = source.replace(
        "The main tables present IV+CV results",
        "The main tables and figures present IV+CV results",
        1,
    )
    source = source.replace(
        "The IV-only results appear in the paired comparison table.",
        "The IV-only results appear in the paired comparison table and control-increment figure.",
        1,
    )
    source = source.replace(
        "no model was rerun to produce this document.",
        "no model was rerun to produce this document.",
        1,
    )

    figures_tex = [r"\clearpage", r"\begin{landscape}", r"\section{Figures}"]
    for index, (heading, filename) in enumerate(FIGURE_FILES):
        if index:
            figures_tex += [r"\end{landscape}", r"\begin{landscape}"]
        figures_tex += [
            r"\phantomsection\addcontentsline{toc}{subsection}{" + heading + "}",
            r"\begin{center}",
            r"\includegraphics[width=\linewidth,height=0.91\textheight,keepaspectratio]{../objective1_figures/" + filename + "}",
            r"\end{center}",
        ]
    figures_tex += [r"\end{landscape}"]

    anchor = r"\clearpage\appendix"
    if source.count(anchor) != 1:
        raise RuntimeError("Could not locate the tables-to-appendix boundary")
    source = source.replace(anchor, "\n".join(figures_tex) + "\n" + anchor, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "Objective1_Complete_Results.tex"
    target.write_text(source, encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
