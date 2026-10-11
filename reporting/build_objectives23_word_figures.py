"""Redraw saved Objective 2 and 3 outputs for portrait manuscript pages."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent
MODELS = ("Logistic Regression", "Lasso", "Ridge", "Elastic Net", "Naive Bayes",
          "Decision Tree", "XGBoost", "CatBoost", "Random Forest", "H2O GBM")
SLUG = {x: x.lower().replace(" ", "_") for x in MODELS}
TARGETS = ("TEA", "OME", "NME")
INST = {
    2: ("prosperity_index_score", "safety__security", "personal_freedom", "governance",
        "social_capital", "investment_environment", "enterprise_conditions",
        "market_access__infrastructure", "economic_quality", "living_conditions",
        "health", "education", "natural_environment"),
    3: ("EFW", "EFW_quartile", "EFW_government", "EFW_legal", "EFW_money",
        "EFW_trade", "EFW_regulation"),
}


def setup():
    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 8.5,
                         "axes.titlesize": 9.5, "axes.labelsize": 8.5,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.facecolor": "white", "pdf.fonttype": 42})


def make(objective: int):
    batch = ROOT / "analysis_output" / f"objective{objective}_batch_20260928"
    cases = batch / f"objective_{objective}"
    out = DEST / f"objective{objective}_complete" / "word_figures"
    out.mkdir(parents=True, exist_ok=True)
    performance = pd.read_csv(batch / "all_performance.csv")
    samples = pd.read_csv(batch / "all_sample_counts.csv")

    def c(scope, target, file):
        return cases / scope / "iv_cv" / target / file

    def save(fig, name):
        fig.savefig(out / name, dpi=220, bbox_inches="tight", pad_inches=.12)
        plt.close(fig)

    # Six panels: outcomes are rows; geographic samples are columns.
    for kind, number in (("roc", 1), ("pr", 2)):
        fig, axes = plt.subplots(3, 2, figsize=(7.1, 8.15), sharex=True, sharey=True)
        for i, target in enumerate(TARGETS):
            for j, scope in enumerate(("global", "india")):
                ax = axes[i, j]
                ranking = performance[(performance.scope == scope) &
                                      (performance.outcome == target) &
                                      (performance.feature_set == "iv_cv")]
                metric = "auc_roc" if kind == "roc" else "auc_pr"
                best = ranking.nlargest(5, metric)
                for k, (_, row) in enumerate(best.iterrows()):
                    d = pd.read_csv(c(scope, target,
                        f"models/{SLUG[row.model]}/{'roc' if kind == 'roc' else 'pr'}_coordinates.csv.gz"))
                    x = d.fpr if kind == "roc" else d.recall
                    y = d.tpr if kind == "roc" else d.precision
                    ix = np.unique(np.linspace(0, len(d)-1, min(1200, len(d)), dtype=int))
                    ax.plot(x.iloc[ix], y.iloc[ix], color=str(.12 + k*.16),
                            linestyle=("-", "--", "-.", ":", (0, (5,2,1,2)))[k],
                            linewidth=1.45, label=f"{row.model} ({row[metric]:.3f})")
                if kind == "roc": ax.plot([0,1],[0,1],color="0.75",linestyle=":",linewidth=.9)
                else:
                    prevalence = samples[(samples.scope == scope) &
                                         (samples.outcome == target) &
                                         (samples.feature_set == "iv_cv")].prevalence.iloc[0]
                    ax.axhline(prevalence,color="0.75",linestyle=":",linewidth=.9)
                ax.set_title(f"{target}  |  {scope.title()}", loc="left", fontweight="bold")
                ax.set_xlim(0,1); ax.set_ylim(0,1)
                ax.grid(alpha=.12)
                if i == 2: ax.set_xlabel("False-positive rate" if kind == "roc" else "Recall")
                if j == 0: ax.set_ylabel("True-positive rate" if kind == "roc" else "Precision")
                ax.legend(fontsize=5.7, loc="lower right" if kind == "roc" else "upper right",
                          frameon=False, handlelength=2.4)
        fig.subplots_adjust(left=.12,right=.98,top=.98,bottom=.075,hspace=.23,wspace=.2)
        save(fig, f"figure_{number}.png")

    for number, institutional in ((3, False), (5, True)):
        fig, axes = plt.subplots(3, 2, figsize=(7.1, 8.1))
        for i, target in enumerate(TARGETS):
            for j, scope in enumerate(("global", "india")):
                ax = axes[i, j]
                d = pd.read_csv(c(scope, target, "random_forest_importance.csv"))
                d.importance = pd.to_numeric(d.importance)
                d["share"] = d.importance / d.importance.sum()
                if institutional: d = d[d.variable.isin(INST[objective])]
                d = d.nlargest(5, "share").iloc[::-1]
                names = [v.replace("__missing", " missing").replace("_", " ").title()
                         for v in d.variable]
                ax.barh(names, 100*d.share, color="0.35", height=.63)
                ax.set_title(f"{target}  |  {scope.title()}",loc="left",fontweight="bold")
                ax.set_xlabel("Share of total importance (%)")
                ax.tick_params(axis="y",labelsize=6.2,length=0)
                ax.grid(axis="x",alpha=.12);ax.set_axisbelow(True)
        fig.subplots_adjust(left=.26,right=.98,top=.98,bottom=.06,hspace=.42,wspace=.67)
        save(fig, f"figure_{number}.png")

    fig, axes = plt.subplots(3, 2, figsize=(7.1, 8.1), sharex=True)
    for i, target in enumerate(TARGETS):
        for j, scope in enumerate(("global", "india")):
            ax=axes[i,j]
            a=performance[(performance.scope==scope)&(performance.outcome==target)&
                          (performance.feature_set=="iv")].set_index("model")
            b=performance[(performance.scope==scope)&(performance.outcome==target)&
                          (performance.feature_set=="iv_cv")].set_index("model")
            delta=(b.auc_pr-a.auc_pr).loc[list(MODELS)]
            y=np.arange(len(MODELS))
            ax.axvline(0,color="black",linewidth=.75)
            ax.hlines(y,0,delta,color="0.5",linewidth=1.6)
            ax.plot(delta,y,"o",color="0.2",markersize=2.7)
            ax.set_yticks(y,MODELS,fontsize=6.1);ax.invert_yaxis()
            ax.set_title(f"{target}  |  {scope.title()}",loc="left",fontweight="bold")
            ax.grid(axis="x",alpha=.12);ax.set_axisbelow(True)
            if i==2: ax.set_xlabel("Change in precision-recall area")
    fig.subplots_adjust(left=.18,right=.98,top=.98,bottom=.065,hspace=.34,wspace=.32)
    save(fig,"figure_4.png")


if __name__ == "__main__":
    setup()
    for number in (2, 3): make(number)
