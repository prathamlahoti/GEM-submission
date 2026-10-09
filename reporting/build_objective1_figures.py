"""Create Objective 1 publication figures from completed, saved model outputs.

The script only reads CSV outputs; it never trains or resumes a classifier.
Requires pandas, numpy, matplotlib, and pypdf (for the combined PDF).
"""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BATCH = Path(os.environ.get("GEM_OBJECTIVE1_BATCH", ROOT / "analysis_output" / "objective1_batch_20260927")).resolve()
CASES = BATCH / "objective_1"
OUT_BASE = Path(os.environ.get("GEM_REPORT_OUTPUT", ROOT / "reporting" / "generated")).resolve()
OUT = OUT_BASE / "objective1_figures"
SCOPES = ("global", "india")
TARGETS = ("TEA", "OME", "NME")
MODELS = (
    "Logistic Regression", "Lasso", "Ridge", "Elastic Net", "Naive Bayes",
    "Decision Tree", "XGBoost", "CatBoost", "Random Forest", "H2O GBM",
)
SLUGS = {
    "Logistic Regression": "logistic_regression", "Lasso": "lasso", "Ridge": "ridge",
    "Elastic Net": "elastic_net", "Naive Bayes": "naive_bayes",
    "Decision Tree": "decision_tree", "XGBoost": "xgboost", "CatBoost": "catboost",
    "Random Forest": "random_forest", "H2O GBM": "h2o_gbm",
}
COLORS = (
    "#212121", "#5f6368", "#9a9a9a", "#425d75", "#8a6145",
    "#436e62", "#6b5a85", "#a06868", "#4b6c96", "#7b773e",
)
STYLES = ("-", "--", ":", "-.", "-", "--", ":", "-.", "-", "--")
LABELS = {
    "entrepreneurial_intention": "Entrepreneurial intention",
    "established_business_owner": "Established business owner",
    "opportunity_perception": "Opportunity perception",
    "suskill_2015_2022": "Self-efficacy",
    "fearfail_2015_2022": "Fear of failure",
    "knowing_entrepreneur": "Knows an entrepreneur",
    "good_career_choice": "Good career choice",
    "ease_start_business": "Ease of starting business",
    "population_totalthousands": "Population",
    "gdp_per_capita_ppp": "GDP per capita (PPP)",
    "education_attainment": "Education",
    "occupation_status": "Occupation status",
    "household_income": "Household income",
    "media_coverage": "Media coverage",
    "social_enterprise": "Social enterprise",
    "high_status": "High status",
    "yrsurv": "Survey year",
    "hhsize": "Household size",
    "gdp_growth": "GDP growth",
    "gender": "Gender",
    "discent": "Business exit",
    "busang": "Business angel",
    "age": "Age",
}


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def case_dir(scope: str, target: str) -> Path:
    return CASES / scope / "iv_cv" / target


def check_inputs() -> dict[tuple[str, str], dict[str, str]]:
    if not (BATCH / "pipeline_complete.txt").exists():
        raise RuntimeError("Objective 1 batch is not complete")
    status = csv_rows(BATCH / "model_status.csv")
    if len(status) != 120 or any(r["status"] != "success" for r in status):
        raise RuntimeError("Expected 120 successful saved model runs")
    counts = {}
    for scope in SCOPES:
        for target in TARGETS:
            folder = case_dir(scope, target)
            if not (folder / "case_complete.txt").exists():
                raise RuntimeError(f"Incomplete case: {scope}/{target}")
            counts[(scope, target)] = csv_rows(folder / "sample_counts.csv")[0]
            a = (CASES / scope / "iv" / target / "heldout_rowids.csv").read_bytes()
            b = (folder / "heldout_rowids.csv").read_bytes()
            if hashlib.sha256(a).digest() != hashlib.sha256(b).digest():
                raise RuntimeError(f"IV and IV+CV rows differ: {scope}/{target}")
    return counts


def style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9.5,
        "axes.titlesize": 11, "axes.labelsize": 9.5,
        "axes.edgecolor": "#444444", "axes.linewidth": 0.8,
        "xtick.color": "#333333", "ytick.color": "#333333",
        "grid.color": "#dedede", "grid.linewidth": 0.55,
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })


