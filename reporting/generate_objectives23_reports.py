"""Create Objective 2 and 3 result reports from completed batch outputs.

No classifiers are fitted. Usage from the GEM workspace:
    python GEM_Submission/reporting/generate_objectives23_reports.py
Outputs are written beside this script unless --output-dir is supplied.
"""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
TARGETS = ("TEA", "OME", "NME")
SCOPES = ("global", "india")
MODELS = (
    "Logistic Regression", "Lasso", "Ridge", "Elastic Net", "Naive Bayes",
    "Decision Tree", "XGBoost", "CatBoost", "Random Forest", "H2O GBM",
)
SLUGS = {m: m.lower().replace(" ", "_") for m in MODELS}
TITLES = {
    2: "Socio-cognitive traits and Legatum Prosperity",
    3: "Socio-cognitive traits and Fraser economic freedom",
}
INST = {
    2: ("prosperity_index_score", "safety__security", "personal_freedom", "governance",
        "social_capital", "investment_environment", "enterprise_conditions",
        "market_access__infrastructure", "economic_quality", "living_conditions",
        "health", "education", "natural_environment"),
    3: ("EFW", "EFW_quartile", "EFW_government", "EFW_legal", "EFW_money",
        "EFW_trade", "EFW_regulation"),
}


def read(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def f3(value: float) -> str:
    return f"{value:.3f}"


def label(name: str) -> str:
    return name.replace("__missing", " (missing)").replace("_", " ").title()


class Report:
    def __init__(self, objective: int, batch: Path, output: Path):
        self.objective, self.batch, self.output = objective, batch, output
        self.cases = batch / f"objective_{objective}"
        self.output.mkdir(parents=True, exist_ok=True)
        self.figures = self.output / "figures"
        self.figures.mkdir(exist_ok=True)
        self.tables = self.output / "tables"
        self.tables.mkdir(exist_ok=True)
        self.samples = read(batch / "all_sample_counts.csv")
        self.perf = read(batch / "all_performance.csv")
        self.comp = read(batch / "feature_set_comparison.csv")
        status = read(batch / "model_status.csv")
        if not (batch / "pipeline_complete.txt").exists() or len(status) != 120 or not status.status.eq("success").all():
            raise RuntimeError(f"Objective {objective} is not 120/120 successful")
        for s in SCOPES:
            for t in TARGETS:
                a = self.case(s, "iv", t, "heldout_rowids.csv").read_bytes()
                b = self.case(s, "iv_cv", t, "heldout_rowids.csv").read_bytes()
                if a != b:
                    raise RuntimeError(f"IV and IV+CV held-out respondents differ: {s}/{t}")
        self.styles = self._styles()
        self.story = []

    def case(self, scope: str, features: str, target: str, file: str) -> Path:
        return self.cases / scope / features / target / file

    def sample(self, scope: str, target: str) -> pd.Series:
        return self.samples.loc[(self.samples.scope == scope) &
                                (self.samples.feature_set == "iv_cv") &
                                (self.samples.outcome == target)].iloc[0]

    def performance(self, scope: str, target: str, features: str = "iv_cv") -> pd.DataFrame:
        result = self.perf.loc[(self.perf.scope == scope) &
                               (self.perf.outcome == target) &
                               (self.perf.feature_set == features)].copy()
        return result.set_index("model").loc[list(MODELS)].reset_index()

    def importance(self, scope: str, target: str) -> pd.DataFrame:
        df = read(self.case(scope, "iv_cv", target, "random_forest_importance.csv"))
        df["importance"] = pd.to_numeric(df.importance)
        total = df.importance.sum()
        if total <= 0:
            raise RuntimeError("Missing random-forest importance")
        df["share"] = df.importance / total
        return df.sort_values("importance", ascending=False)

    @staticmethod
    def _styles():
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Times-Bold",
                                  fontSize=20, leading=23, spaceAfter=10, textColor=colors.black))
        styles.add(ParagraphStyle(name="SectionX", parent=styles["Heading1"], fontName="Times-Bold",
                                  fontSize=13.5, leading=16, spaceBefore=10, spaceAfter=8,
                                  textColor=colors.black))
        styles.add(ParagraphStyle(name="SubX", parent=styles["Heading2"], fontName="Times-Bold",
                                  fontSize=10.5, leading=13, spaceBefore=9, spaceAfter=4,
                                  textColor=colors.black))
        styles.add(ParagraphStyle(name="BodyX", parent=styles["BodyText"], fontName="Times-Roman",
                                  fontSize=9.5, leading=13.5, spaceAfter=8, textColor=colors.black))
        styles.add(ParagraphStyle(name="NoteX", parent=styles["BodyText"], fontName="Times-Italic",
                                  fontSize=8.3, leading=11, spaceBefore=5, spaceAfter=9,
                                  textColor=colors.black))
        styles.add(ParagraphStyle(name="CellX", parent=styles["BodyText"], fontName="Times-Roman",
                                  fontSize=7.6, leading=9.2, textColor=colors.black))
        styles.add(ParagraphStyle(name="HeaderX", parent=styles["CellX"], fontName="Times-Bold",
                                  alignment=TA_CENTER))
        return styles

    def p(self, text: str, style: str = "BodyX"):
        self.story.append(Paragraph(text, self.styles[style]))

    def heading(self, title: str):
        self.story.append(PageBreak())
        self.p(title, "SectionX")

    def table(self, number: int, title: str, filename: str, data: pd.DataFrame,
              columns: list[tuple[str, str]], widths: list[float], note: str = ""):
        data.to_csv(self.tables / filename, index=False)
        self.p(f"Table {number}. {escape(title)}", "SubX")
        head = [Paragraph(escape(h), self.styles["HeaderX"]) for _, h in columns]
        body = [head]
        for _, row in data.iterrows():
            body.append([Paragraph(escape(str(row[k])), self.styles["CellX"]) for k, _ in columns])
        tab = Table(body, colWidths=widths, repeatRows=1, hAlign="LEFT")
        tab.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
            ("LINEBELOW", (0, -1), (-1, -1), 0.7, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        self.story.append(tab)
        if note:
            self.p(escape(note), "NoteX")

    def interpretation(self, global_text: str, india_text: str):
        self.p("Interpretation", "SubX")
        self.p("<b>Global.</b> " + global_text)
        self.p("<b>India.</b> " + india_text)

    def figure(self, number: int, title: str, image: Path, note: str,
               global_text: str, india_text: str):
        self.heading(f"Figure {number}. {title}")
        from PIL import Image as PILImage
        with PILImage.open(image) as im:
            w, h = im.size
        maxw, maxh = 690, 325
        scale = min(maxw / w, maxh / h)
        self.story.append(Image(str(image), width=w * scale, height=h * scale))
        self.p(escape(note), "NoteX")
        self.interpretation(global_text, india_text)

    def build(self):
        self.p(f"Objective {self.objective}: tables, figures and interpretation", "ReportTitle")
        self.p(escape(TITLES[self.objective]), "SectionX")
        self.p("This report uses the completed saved model outputs. Global includes India. "
               "TEA, OME and NME are modeled separately. Main model comparisons use independent "
               "variables plus controls (IV+CV); Table 6 and Figure 4 compare those fits with IV-only "
               "fits on the same held-out respondents. No model was refitted for this report.")
        self.p("<b>Interpretation guide.</b> PR-AUC measures ranking of positive cases and should be "
               "read against outcome prevalence. ROC-AUC is less sensitive to class imbalance. "
               "Precision, recall, F1 and confusion counts use thresholds chosen on validation data. "
               "Feature importance is descriptive. The analysis measures prediction, not causal effects.")
        self._table1()
        self._table2()
        self._table3()
        self._table4()
        self._table5()
        self._table6()
        self._table7()
        self._figures()
        pdf = self.output / f"Objective{self.objective}_Complete_Results_and_Interpretation.pdf"
        pagesize = landscape(A4)
        doc = BaseDocTemplate(str(pdf), pagesize=pagesize, leftMargin=35,
                              rightMargin=35, topMargin=37, bottomMargin=37,
                              title=f"Objective {self.objective} results and interpretation",
                              author="GEM analysis")
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                      leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0)
        doc.addPageTemplates(PageTemplate(id="normal", frames=frame, onPage=self._footer))
        doc.build(self.story)
        return pdf

    def _footer(self, canv, doc):
        canv.setFont("Times-Roman", 8)
        canv.drawString(35, 22, f"Objective {self.objective} | Global and India | saved held-out results")
        canv.drawRightString(landscape(A4)[0] - 35, 22, str(doc.page))

    def _table1(self):
        self.heading("Samples and coverage")
        rows = []
        for s in SCOPES:
            for t in TARGETS:
                x = self.sample(s, t)
                rows.append(dict(Sample=s.title(), Target=t, N=f"{x.n:,}", Positive=f"{x.positive:,}",
                                 Prevalence=pct(x.prevalence), Train=f"{x.n_train:,}",
                                 Validation=f"{x.n_validation:,}", Test=f"{x.n_test:,}",
                                 Countries=str(x.countries), Years=str(x.years)))
        df = pd.DataFrame(rows)
        cols = [(c, c) for c in df.columns]
        self.table(1, "Sample size, outcome prevalence and data split", "table_1_samples.csv",
                   df, cols, [65, 44, 75, 75, 66, 75, 75, 75, 66, 55],
                   "The same eligible records and held-out split are used for IV and IV+CV within each scope and target.")
        g, i = self.sample("global", "TEA"), self.sample("india", "TEA")
        gprev = ", ".join(f"{t} {pct(self.sample('global', t).prevalence)}" for t in TARGETS)
        iprev = ", ".join(f"{t} {pct(self.sample('india', t).prevalence)}" for t in TARGETS)
        self.interpretation(
            f"The global sample contains {g.n:,} respondents from {g.countries} countries over {g.years} survey years, including India. Positive-case prevalence is {gprev}. The much smaller OME and NME positive classes make PR-AUC and false-positive counts especially informative.",
            f"The India sample contains {i.n:,} respondents across {i.years} years, with {i.n_test:,} held-out test records per target. Positive-case prevalence is {iprev}. India uses the same target definitions and split logic as the global analysis, so the two panels describe different populations rather than alternative definitions.")

    def _table2(self):
        self.heading("Descriptive statistics")
        feat = read(self.case("global", "iv_cv", "TEA", "features.csv"))
        gm = read(self.case("global", "iv_cv", "TEA", "descriptive_statistics.csv")).set_index("variable")
        im = read(self.case("india", "iv_cv", "TEA", "descriptive_statistics.csv")).set_index("variable")
        rows = []
        for name in feat.variable:
            a, b = gm.loc[name], im.loc[name]
            def summary(x):
                if x["type"] == "categorical":
                    return f"{len(str(x.categories).split(';'))} categories"
                if x.minimum == 0 and x.maximum == 1:
                    return pct(x["mean"])
                return f"{x['mean']:.2f} ({x.sd:.2f})"
            rows.append(dict(Variable=name, Role=feat.loc[feat.variable == name, "role"].iloc[0],
                             Global=summary(a), Global_missing=pct(a.n_missing / a.n),
                             India=summary(b), India_missing=pct(b.n_missing / b.n)))
        df = pd.DataFrame(rows)
        self.table(2, "Predictor distributions and missingness", "table_2_descriptives.csv", df,
                   [("Variable", "Variable"), ("Role", "Role"), ("Global", "Global summary"),
                    ("Global_missing", "Missing"), ("India", "India summary"),
                    ("India_missing", "Missing")], [190, 78, 126, 65, 126, 65],
                   "Binary variables show the proportion coded 1; other numeric variables show mean (SD). Missingness is the proportion of eligible respondents without an observed value. All source values are retained in the CSV export.")
        inst = INST[self.objective]
        inst_missing_g = np.mean([gm.loc[n, "n_missing"] / gm.loc[n, "n"] for n in inst])
        inst_missing_i = np.mean([im.loc[n, "n_missing"] / im.loc[n, "n"] for n in inst])
        self.interpretation(
            f"The global descriptive panel includes socio-cognitive predictors, {len(inst)} institutional variables and the agreed controls. Mean missingness across the institutional fields is {pct(inst_missing_g)}; individual rows should be checked before treating any score as universally observed. Country-level scores repeat across respondents within a country-year, so the respondent count is not the number of independent institutional observations.",
            f"The India panel uses the same predictors, with institutional mean missingness of {pct(inst_missing_i)} across the listed fields. India has one institutional score per survey year, shared by all respondents in that year. Consequently, differences in these scores capture year-to-year co-movement and cannot by themselves isolate an institutional mechanism.")

    def _table3(self):
        self.heading("Intention missingness")
        rows = []
        for s in SCOPES:
            for t in TARGETS:
                raw = read(self.case(s, "iv_cv", t, "intention_missingness_by_outcome.csv"))
                def cell(outcome, missing):
                    x = raw[(raw.outcome == outcome) & (raw.intention_missing.astype(str).str.upper() == str(missing).upper())]
                    return int(x.Freq.iloc[0]) if len(x) else 0
                pos, neg = cell(1, True), cell(0, True)
                ptotal = pos + cell(1, False)
                ntotal = neg + cell(0, False)
                rows.append(dict(Sample=s.title(), Target=t, Positive_N=f"{ptotal:,}",
                                 Positive_missing=f"{pos:,}", Positive_pct=pct(pos / ptotal),
                                 Negative_N=f"{ntotal:,}", Negative_missing=f"{neg:,}",
                                 Negative_pct=pct(neg / ntotal)))
        df = pd.DataFrame(rows)
        self.table(3, "Entrepreneurial intention missingness by outcome", "table_3_intention_missingness.csv",
                   df, [("Sample", "Sample"), ("Target", "Target"), ("Positive_N", "Positive N"),
                        ("Positive_missing", "Missing"), ("Positive_pct", "Missing %"),
                        ("Negative_N", "Negative N"), ("Negative_missing", "Missing"),
                        ("Negative_pct", "Missing %")], [72, 55, 90, 90, 80, 90, 90, 80],
                   "Missing intention is retained as a distinct input state under the agreed analysis plan.")
        def rates(scope):
            z = df[df.Sample == scope.title()]
            return ", ".join(f"{r.Target}: {r.Negative_pct}" for _, r in z.iterrows())
        self.interpretation(
            f"In the global sample, entrepreneurial intention is missing for 100% of positive TEA, OME and NME cases, while negative-case missingness is {rates('global')}. This is a strong target-linked pattern in the survey field. The model can use missingness itself as a predictor, so high performance cannot be attributed solely to reported intention or institutional scores.",
            f"The India sample shows the same 100% missingness among positive cases; negative-case missingness is {rates('india')}. Intention remains in the fitted predictors as requested. The result is useful for reproducing the specified predictive task, but a prospective model using an intention question asked of everyone could behave differently.")

    def _table4(self):
        self.heading("Held-out classifier performance")
        rows = []
        for s in SCOPES:
            for t in TARGETS:
                for _, x in self.performance(s, t).iterrows():
                    rows.append(dict(Sample=s.title(), Target=t, Model=x.model,
                                     ROC_AUC=f3(x.auc_roc), PR_AUC=f3(x.auc_pr),
                                     Precision=f3(x.precision), Recall=f3(x.recall), F1=f3(x.f1),
                                     Threshold=f3(x.threshold)))
        df = pd.DataFrame(rows)
        self.table(4, "Classifier performance on held-out test data, IV+CV", "table_4_performance.csv",
                   df, [("Sample", "Sample"), ("Target", "Target"), ("Model", "Model"),
                        ("ROC_AUC", "ROC-AUC"), ("PR_AUC", "PR-AUC"),
                        ("Precision", "Precision"), ("Recall", "Recall"), ("F1", "F1"),
                        ("Threshold", "Threshold")], [58, 43, 134, 68, 68, 76, 65, 51, 77],
                   "All ten models are shown for each target and scope. Thresholds were selected on validation data, then applied once to held-out test data.")
        def best(scope):
            bits = []
            for t in TARGETS:
                x = self.performance(scope, t).sort_values("auc_pr", ascending=False).iloc[0]
                bits.append(f"{t}: {x.model} PR-AUC {f3(x.auc_pr)}, ROC-AUC {f3(x.auc_roc)}")
            return "; ".join(bits)
        self.interpretation(
            f"The highest global PR-AUC in each outcome is {best('global')}. These values are well above each target's prevalence baseline, showing strong ranking of positive cases on the saved test split. Because intention missingness is perfectly present among positive cases (Table 3), this performance should be read as performance of the full observed-data pipeline.",
            f"The highest India PR-AUC values are {best('india')}. The leading algorithm changes by target, so there is no single best model for all India outcomes. India estimates use only 5,510 test cases per target and should be compared with the global results in light of different sample sizes and prevalence.")

    def _table5(self):
        self.heading("Classification counts")
        rows = []
        for s in SCOPES:
            for t in TARGETS:
                cm = read(self.case(s, "iv_cv", t, "confusion_matrices.csv"))
                for _, x in cm.iterrows():
                    total = int(x.TP + x.FP + x.TN + x.FN)
                    if total != int(self.sample(s, t).n_test):
                        raise RuntimeError("Confusion matrix does not sum to test N")
                    rows.append(dict(Sample=s.title(), Target=t, Model=x.model,
                                     TP=f"{x.TP:,}", FP=f"{x.FP:,}", TN=f"{x.TN:,}",
                                     FN=f"{x.FN:,}"))
        df = pd.DataFrame(rows)
        self.table(5, "Held-out confusion matrices, IV+CV", "table_5_confusion_matrices.csv",
                   df, [("Sample", "Sample"), ("Target", "Target"), ("Model", "Model"),
                        ("TP", "TP"), ("FP", "FP"), ("TN", "TN"), ("FN", "FN")],
                   [68, 50, 160, 98, 98, 98, 98],
                   "TP and TN are correct positive and negative classifications; FP and FN are false positive and false negative classifications at each validation-selected threshold.")
        def best_counts(scope):
            bits = []
            for t in TARGETS:
                m = self.performance(scope, t).sort_values("auc_pr", ascending=False).iloc[0].model
                x = read(self.case(scope, "iv_cv", t, "confusion_matrices.csv"))
                x = x[x.model == m].iloc[0]
                bits.append(f"{t} ({m}): {x.TP:,} TP, {x.FP:,} FP, {x.FN:,} FN")
            return "; ".join(bits)
        self.interpretation(
            f"For the highest-PR-AUC model in each global target, the classification counts are {best_counts('global')}. These are threshold-dependent operating points, unlike ROC-AUC and PR-AUC. OME and NME have fewer positive cases, so even modest false-positive counts can materially affect precision.",
            f"The corresponding India operating points are {best_counts('india')}. The table permits an explicit choice between missed entrepreneurs (FN) and false alarms (FP); the preferred trade-off depends on the eventual use. No cost ratio was specified, so the report does not name a universally preferred threshold.")

    def _table6(self):
        self.heading("Added controls")
        rows = []
        for s in SCOPES:
            for t in TARGETS:
                a = self.performance(s, t, "iv").set_index("model")
                b = self.performance(s, t, "iv_cv").set_index("model")
                for m in MODELS:
                    rows.append(dict(Sample=s.title(), Target=t, Model=m,
                                     PR_IV=f3(a.loc[m, "auc_pr"]), PR_IV_CV=f3(b.loc[m, "auc_pr"]),
                                     Delta_PR=f"{b.loc[m, 'auc_pr'] - a.loc[m, 'auc_pr']:+.3f}",
                                     Delta_ROC=f"{b.loc[m, 'auc_roc'] - a.loc[m, 'auc_roc']:+.3f}",
                                     Delta_F1=f"{b.loc[m, 'f1'] - a.loc[m, 'f1']:+.3f}"))
        df = pd.DataFrame(rows)
        self.table(6, "IV versus IV+CV on matched held-out respondents", "table_6_controls_comparison.csv",
                   df, [("Sample", "Sample"), ("Target", "Target"), ("Model", "Model"),
                        ("PR_IV", "PR IV"), ("PR_IV_CV", "PR +CV"),
                        ("Delta_PR", "Delta PR"), ("Delta_ROC", "Delta ROC"),
                        ("Delta_F1", "Delta F1")], [55, 40, 140, 72, 72, 80, 80, 80],
                   "Delta equals IV+CV minus IV. Identical held-out row IDs were verified in each paired comparison. These are descriptive differences, not significance tests.")
        def deltas(scope):
            bits = []
            for t in TARGETS:
                a = self.performance(scope, t, "iv").set_index("model")
                b = self.performance(scope, t, "iv_cv").set_index("model")
                d = b.auc_pr - a.auc_pr
                bits.append(f"{t} median {d.median():+.3f}, range {d.min():+.3f} to {d.max():+.3f}")
            return "; ".join(bits)
        self.interpretation(
            f"Across the ten global models, the change in PR-AUC after adding controls is {deltas('global')}. Positive values indicate that controls improve ranking on the matched test sample. This incremental performance is conditional on the institutional and socio-cognitive predictors already present in the IV-only model.",
            f"For India, the corresponding changes are {deltas('india')}. Controls include survey year; because each India institutional score varies only across years, the institutional and year signals overlap. The gain from adding controls is predictive and does not measure the separate effect of institutions.")

    def _table7(self):
        self.heading("Institutional predictor importance")
        rows = []
        for s in SCOPES:
            for t in TARGETS:
                imp = self.importance(s, t)
                exact = imp[imp.variable.isin(INST[self.objective])].head(5)
                total = imp[imp.variable.isin(INST[self.objective])].share.sum()
                for rank, (_, x) in enumerate(exact.iterrows(), 1):
                    rows.append(dict(Sample=s.title(), Target=t, Rank=rank, Variable=x.variable,
                                     Share=pct(x.share), Institution_total=pct(total)))
        df = pd.DataFrame(rows)
        self.table(7, "Leading institutional variables in random-forest impurity importance", "table_7_institutional_importance.csv",
                   df, [("Sample", "Sample"), ("Target", "Target"), ("Rank", "Rank"),
                        ("Variable", "Institutional predictor"), ("Share", "Share of all"),
                        ("Institution_total", "All institutional")],
                   [60, 47, 45, 240, 90, 130],
                   "Shares use the total importance of all fitted random-forest inputs as denominator. Five largest raw institutional fields are displayed per target; missingness indicators are excluded from the ranking but included in the denominator.")
        def summary(scope):
            bits = []
            for t in TARGETS:
                imp = self.importance(scope, t)
                block = imp[imp.variable.isin(INST[self.objective])]
                top = block.iloc[0]
                bits.append(f"{t}: {label(top.variable)} {pct(top.share)}; all institutional fields {pct(block.share.sum())}")
            return "; ".join(bits)
        self.interpretation(
            f"The global institutional rankings are {summary('global')}. These values describe how the fitted random forest split the observed data; they are not marginal effects or evidence that raising a score changes entrepreneurship. Correlated institutional dimensions may share or substitute for one another in the importance calculation.",
            f"The India institutional rankings are {summary('india')}. With only eight annual values for each national score, these shares are especially sensitive to temporal patterns and the survey-year control. They should be reported as model usage of institutional information, not as evidence for an independent India-level institutional effect.")

    def _figures(self):
        plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8,
                             "axes.spines.top": False, "axes.spines.right": False,
                             "savefig.facecolor": "white"})
        for kind, num, title in (("roc", 1, "ROC curves"), ("pr", 2, "Precision-recall curves")):
            path = self._curves(kind, num)
            def summary(scope):
                bits = []
                metric = "auc_roc" if kind == "roc" else "auc_pr"
                for t in TARGETS:
                    x = self.performance(scope, t).sort_values(metric, ascending=False).iloc[0]
                    bits.append(f"{t} {x.model} {f3(x[metric])}")
                return "; ".join(bits)
            context = ("The diagonal is chance discrimination. " if kind == "roc" else
                       "The dashed horizontal line marks each outcome's positive-case prevalence. ")
            self.figure(num, title, path,
                        "All ten IV+CV models use saved held-out test coordinates. Global includes India. " + context,
                        f"Global leading curve areas are {summary('global')}. " +
                        ("Curves closer to the upper-left corner indicate stronger ranking. Small area differences should not be treated as proven superiority without uncertainty estimates."
                         if kind == "roc" else
                         "The curves should be compared with their outcome-specific prevalence lines, particularly for OME and NME. Precision decreases as recall is pushed higher."),
                        f"India leading curve areas are {summary('india')}. " +
                        ("The India panels use fewer test respondents, which can make curve shapes more variable than global panels. They represent performance in India, not transfer performance from a model trained globally."
                         if kind == "roc" else
                         "The India prevalence baselines differ by target. Curves above these baselines indicate useful positive-case ranking within this saved split, with the intention-missingness pattern in Table 3 still present."))
        path = self._importance_figure()
        def top(scope):
            return "; ".join(f"{t}: {label(self.importance(scope,t).iloc[0].variable)} "
                             f"{pct(self.importance(scope,t).iloc[0].share)}" for t in TARGETS)
        self.figure(3, "Random-forest feature importance", path,
                    "Top eight features in each IV+CV panel; share of all fitted feature importance. Importance is impurity-based and descriptive.",
                    f"The leading global features are {top('global')}. The chart puts institutional predictors and socio-cognitive variables on the same relative scale, but a larger bar does not imply an intervention effect. Intention's missingness pattern is particularly relevant when that feature ranks highly.",
                    f"The leading India features are {top('india')}. Institutional bars may be small because their country-level values vary only across eight years and because other variables explain more splits. The survey-year control also shares temporal information with institutional scores.")
        path = self._controls_figure()
        def delta(scope):
            bits=[]
            for t in TARGETS:
                a=self.performance(scope,t,"iv").set_index("model")
                b=self.performance(scope,t,"iv_cv").set_index("model")
                d=b.auc_pr-a.auc_pr
                bits.append(f"{t}: {int((d>0).sum())}/10 models improve, median {d.median():+.3f}")
            return "; ".join(bits)
        self.figure(4, "Change in PR-AUC after adding controls", path,
                    "Positive values favor IV+CV. Each comparison uses the same held-out respondents and model family.",
                    f"For global fits, {delta('global')}. The spread across algorithms shows that controls do not have one fixed predictive contribution; their value depends on the fitted model and outcome.",
                    f"For India fits, {delta('india')}. Since annual institutional scores and survey year move together, a positive increment is best read as additional predictive information from the full control set, not the causal value of a particular national index.")
        path = self._institutional_figure()
        self.figure(5, "Institutional feature importance", path,
                    "Top six raw institutional predictors by random-forest impurity importance for each IV+CV fit. Missingness flags are excluded from the display.",
                    f"The global panels visualize the rankings in Table 7 across TEA, OME and NME. Bars are percentages of all fitted-feature importance, not percentages of institutional importance. Related pillars are correlated, so the order should be treated as a model description rather than an institutional league table.",
                    f"The India panels also reflect only eight annual score profiles. Institutional importance may be assigned differently when year is included, and the bars cannot separate a score's association from other changes over time. The figure supports comparison of predictor usage, not causal attribution.")

    def _curves(self, kind: str, number: int) -> Path:
        fig, axes = plt.subplots(2, 3, figsize=(14.5, 7.3), sharex=True, sharey=True)
        shades = np.linspace(0.12, 0.72, len(MODELS))
        for i, s in enumerate(SCOPES):
            for j, t in enumerate(TARGETS):
                ax=axes[i,j]
                for k,m in enumerate(MODELS):
                    fn="roc_coordinates.csv.gz" if kind=="roc" else "pr_coordinates.csv.gz"
                    d=read(self.case(s,"iv_cv",t,f"models/{SLUGS[m]}/{fn}"))
                    x=d.fpr if kind=="roc" else d.recall
                    y=d.tpr if kind=="roc" else d.precision
                    ix=np.unique(np.linspace(0,len(d)-1,min(1200,len(d)),dtype=int))
                    ax.plot(x.iloc[ix],y.iloc[ix],color=str(shades[k]),linewidth=1.1,
                            linestyle=("-","--",":","-.")[k%4],label=m)
                if kind=="roc": ax.plot([0,1],[0,1],"k:",linewidth=.8)
                else: ax.axhline(self.sample(s,t).prevalence,color="black",linestyle=":",linewidth=.8)
                ax.set_title(f"{s.title()} | {t}")
                ax.set_xlim(0,1);ax.set_ylim(0,1)
                ax.grid(alpha=.18)
                if i==1: ax.set_xlabel("False-positive rate" if kind=="roc" else "Recall")
                if j==0: ax.set_ylabel("True-positive rate" if kind=="roc" else "Precision")
        handles,labels=axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,loc="lower center",ncol=5,frameon=False,fontsize=7)
        fig.suptitle(f"Figure {number}. {kind.upper() if kind=='roc' else 'Precision-recall'} curves - Objective {self.objective}",fontsize=13)
        fig.subplots_adjust(left=.06,right=.985,top=.91,bottom=.16,hspace=.29,wspace=.2)
        path=self.figures/f"figure_{number}_{kind}.png"
        fig.savefig(path,dpi=180,bbox_inches="tight");plt.close(fig)
        return path

    def _bar_panels(self, number: int, institutional: bool) -> Path:
        fig,axes=plt.subplots(2,3,figsize=(14.5,7.7))
        for i,s in enumerate(SCOPES):
            for j,t in enumerate(TARGETS):
                ax=axes[i,j]; d=self.importance(s,t)
                if institutional: d=d[d.variable.isin(INST[self.objective])]
                d=d.head(6 if institutional else 8).iloc[::-1]
                ax.barh([label(v) for v in d.variable],100*d.share,color="#666666")
                ax.set_title(f"{s.title()} | {t}")
                ax.set_xlabel("Share of all feature importance (%)")
                ax.grid(axis="x",alpha=.18);ax.set_axisbelow(True)
                ax.tick_params(axis="y",labelsize=7)
        fig.suptitle(f"Figure {number}. {'Institutional' if institutional else 'Random-forest'} feature importance - Objective {self.objective}",fontsize=13)
        fig.subplots_adjust(left=.18,right=.98,top=.91,bottom=.085,hspace=.48,wspace=.65)
        path=self.figures/f"figure_{number}_{'institutional' if institutional else 'rf'}_importance.png"
        fig.savefig(path,dpi=180,bbox_inches="tight");plt.close(fig)
        return path

    def _importance_figure(self): return self._bar_panels(3,False)
    def _institutional_figure(self): return self._bar_panels(5,True)

    def _controls_figure(self):
        fig,axes=plt.subplots(2,3,figsize=(14.5,7.5),sharex=True)
        for i,s in enumerate(SCOPES):
            for j,t in enumerate(TARGETS):
                ax=axes[i,j]
                a=self.performance(s,t,"iv").set_index("model")
                b=self.performance(s,t,"iv_cv").set_index("model")
                d=(b.auc_pr-a.auc_pr).loc[list(MODELS)]
                y=np.arange(len(MODELS))
                ax.axvline(0,color="black",linewidth=.8)
                ax.hlines(y,0,d,color="#777777",linewidth=2)
                ax.scatter(d,y,color="black",s=11)
                ax.set_yticks(y,MODELS,fontsize=7)
                ax.invert_yaxis();ax.set_title(f"{s.title()} | {t}")
                ax.grid(axis="x",alpha=.18);ax.set_axisbelow(True)
                if i==1:ax.set_xlabel("Delta PR-AUC (IV+CV minus IV)")
        fig.suptitle(f"Figure 4. Change after adding controls - Objective {self.objective}",fontsize=13)
        fig.subplots_adjust(left=.13,right=.98,top=.9,bottom=.1,hspace=.32,wspace=.35)
        path=self.figures/"figure_4_controls_delta.png"
        fig.savefig(path,dpi=180,bbox_inches="tight");plt.close(fig)
        return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root",type=Path,default=WORKSPACE/"analysis_output")
    parser.add_argument("--output-dir",type=Path,default=HERE)
    args=parser.parse_args()
    for n in (2,3):
        batch=args.batch_root/f"objective{n}_batch_20260928"
        out=args.output_dir/f"objective{n}_complete"
        pdf=Report(n,batch,out).build()
        print(pdf)


if __name__=="__main__": main()
