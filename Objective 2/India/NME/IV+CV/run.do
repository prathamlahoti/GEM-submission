version 19
clear all
set more off

* Start Stata with its working directory set to the submission root.
do "CONFIG.do"
do "prepare_data.do"
capture erase "Objective 2\India\NME\IV+CV\rerun_output\pipeline_complete.txt"
capture erase "Objective 2\India\NME\IV+CV\rerun_output\rerun_failed.txt"
winexec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "run_case.ps1" -CaseDir "Objective 2\India\NME\IV+CV" -RscriptPath "$GEM_RSCRIPT"
local attempts = 0
capture confirm file "Objective 2\India\NME\IV+CV\rerun_output\pipeline_complete.txt"
while _rc {
    capture confirm file "Objective 2\India\NME\IV+CV\rerun_output\rerun_failed.txt"
    if !_rc {
        display as error "R analysis failed. See rerun_console.log in the case folder."
        exit 459
    }
    sleep 1000
    local attempts = `attempts' + 1
    if `attempts' > 43200 {
        display as error "Timed out waiting for R analysis."
        exit 459
    }
    capture confirm file "Objective 2\India\NME\IV+CV\rerun_output\pipeline_complete.txt"
}
confirm file "Objective 2\India\NME\IV+CV\rerun_output\pipeline_complete.txt"
display as result "Completed: Objective 2\India\NME\IV+CV"
