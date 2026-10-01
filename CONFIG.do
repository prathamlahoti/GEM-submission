* Run Stata from the submission root; only edit these two paths.
global GEM_ROOT `"`c(pwd)'"'
global GEM_SOURCE "C:\path\to\HarmonizedGEM_2015_22Final.dta"
global GEM_RSCRIPT "C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
global GEM_INPUT "$GEM_ROOT\model_input.csv"
* Set to 1 after changing the source data, then restore to 0.
global GEM_REEXPORT 0
