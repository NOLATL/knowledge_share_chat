from playbook_shared.analytics.features import build_feature_profile, pain_score
from playbook_shared.analytics.models import RespondentProfile


def test_feature_profile_normalizes_text_answers():
    profile = RespondentProfile(
        respondent_id="r1",
        source="synthetic",
        role="Controller",
        answers={
            "close.days": "Close takes 12 days",
            "pain.manual_hours": "140 hours per month",
            "sys.erp": "NetSuite",
            "sys.dataprep_tools": "Excel, Power Query, SQL",
            "ctx.company_profile": "201-1000 employees",
            "pain.error_cost": "Errors delay reporting",
        },
    )

    result = build_feature_profile(profile)

    assert result.feature_vector["close_days"] == 12
    assert result.feature_vector["manual_hours"] == 140
    assert result.feature_vector["erp_netsuite"] == 1
    assert result.feature_vector["tool_sql"] == 1
    assert result.feature_vector["has_pain_error_cost"] == 1
    assert result.feature_vector["score_pain_error_cost"] > 1
    assert result.feature_vector["score_pain_manual_hours"] > result.feature_vector["score_pain_error_cost"]
    assert 1 <= result.maturity_score <= 5


def test_pain_score_weights_answer_content():
    profile = RespondentProfile(
        respondent_id="r1",
        source="synthetic",
        role="Controller",
        answers={
            "pain.manual_hours": "We spend 180 manual hours on spreadsheet prep every month.",
            "pain.audit_burden": "Audit evidence is mostly ready in the system.",
        },
    )

    assert pain_score(profile, "pain.manual_hours") > pain_score(profile, "pain.audit_burden")
    assert pain_score(profile, "pain.bus_factor") == 0
