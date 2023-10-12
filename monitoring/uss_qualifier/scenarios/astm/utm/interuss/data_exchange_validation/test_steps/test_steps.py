from typing import Optional
from monitoring.monitorlib import schema_validation, fetch
from uas_standards.astm.f3548.v21.api import OperationalIntentState

from monitoring.monitorlib.scd import bounding_vol4
from monitoring.monitorlib.scd_automated_testing.scd_injection_api import (
    InjectFlightRequest,
    InjectFlightResult,
    InjectFlightResponse,
)
from monitoring.uss_qualifier.common_data_definitions import Severity
from monitoring.uss_qualifier.resources.astm.f3548.v21.dss import DSSInstance
from monitoring.uss_qualifier.resources.flight_planning.flight_planner import (
    FlightPlanner,
)
from monitoring.uss_qualifier.scenarios.flight_planning.test_steps import (
    submit_flight_intent,
    expect_flight_intent_state,
)
from monitoring.uss_qualifier.scenarios.scenario import TestScenarioType
from monitoring.uss_qualifier.resources.interuss.mock_uss import MockUSSClient


def plan_flight_intent_expect_failed(
    scenario: TestScenarioType,
    test_step: str,
    flight_planner: FlightPlanner,
    flight_intent: InjectFlightRequest,
    mock_uss: Optional[MockUSSClient] = None,
) -> InjectFlightResponse:
    """Attempt to plan a flight intent that would result in a Failed result.

    This function implements the test step described in scd_data_exchange_validation.md.
    It validates requirement astm.f3548.v21.SCD00abc.

    Returns: The injection response.
    """
    expect_flight_intent_state(
        flight_intent, OperationalIntentState.Accepted, scenario, test_step
    )

    return submit_flight_intent(
        scenario,
        test_step,
        "Plan should fail",
        {InjectFlightResult.Failed},
        {InjectFlightResult.Planned: "Failure If Planned",
         InjectFlightResult.ConflictWithFlight: "Failure If Conflict",
         InjectFlightResult.Rejected: "Failure If Rejected"
         },
        flight_planner,
        flight_intent,
        mock_uss=mock_uss,
    )[0]


def validate_sharing_operational_intent_with_invalid_interuss_data(
    scenario: TestScenarioType,
    flight_planner: FlightPlanner,
    dss: DSSInstance,
    test_step: str,
    flight_intent: InjectFlightRequest,
    op_intent_id: str,
    skip_if_not_found: bool = False,
) -> bool:
    """Validate that operational intent is shared in DSS, but the data shared with other USSes is invalid.

    This function implements the test step described in
    validate_sharing_operational_intent_with_invalid_data_interuss.md.

    :returns: True if the operational intent was invalid. May return False without failing a check e.g. if the
    operational intent was not found and skip_if_not_found was True.
    """
    scenario.begin_test_step(test_step)
    extent = bounding_vol4(
        flight_intent.operational_intent.volumes
        + flight_intent.operational_intent.off_nominal_volumes
    )
    op_intent_refs, query = dss.find_op_intent(extent)
    scenario.record_query(query)
    with scenario.check("DSS response", [dss.participant_id]) as check:
        if query.status_code != 200:
            check.record_failed(
                summary="Failed to query DSS for operational intents",
                severity=Severity.High,
                details=f"Received status code {query.status_code} from the DSS",
                query_timestamps=[query.request.timestamp],
            )

    matching_op_intent_refs = [
        op_intent_ref
        for op_intent_ref in op_intent_refs
        if op_intent_ref.id == op_intent_id
    ]
    with scenario.check(
        "Operational intent shared with DSS", [flight_planner.participant_id]
    ) as check:
        if not matching_op_intent_refs:
            if not skip_if_not_found:
                check.record_failed(
                    summary="Operational intent reference not found in DSS",
                    severity=Severity.High,
                    details=f"USS {flight_planner.participant_id} was supposed to have shared an operational intent with ID {op_intent_id}, but no operational intent references with that ID were found in the DSS in the area of the flight intent",
                    query_timestamps=[query.request.timestamp],
                )
            else:
                scenario.record_note(
                    flight_planner.participant_id,
                    f"Operational intent reference with ID {op_intent_id} not found in DSS, instructed to skip test step.",
                )
                scenario.end_test_step()
                return False
    op_intent_ref = matching_op_intent_refs[0]

    op_intent, query = dss.get_full_op_intent(op_intent_ref)
    scenario.record_query(query)
    with scenario.check(
        "Operational intent details retrievable", [flight_planner.participant_id]
    ) as check:
        if query.status_code != 200:
            check.record_failed(
                summary="Operational intent details could not be retrieved from USS",
                severity=Severity.High,
                details=f"Received status code {query.status_code} from {flight_planner.participant_id} when querying for details of operational intent {op_intent_id}",
                query_timestamps=[query.request.timestamp],
            )

    with scenario.check(
        "Operational intent details invalid data format", [flight_planner.participant_id]
    ) as check:
        errors = schema_validation.validate(
            schema_validation.F3548_21.OpenAPIPath,
            schema_validation.F3548_21.GetOperationalIntentDetailsResponse,
            query.response.json,
        )
        if not errors:
            check.record_failed(
                summary="Invalid Operational intent details response did not fail schema validation",
                severity=Severity.Medium,
                details="The response received from querying operational intent details has invalid data and should fail OpenAPI schema validation:\n",
                query_timestamps=[query.request.timestamp],
            )

    with scenario.check(
        "Off-nominal volumes", [flight_planner.participant_id]
    ) as check:
        if (
            op_intent.reference.state == OperationalIntentState.Accepted
            or op_intent.reference.state == OperationalIntentState.Activated
        ) and op_intent.details.get("off_nominal_volumes", None):
            check.record_failed(
                summary="Accepted or Activated operational intents are not allowed off-nominal volumes",
                severity=Severity.Medium,
                details=f"Operational intent {op_intent.reference.id} was {op_intent.reference.state} and had {len(op_intent.details.off_nominal_volumes)} off-nominal volumes",
                query_timestamps=[query.request.timestamp],
            )

    all_volumes = op_intent.details.get("volumes", []) + op_intent.details.get(
        "off_nominal_volumes", []
    )

    def volume_vertices(v4):
        if "outline_circle" in v4.volume:
            return 1
        if "outline_polygon" in v4.volume:
            return len(v4.volume.outline_polygon.vertices)

    n_vertices = sum(volume_vertices(v) for v in all_volumes)
    with scenario.check("Vertices", [flight_planner.participant_id]) as check:
        if n_vertices > 10000:
            check.record_failed(
                summary="Too many vertices",
                severity=Severity.Medium,
                details=f"Operational intent {op_intent.reference.id} had {n_vertices} vertices total",
                query_timestamps=[query.request.timestamp],
            )

    scenario.end_test_step()
    return True