def save(fig: plt.Figure, stem: str) -> Path:
    pdf = OUT / f"{stem}.pdf"
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.25)
    fig.savefig(OUT / f"{stem}.png", dpi=220, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return pdf


def curve_figure(kind: str, counts: dict[tuple[str, str], dict[str, str]]) -> Path:
    is_roc = kind == "roc"
    fig, axes = plt.subplots(2, 3, figsize=(15.2, 8.8), sharex=True, sharey=True)
    for i, scope in enumerate(SCOPES):
        for j, target in enumerate(TARGETS):
            ax = axes[i, j]
            for k, model in enumerate(MODELS):
                path = case_dir(scope, target) / "models" / SLUGS[model] / (
                    "roc_coordinates.csv.gz" if is_roc else "pr_coordinates.csv.gz")
                data = pd.read_csv(path)
                x = data["fpr" if is_roc else "recall"].to_numpy(dtype=float)
                y = data["tpr" if is_roc else "precision"].to_numpy(dtype=float)
                if not (len(x) > 1 and abs(x[0]) < 1e-8 and abs(x[-1] - 1) < 1e-8):
                    raise RuntimeError(f"Bad curve endpoints: {path}")
                indices = np.unique(np.linspace(0, len(x) - 1, min(2400, len(x)), dtype=int))
                ax.plot(x[indices], y[indices], color=COLORS[k], ls=STYLES[k],
                        lw=1.35, alpha=0.94, solid_capstyle="round")
            if is_roc:
                ax.plot([0, 1], [0, 1], color="#b8b8b8", ls="--", lw=0.85, zorder=0)
            else:
                prevalence = float(counts[(scope, target)]["prevalence"])
                ax.axhline(prevalence, color="#b8b8b8", ls="--", lw=0.85, zorder=0)
            ax.set_title(f"{scope.title()}  |  {target}", loc="left", fontweight="bold", pad=8)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1.01)
            ax.set_xticks(np.linspace(0, 1, 6))
            ax.set_yticks(np.linspace(0, 1, 6))
            ax.grid(True, alpha=0.75)
            ax.spines[["top", "right"]].set_visible(False)
            if i == 1:
                ax.set_xlabel("False-positive rate" if is_roc else "Recall")
            if j == 0:
                ax.set_ylabel("True-positive rate" if is_roc else "Precision")
    handles = [Line2D([0], [0], color=COLORS[k], ls=STYLES[k], lw=2, label=model)
               for k, model in enumerate(MODELS)]
    handles.append(Line2D([0], [0], color="#b8b8b8", ls="--", lw=1,
                          label="Chance line" if is_roc else "Outcome prevalence"))
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.055),
               ncol=4, frameon=False, fontsize=9, handlelength=2.7, columnspacing=1.2)
    fig.suptitle("Figure 1. ROC curves for Objective 1" if is_roc else
                 "Figure 2. Precision-recall curves for Objective 1",
                 x=0.06, y=0.98, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.06, 0.017,
             "IV+CV models; held-out test data. Global includes India. All models in each panel use the same test records."
             + ("" if is_roc else " Dashed lines show outcome prevalence."),
             fontsize=8.2, color="#444444")
    fig.subplots_adjust(left=0.06, right=0.985, top=0.92, bottom=0.19, wspace=0.18, hspace=0.27)
    return save(fig, "Figure_1_ROC_IV_CV" if is_roc else "Figure_2_Precision_Recall_IV_CV")


