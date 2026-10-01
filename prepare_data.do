version 19
* Shared, read-only source export used by every run.
capture confirm file "$GEM_INPUT"
local export_now = _rc
if "$GEM_REEXPORT" == "1" local export_now = 1
if `export_now' {
    confirm file "$GEM_SOURCE"
    use ///
        country_name setid yrsurv TEA ///
        OME NME EXIT_ENT exit_ent ///
        suskill_2015_2022 opportunity_perception fearfail_2015_2022 knowing_entrepreneur ///
        entrepreneurial_intention media_coverage discent busang ///
        established_business_owner good_career_choice ease_start_business high_status ///
        social_enterprise age gender education_attainment ///
        household_income hhsize occupation_status gdp_per_capita_ppp ///
        population_totalthousands gdp_growth prosperity_index_score safety__security ///
        personal_freedom governance social_capital investment_environment ///
        enterprise_conditions market_access__infrastructure economic_quality living_conditions ///
        health education natural_environment EFW ///
        EFW_quartile EFW_government EFW_legal EFW_money ///
        EFW_trade EFW_regulation financing govt_support ///
        taxes_bureaucracy govt_programs education_training commercial_infrastructure ///
        rd_transfer market_dynamics market_changes market_entry ///
        physical_infrastructure cultural_social_norms ///
        using "$GEM_SOURCE", clear
    generate double EXIT_ENT_harmonized = EXIT_ENT
    replace EXIT_ENT_harmonized = exit_ent if missing(EXIT_ENT_harmonized)
    generate long __rowid = _n
    order __rowid country_name setid yrsurv
    export delimited using "$GEM_INPUT", replace nolabel
}
confirm file "$GEM_INPUT"
