# Generate Objective 1 tables and figures

`generate_tables_figures.py` rebuilds the Objective 1 tables, four figures, and combined PDF **from saved analysis outputs**. It does not fit models. The supplied `Objective1_Complete_Results.pdf` is the verified report from the original completed batch.

## Inputs

The repository deliberately omits respondent-level data and the large saved batch outputs. To reproduce the report, provide:

- the completed `objective1_batch_20260927` folder, with its `objective_1` case folders, performance CSVs, ROC/PR coordinates, importance CSVs, and completion markers;
- `model_input.csv` in that batch folder's parent (`analysis_output/model_input.csv`), used only to calculate the household-size quartiles in Table 3.

The scripts check that all 120 model statuses are successful and that IV and IV+CV use identical held-out row IDs. They stop if required files are absent.

## Run

Install Python with `pandas`, `numpy`, and `matplotlib`. Install either `pdfunite` or `pypdf` for the combined figure PDF, and `pdflatex` for the table and full-report PDFs.

From the repository root:

```powershell
python generate_tables_figures.py --batch-dir "C:\path\to\analysis_output\objective1_batch_20260927"
```

If `pdflatex` is not on `PATH`, add `--pdflatex "C:\path\to\pdflatex.exe"`. Add `--skip-compile` to generate the LaTeX table source and figure PDFs without compiling the table and full-report PDFs. Use `--output-dir` to choose a different destination. The default is `reporting/generated/`, which Git ignores.

The output has 6 main tables, 2 appendix tables, 4 vector figures, and the combined `objective1_complete/Objective1_Complete_Results.pdf`. The main results use IV+CV for Global and India across TEA, OME, and NME. The comparison table and figure show IV versus IV+CV.