def importance_figure() -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(16.5, 10.2))
    audit = []
    for i, scope in enumerate(SCOPES):
        for j, target in enumerate(TARGETS):
            ax = axes[i, j]
            data = pd.read_csv(case_dir(scope, target) / "random_forest_importance.csv")
            data["importance"] = pd.to_numeric(data["importance"], errors="coerce")
            total = data["importance"].sum()
            if total <= 0:
                raise RuntimeError(f"Empty random-forest importance: {scope}/{target}")
            data["percent"] = 100 * data["importance"] / total
            data = data.sort_values("percent", ascending=False).head(10).iloc[::-1]
            labels = [LABELS.get(v, v.replace("_", " ").title()) for v in data["variable"]]
            bars = ax.barh(labels, data["percent"], height=0.72, color="#5c7284")
            ax.bar_label(bars, labels=[f"{v:.1f}" for v in data["percent"]],
                         padding=3, fontsize=8.3, color="#333333")
            ax.set_xlim(0, max(data["percent"]) * 1.15)
            ax.set_title(f"{scope.title()}  |  {target}", loc="left", fontweight="bold", pad=8)
            ax.set_xlabel("Share of total impurity importance (%)")
            ax.grid(axis="x", alpha=0.7)
            ax.set_axisbelow(True)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.tick_params(axis="y", length=0)
            for _, row in data.iterrows():
                audit.append({"sample": scope, "target": target,
                              "variable": row["variable"], "importance": row["importance"],
                              "share_pct": row["percent"]})
    pd.DataFrame(audit).to_csv(OUT / "Figure_3_importance_top10.csv", index=False)
    fig.suptitle("Figure 3. Random-forest feature importance for Objective 1",
                 x=0.03, y=0.985, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.03, 0.015,
             "IV+CV models. Top 10 features per panel; percentages use all fitted features as denominator. "
             "Impurity importance is descriptive and does not establish causal effects. "
             "Entrepreneurial intention has outcome-linked missingness (Table 2).",
             fontsize=8.1, color="#444444")
    fig.subplots_adjust(left=0.16, right=0.98, top=0.92, bottom=0.09, wspace=0.51, hspace=0.43)
    return save(fig, "Figure_3_RF_Feature_Importance_IV_CV")


def controls_figure() -> Path:
    comp = pd.read_csv(BATCH / "feature_set_comparison.csv")
    if len(comp) != 60:
        raise RuntimeError("Expected 60 paired comparisons")
    comp["delta_pr"] = comp["auc_pr_iv_cv"] - comp["auc_pr_iv"]
    fig, axes = plt.subplots(2, 3, figsize=(15.8, 9.8), sharex=True)
    low = min(-0.012, comp["delta_pr"].min() * 1.2)
    high = max(0.245, comp["delta_pr"].max() * 1.13)
    for i, scope in enumerate(SCOPES):
        for j, target in enumerate(TARGETS):
            ax = axes[i, j]
            group = comp[(comp["scope"] == scope) & (comp["outcome"] == target)]
            group = group.set_index("model").loc[list(MODELS)]
            values = group["delta_pr"].to_numpy()
            y = np.arange(len(MODELS))
            ax.axvline(0, color="#444444", lw=0.8)
            ax.hlines(y, 0, values, color="#7b8b96", lw=2.5)
            ax.scatter(values, y, color=np.where(values >= 0, "#3d6778", "#9b685b"),
                       s=28, zorder=3)
            ax.set_yticks(y, MODELS, fontsize=8.4)
            ax.invert_yaxis()
            ax.set_xlim(low, high)
            ax.grid(axis="x", alpha=0.7)
            ax.set_axisbelow(True)
            ax.set_title(f"{scope.title()}  |  {target}", loc="left", fontweight="bold", pad=8)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.tick_params(axis="y", length=0)
            if i == 1:
                ax.set_xlabel("Change in PR-AUC (IV+CV minus IV)")
    fig.suptitle("Figure 4. Predictive change after adding controls",
                 x=0.05, y=0.985, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.05, 0.014,
             "Positive values favour IV+CV. Each pair uses exactly the same held-out respondents. "
             "Differences describe this test split; no causal effect or significance test is implied.",
             fontsize=8.2, color="#444444")
    fig.subplots_adjust(left=0.12, right=0.985, top=0.92, bottom=0.08, wspace=0.39, hspace=0.31)
    return save(fig, "Figure_4_Control_Increment_PR_AUC")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    counts = check_inputs()
    pdfs = [curve_figure("roc", counts), curve_figure("pr", counts),
            importance_figure(), controls_figure()]
    combined = OUT / "Objective1_Figures.pdf"
    if shutil.which("pdfunite"):
        subprocess.run(["pdfunite", *(str(pdf) for pdf in pdfs), str(combined)], check=True)
    else:
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        for pdf in pdfs:
            reader = PdfReader(str(pdf))
            if len(reader.pages) != 1:
                raise RuntimeError(f"Figure is not one page: {pdf}")
            writer.add_page(reader.pages[0])
        with combined.open("wb") as stream:
            writer.write(stream)
    print(f"Wrote {len(pdfs)} vector PDF figures, PNG previews and {combined}")


if __name__ == "__main__":
    main()
