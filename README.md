# GEM analysis submission

This folder contains **code and results only**. No respondent-level data are included. The tree has 48 case folders: 12 cases each for Objectives 1–3 and 6 cases each for Objectives 4–5. Every case folder has a `run.do`, `run.R`, and one-page `results.pdf`.

## Folder order

`Objective N / India or Global / target / IV, IV+CV, or IV+CV+NES`.

Objectives 1–3 have targets TEA, OME, NME and use IV or IV+CV. Objective 4 has Fear_of_failure; Objective 5 has Business_exit. Objectives 4–5 also have IV+CV+NES. `CASE_INDEX.csv` maps each folder to the exact outcome name, source run, and report page.

## Reproduce a case on Windows

1. Install Stata 19, R 4.6.1, Java 8, and the required R packages. The original runs used CPU. If packages are missing, run `powershell -NoProfile -ExecutionPolicy Bypass -File install_dependencies.ps1 -RscriptPath "C:\path\to\Rscript.exe"` from this folder; internet access is needed to install them. Package versions used in the original runs are listed in `original_package_versions.csv`. The install script creates `.r-lib` and downloads Java 8 for H2O.
2. Obtain the same harmonized GEM `.dta` dataset used in the study. It is intentionally absent here. Edit **only the two paths** in `CONFIG.do`: `GEM_SOURCE` and `GEM_RSCRIPT`. The source must have the variables named in `prepare_data.do` and the same 2015–2022 harmonization. Different source data can give different results.
3. Start Stata, change its working directory to this submission root (`cd "C:\path\to\GEM_Submission"`), then run the chosen folder's `.do` file, for example `do "Objective 1\India\TEA\IV\run.do"`.
4. The first run exports the required columns to `model_input.csv`; later runs reuse it. Set `GEM_REEXPORT` to 1 in `CONFIG.do` after changing source data. The run writes fresh files to that case folder's `rerun_output` directory and `rerun_console.log`; `results.pdf` remains the original completed result.

Each `run.do` calls `prepare_data.do`, then the case's `run.R` via `run_case.ps1`. `run.R` loads a shared script from `analysis/`, which contains the actual ten-model pipeline and variable definitions. The CSV dictionary files are needed by the pipeline. The code verifies data, applies training-only preprocessing, uses a stratified 68/12/20 split with fixed seed, and writes predictions, metrics, confusion matrices, ROC/PR coordinates, feature importance, logs, and status files. The completion marker appears only if every requested model succeeds.

Stata starts PowerShell with `winexec` and then waits for a success or failure marker in the case's `rerun_output` folder. Keep Stata and the computer open until the case finishes. Full global cases can take much longer than the one-model diagnostic checks used to validate this package.

Objective 4 excludes fear of failure from its own predictors. Objective 5 combines `EXIT_ENT` and `exit_ent` and excludes duplicate outcome predictor `discent`. IV+CV+NES adds all twelve NES variables to the ten original controls. If you run a NES case after its matching IV+CV case, the code checks held-out row IDs and produces a comparison table. A NES case can run alone using the same fixed split seed.

**Requirements:** Windows PowerShell, Stata, R and the supplied harmonized data. This folder is a reproducible code package, not a claim that code can run without the licensed source data or installed model packages. Use the case PDF for the exact saved study result; rerunning with a different environment can yield small numeric differences.

## Objective 1 tables and figures

The verified combined report is [`reporting/Objective1_Complete_Results.pdf`](reporting/Objective1_Complete_Results.pdf). Run [`generate_tables_figures.py`](generate_tables_figures.py) from this repository root to regenerate its six main tables, two appendix tables, and four figures. Its helper scripts and instructions are in [`reporting/`](reporting/README.md). The large batch outputs and respondent-level data are intentionally not included.
