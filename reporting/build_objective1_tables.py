"""Build publication-style Objective 1 tables from saved analysis results.

This script reads completed CSV outputs and never fits or reruns a model.
"""

from __future__ import annotations

import csv
import hashlib
import math
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BATCH = Path(os.environ.get("GEM_OBJECTIVE1_BATCH", ROOT / "analysis_output" / "objective1_batch_20260927")).resolve()
CASES = BATCH / "objective_1"
OUT_BASE = Path(os.environ.get("GEM_REPORT_OUTPUT", ROOT / "reporting" / "generated")).resolve()
OUT = OUT_BASE / "objective1_tables"
TARGETS = ("TEA", "OME", "NME")
SCOPES = ("global", "india")
MODELS = (
    "Logistic Regression", "Lasso", "Ridge", "Elastic Net", "Naive Bayes",
    "Decision Tree", "XGBoost", "CatBoost", "Random Forest", "H2O GBM",
)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(name: str, data: list[dict[str, object]]) -> None:
    if not data:
        return
    path = OUT / "csv" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def tex(value: object) -> str:
    text = str(value)
    for original, replacement in (
        ("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
        ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
        ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ):
        text = text.replace(original, replacement)
    return text


def fmt(x: object, digits: int = 3) -> str:
    if x in (None, ""):
        return "--"
    return f"{float(x):.{digits}f}"


def count(x: object) -> str:
    return f"{int(float(x)):,}"


def pct(n: object, total: object, digits: int = 1) -> str:
    return f"{100 * float(n) / float(total):.{digits}f}"


def case(scope: str, feature: str, target: str, filename: str) -> Path:
    return CASES / scope / feature / target / filename


def section_table(title: str, label: str, spec: str, header: list[str], body: list[list[str]],
                  note: str = "", size: str = r"\small") -> str:
    width = len(header)
    assert all(len(row) in (1, width) for row in body)
    lines = [size, r"\setlength{\tabcolsep}{5pt}",
             r"\begin{longtable}{" + spec + "}",
             r"\caption{" + tex(title) + r"}\label{" + label + r"}\\",
             r"\toprule", " & ".join(header) + r"\\", r"\midrule", r"\endfirsthead",
             r"\multicolumn{" + str(width) + r"}{l}{\small\emph{Table continued}}\\",
             r"\toprule", " & ".join(header) + r"\\", r"\midrule", r"\endhead",
             r"\midrule", r"\multicolumn{" + str(width) + r"}{r}{\small Continued on next page}\\",
             r"\endfoot", r"\bottomrule", r"\endlastfoot"]
    lines += [(row[0] + r"\\") if len(row) == 1 else (" & ".join(row) + r"\\")
              for row in body]
    lines.append(r"\end{longtable}")
    if note:
        lines.append(r"{\footnotesize\noindent\emph{Note.} " + note + r"\par}")
    lines.append(r"\normalsize")
    return "\n".join(lines)


def main() -> None:
    if not (BATCH / "pipeline_complete.txt").exists():
        raise RuntimeError("Objective 1 batch is not marked complete")
    OUT.mkdir(parents=True, exist_ok=True)
    sample = rows(BATCH / "all_sample_counts.csv")
    sample_map = {(r["scope"], r["feature_set"], r["outcome"]): r for r in sample}
    performance = rows(BATCH / "all_performance.csv")
    perf_map = {(r["scope"], r["feature_set"], r["outcome"], r["model"]): r
                for r in performance}

    # The feature-set comparison is valid only if the held-out rows match.
    for scope in SCOPES:
        for target in TARGETS:
            a = case(scope, "iv", target, "heldout_rowids.csv").read_bytes()
            b = case(scope, "iv_cv", target, "heldout_rowids.csv").read_bytes()
            if hashlib.sha256(a).digest() != hashlib.sha256(b).digest():
                raise RuntimeError(f"Test/validation rows differ: {scope} {target}")

    parts = [r"\documentclass[10pt]{article}",
             r"\usepackage[T1]{fontenc}", r"\usepackage[utf8]{inputenc}",
             r"\usepackage{lmodern}", r"\usepackage[a4paper,margin=19mm]{geometry}",
             r"\usepackage{booktabs,longtable,array,ragged2e,pdflscape}",
             r"\usepackage{fancyhdr}", r"\usepackage[hidelinks]{hyperref}",
             r"\pagestyle{fancy}", r"\fancyhf{}",
             r"\fancyhead[L]{\small Objective 1: socio-cognitive traits}",
             r"\fancyhead[R]{\small Global and India}",
             r"\fancyfoot[C]{\thepage}",
             r"\setlength{\headheight}{13pt}",
             r"\setlength{\parindent}{0pt}",
             r"\setlength{\parskip}{5pt}",
             r"\begin{document}",
             r"{\LARGE\bfseries Objective 1: tables}\par",
             r"{\large Machine learning and socio-cognitive traits}\par",
             r"\vspace{4mm}",
             r"\noindent\textbf{Scope.} The main tables present IV+CV results for TEA, OME and NME in the global sample (including India) and India alone. The IV-only results appear in the paired comparison table. All model metrics are from the saved held-out test predictions; no model was rerun to produce this document.\par",
             r"\noindent\textbf{Reading guide.} PR-AUC is the area under the precision-recall curve; ROC-AUC is the area under the receiver-operating-characteristic curve. The positive class is outcome=1. Each feature set uses the same held-out records for a given sample and outcome.\par",
             r"\tableofcontents\newpage"]

    # Table 1: sample composition.
    t1 = []
    t1_csv = []
    for scope in SCOPES:
        for target in TARGETS:
            r = sample_map[(scope, "iv_cv", target)]
            row = {"sample": scope.title(), "outcome": target,
                   "n": r["n"], "positive": r["positive"],
                   "prevalence_pct": pct(r["positive"], r["n"]),
                   "train": r["n_train"], "validation": r["n_validation"],
                   "test": r["n_test"], "countries": r["countries"], "years": r["years"]}
            t1_csv.append(row)
            t1.append([tex(row["sample"]), target, count(r["n"]), count(r["positive"]),
                       row["prevalence_pct"], count(r["n_train"]), count(r["n_validation"]),
                       count(r["n_test"]), r["countries"], r["years"]])
    write_csv("table_1_sample.csv", t1_csv)
    parts += [r"\section{Samples and descriptive statistics}",
              section_table("Sample size, outcome prevalence, and data split", "tab:sample",
                            r"@{}llrrrrrrrr@{}",
                            ["Sample", "Target", "$N$", "Positive", "Prev.\\%", "Train", "Valid.", "Test", "Countries", "Years"],
                            t1, "Global includes India. The same eligible respondents and split sizes are used for IV and IV+CV within each sample and target.",
                            r"\footnotesize")]

    # Table 2: summary from saved descriptive files. 0/1 means display share=1.
    feat = rows(case("global", "iv_cv", "TEA", "features.csv"))
    names = [r["variable"] for r in feat]
    dmaps = {scope: {r["variable"]: r for r in rows(case(scope, "iv_cv", "TEA", "descriptive_statistics.csv"))}
             for scope in SCOPES}
    household = pd.read_csv(BATCH.parent / "model_input.csv", usecols=["country_name", "hhsize"])
    household["hhsize"] = pd.to_numeric(household["hhsize"], errors="coerce")
    hh_quantiles = {
        "global": household["hhsize"].quantile([0.25, 0.50, 0.75]).to_list(),
        "india": household.loc[household["country_name"].eq("India"), "hhsize"]
                  .quantile([0.25, 0.50, 0.75]).to_list(),
    }
    del household
    t2, t2_csv = [], []
    for name in names:
        a, b = dmaps["global"][name], dmaps["india"][name]
        def summary(r: dict[str, str]) -> str:
            if r["type"] == "categorical":
                return f"{len(r['categories'].split(';'))} categories"
            lo, hi = r["minimum"], r["maximum"]
            if lo == "0" and hi == "1":
                return f"{100 * float(r['mean']):.1f}\\% = 1"
            if name == "hhsize":
                q = hh_quantiles["global" if r["n"] == "1342884" else "india"]
                return f"{q[1]:.0f} [{q[0]:.0f}, {q[2]:.0f}]"
            mean, sd = float(r["mean"]), float(r["sd"])
            if abs(mean) >= 1000:
                return f"{mean:,.0f} ({sd:,.0f})"
            return f"{mean:.2f} ({sd:.2f})"
        # Summary text is LaTeX-ready only for percentage sign; use a safe escape first.
        ga, ib = summary(a), summary(b)
        type_label = "Categorical" if a["type"] == "categorical" else "Numeric"
        t2_csv.append({"variable": name, "role": next(x["role"] for x in feat if x["variable"] == name),
                       "type": type_label, "global_summary": ga.replace(r"\%", "%"),
                       "global_missing_pct": pct(a["n_missing"], a["n"]),
                       "india_summary": ib.replace(r"\%", "%"),
                       "india_missing_pct": pct(b["n_missing"], b["n"])})
        t2.append([r"\texttt{" + tex(name) + "}", type_label,
                   ga if r"\%" in ga else tex(ga), pct(a["n_missing"], a["n"]),
                   ib if r"\%" in ib else tex(ib), pct(b["n_missing"], b["n"])])
    write_csv("table_3_descriptive.csv", t2_csv)
    desc_section = [r"\begin{landscape}",
              section_table("Descriptive statistics for Objective 1 predictors", "tab:desc",
                            r"@{}p{66mm}p{23mm}p{56mm}rp{56mm}r@{}",
                            ["Predictor", "Type", "Global summary", "Miss.\\%", "India summary", "Miss.\\%"],
                            t2,
                            "Binary variables show the observed percentage coded 1. Other numeric variables show mean (SD), except household size, which shows median [Q1, Q3] because of extreme values. Categorical variables show the number of observed categories. Values are respondent-weighted. Missingness uses all eligible respondents as denominator. Survey year and country-level variables are controls.",
                            r"\small"), r"\end{landscape}"]

    # Table 3: intention missingness by outcome; critical audit.
    t3, t3_csv = [], []
    for scope in SCOPES:
        for target in TARGETS:
            data = rows(case(scope, "iv_cv", target, "intention_missingness_by_outcome.csv"))
            counts = {(int(r["outcome"]), r["intention_missing"]): int(r["Freq"]) for r in data}
            n_pos = counts[(1, "TRUE")] + counts[(1, "FALSE")]
            n_neg = counts[(0, "TRUE")] + counts[(0, "FALSE")]
            entry = {"sample": scope.title(), "target": target,
                     "positive_total": n_pos, "positive_missing": counts[(1, "TRUE")],
                     "positive_missing_pct": pct(counts[(1, "TRUE")], n_pos),
                     "negative_total": n_neg, "negative_missing": counts[(0, "TRUE")],
                     "negative_missing_pct": pct(counts[(0, "TRUE")], n_neg)}
            t3_csv.append(entry)
            t3.append([scope.title(), target, count(n_pos), count(counts[(1, "TRUE")]),
                       entry["positive_missing_pct"], count(n_neg), count(counts[(0, "TRUE")]),
                       entry["negative_missing_pct"]])
    write_csv("table_2_intention_missingness.csv", t3_csv)
    parts += [section_table("Entrepreneurial intention missingness by outcome", "tab:intention",
                            r"@{}llrrrrrr@{}",
                            ["Sample", "Target", "Positive $N$", "Missing", "Missing\\%", "Negative $N$", "Missing", "Missing\\%"],
                            t3,
                            "Missing intention is retained as a distinct predictor state. Its survey pattern is strongly associated with outcome status; interpretation of model performance must account for this.",
                            r"\small")] + desc_section

    # Table 4: all ten model performances, six case groups.
    t4, t4_csv = [], []
    for scope in SCOPES:
        for target in TARGETS:
            ntest = sample_map[(scope, "iv_cv", target)]["n_test"]
            t4.append([r"\multicolumn{9}{@{}l}{\textbf{" +
                       tex(f"{scope.title()} | {target} | test N={count(ntest)}") + r"}}"])
            for model in MODELS:
                r = perf_map[(scope, "iv_cv", target, model)]
                t4_csv.append({"sample": scope.title(), "target": target, "model": model,
                               "test_n": ntest, **{key: r[key] for key in
                                   ("auc_roc", "auc_pr", "precision", "recall", "f1", "accuracy", "threshold")}})
                t4.append([tex(model), fmt(r["auc_roc"]), fmt(r["auc_pr"]),
                           fmt(r["precision"]), fmt(r["recall"]), fmt(r["f1"]),
                           fmt(r["accuracy"]), fmt(r["threshold"]), count(ntest)])
    write_csv("table_4_classifier_performance.csv", t4_csv)
    parts += [r"\clearpage\begin{landscape}\section{Classifier results}",
              section_table("Held-out classifier performance, IV+CV", "tab:perf",
                            r"@{}p{43mm}rrrrrrrr@{}",
                            ["Model", "ROC-AUC", "PR-AUC", "Prec.", "Recall", "F1", "Acc.", "Thresh.", "Test $N$"],
                            t4,
                            "Each group uses the same test respondents across models. Thresholds were selected from validation data; metrics are evaluated on held-out test data. Scores are rounded for display; source CSVs retain full precision.",
                            r"\small"), r"\end{landscape}"]

    # Table 5: full confusion matrices.
    t5, t5_csv = [], []
    for scope in SCOPES:
        for target in TARGETS:
            t5.append([r"\multicolumn{7}{@{}l}{\textbf{" +
                       tex(f"{scope.title()} | {target}") + r"}}"])
            crows = {r["model"]: r for r in rows(case(scope, "iv_cv", target, "confusion_matrices.csv"))}
            for model in MODELS:
                r = crows[model]
                total = sum(int(r[k]) for k in ("TP", "FP", "TN", "FN"))
                expected = int(sample_map[(scope, "iv_cv", target)]["n_test"])
                if total != expected:
                    raise RuntimeError(f"Confusion matrix does not sum to test N: {scope}/{target}/{model}")
                t5_csv.append({"sample": scope.title(), "target": target, "model": model,
                               **{k: r[k] for k in ("TP", "FP", "TN", "FN")},
                               "test_n": total})
                t5.append([tex(model), count(r["TP"]), count(r["FP"]), count(r["TN"]),
                           count(r["FN"]), count(total), fmt(perf_map[(scope, "iv_cv", target, model)]["threshold"])])
    write_csv("table_5_confusion_matrices.csv", t5_csv)
    parts += [section_table("Held-out confusion matrices, IV+CV", "tab:conf",
                            r"@{}p{48mm}rrrrrr@{}",
                            ["Model", "TP", "FP", "TN", "FN", "Test $N$", "Thresh."],
                            t5,
                            "TP=true positives; FP=false positives; TN=true negatives; FN=false negatives. Counts use each model's validation-selected threshold.",
                            r"\footnotesize")]

    # Table 6: feature set comparisons for every paired model.
    t6, t6_csv = [], []
    for scope in SCOPES:
        for target in TARGETS:
            t6.append([r"\multicolumn{8}{@{}l}{\textbf{" +
                       tex(f"{scope.title()} | {target}") + r"}}"])
            for model in MODELS:
                a = perf_map[(scope, "iv", target, model)]
                b = perf_map[(scope, "iv_cv", target, model)]
                delta_pr = float(b["auc_pr"]) - float(a["auc_pr"])
                delta_roc = float(b["auc_roc"]) - float(a["auc_roc"])
                delta_f1 = float(b["f1"]) - float(a["f1"])
                t6_csv.append({"sample": scope.title(), "target": target, "model": model,
                               "pr_auc_iv": a["auc_pr"], "pr_auc_iv_cv": b["auc_pr"],
                               "delta_pr_auc": delta_pr, "delta_roc_auc": delta_roc,
                               "delta_f1": delta_f1})
                t6.append([tex(model), fmt(a["auc_pr"]), fmt(b["auc_pr"]),
                           f"{delta_pr:+.3f}", f"{delta_roc:+.3f}", f"{delta_f1:+.3f}",
                           fmt(a["f1"]), fmt(b["f1"])])
    write_csv("table_6_controls_comparison.csv", t6_csv)
    parts += [r"\clearpage\begin{landscape}\section{Effect of adding controls}",
              section_table("IV versus IV+CV on matched held-out respondents", "tab:controls",
                            r"@{}p{43mm}rrrrrrr@{}",
                            ["Model", "PR IV", "PR +CV", "$\\Delta$ PR", "$\\Delta$ ROC", "$\\Delta$ F1", "F1 IV", "F1 +CV"],
                            t6,
                            "Delta is IV+CV minus IV. Held-out row IDs were checked and match exactly for every sample-target pair. No statistical significance is claimed by these descriptive differences.",
                            r"\small"), r"\end{landscape}"]

    # Appendix A1: only Objective 1 variables and controls.
    required = {"country_name", "setid", *TARGETS, *names}
    dictionary = [r for r in rows(BATCH / "appendix_A1_variables.csv") if r["variable"] in required]
    if {r["variable"] for r in dictionary} != required:
        raise RuntimeError("Objective 1 variable dictionary is incomplete")
    short_definition = {
        "country_name": "Survey country; selects the Global or India sample.",
        "setid": "Respondent or observation identifier.",
        "TEA": "Indicator of total early-stage entrepreneurial activity.",
        "OME": "Indicator of opportunity-motivated early-stage entrepreneurship.",
        "NME": "Indicator of necessity-motivated early-stage entrepreneurship.",
        "suskill_2015_2022": "Perceived knowledge, skills and experience to start a business.",
        "opportunity_perception": "Perception of good opportunities to start a business.",
        "fearfail_2015_2022": "Fear of failure as a barrier to starting a business.",
        "knowing_entrepreneur": "Personally knows someone who started a business.",
        "entrepreneurial_intention": "Intention to start a business among eligible non-entrepreneurs.",
        "media_coverage": "Perceived media coverage of successful new businesses.",
        "discent": "Reported business discontinuation or exit.",
        "busang": "Reported business angel investment.",
        "established_business_owner": "Ownership or management of an established business.",
        "good_career_choice": "Belief that entrepreneurship is a desirable career choice.",
        "ease_start_business": "Perceived ease of starting a business.",
        "high_status": "Belief that successful entrepreneurs have high status.",
        "social_enterprise": "Social or environmental purpose of entrepreneurial activity.",
        "yrsurv": "Year of the GEM survey.",
        "age": "Respondent age at survey.",
        "gender": "Respondent gender code.",
        "education_attainment": "Harmonized educational attainment category.",
        "household_income": "Relative household income category.",
        "hhsize": "Number of people in the respondent's household.",
        "occupation_status": "Respondent occupational status category.",
        "gdp_per_capita_ppp": "Country GDP per capita adjusted for purchasing power.",
        "population_totalthousands": "Country population measure as stored in the source data.",
        "gdp_growth": "Annual country GDP growth rate.",
    }
    a1 = [[r"\texttt{" + tex(r["variable"]) + "}", tex(r["role"]),
           tex(short_definition[r["variable"]]), tex(r["data_type"])] for r in dictionary]
    write_csv("appendix_A1_variables.csv", dictionary)
    parts += [r"\clearpage\appendix\renewcommand{\thetable}{A\arabic{table}}\renewcommand{\theHtable}{A\arabic{table}}\setcounter{table}{0}",
              r"\begin{landscape}",
              r"\section{Variable and model reference}",
              section_table("Description and type of variables used in Objective 1", "tab:variables",
                            r"@{}p{53mm}p{32mm}p{125mm}p{20mm}@{}",
                            ["Variable", "Role", "Description", "Type"], a1,
                            "Country identifies the sample and setid identifies the record; neither enters a model. Descriptions are drawn from the supplied variable dictionary.",
                            r"\footnotesize")]

    # Appendix A2: model overview and observed time across all 12 cases.
    models = rows(BATCH / "appendix_A2_models.csv")
    a2 = [[tex(r["model"]), tex(r["feature"]), tex(r["advantage"]),
           tex(r["limitation"]), fmt(float(r["total_seconds"]) / 60, 1)] for r in models]
    write_csv("appendix_A2_models.csv", models)
    parts += [r"\clearpage", section_table("Advantages, limitations, and observed model runtime", "tab:models",
                            r"@{}p{35mm}p{62mm}p{55mm}p{70mm}r@{}",
                            ["Model", "Model type", "Advantage", "Limitation", "Min."],
                            a2,
                            "Runtime is total fit-and-predict time across all 12 Objective 1 cases, not time per case.",
                            r"\footnotesize"), r"\end{landscape}", r"\end{document}"]

    (OUT / "Objective1_Tables.tex").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {OUT / 'Objective1_Tables.tex'}")
    print(f"Main tables: 6; appendix tables: 2; CSV exports: {len(list((OUT / 'csv').glob('*.csv')))}")


if __name__ == "__main__":
    main()
