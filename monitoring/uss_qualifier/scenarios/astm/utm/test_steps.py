from __future__ import annotations

from typing import List, Optional, Union
from implicitdict import ImplicitDict
from monitoring.monitorlib import schema_validation, fetch
from monitoring.monitorlib.clients.flight_planning.client import FlightPlannerClient
from monitoring.monitorlib.geotemporal import Volume4DCollection
from uas_standards.astm.f3548.v21.api import (
    OperationalIntentState,
    Volume4D,
    OperationalIntentReference,
    GetOperationalIntentDetailsResponse,
)
from monitoring.monitorlib.clients.flight_planning.flight_info import (
    UasState,
    AirspaceUsageState,
)
from monitoring.uss_qualifier.common_data_definitions import Severity
from monitoring.uss_qualifier.resources.astm.f3548.v21.dss import DSSInstance
from monitoring.uss_qualifier.resources.flight_planning.flight_planner import (
    FlightPlanner,
)
from monitoring.monitorlib.clients.flight_planning.flight_info import FlightInfo
from monitoring.uss_qualifier.scenarios.astm.utm.evaluation import (
    validate_op_intent_details,
)
from monitoring.uss_qualifier.scenarios.scenario import (
    TestScenarioType,
    TestRunCannotContinueError,
)
from uas_standards.interuss.automated_testing.scd.v1.api import InjectFlightRequest


class OpIntentValidator(object):
    """
    This class enables the validation of the sharing (or not) of an operational
    intent with the DSS. It does so by comparing the operational intents found
    in the area of the intent before and after a planning attempt.
    It is meant to be used within a `with` statement.
    It assumes an area lock on the extent of the flight intent.
    """

    _before_oi_refs: List[OperationalIntentReference]
    _before_query: fetch.Query

    _after_oi_refs: List[OperationalIntentReference]
    _after_query: fetch.Query

    _new_oi_ref: Optional[OperationalIntentReference] = None

    def __init__(
        self,
        scenario: TestScenarioType,
        flight_planner: Union[FlightPlanner, FlightPlannerClient],
        dss: DSSInstance,
        test_step: str,
        extent: Volume4D,
        orig_oi_ref: Optional[OperationalIntentReference] = None,
    ):
        """
        :param scenario:
        :param flight_planner:
        :param dss:
        :param test_step:
        :param extent: the extent over which the operational intents are to be compared.
        :param orig_oi_ref: if this is validating a previously existing operational intent (e.g. modification), pass the original reference.
        """
        self._scenario: TestScenarioType = scenario
        self._flight_planner: Union[FlightPlanner, FlightPlannerClient] = flight_planner
        self._dss: DSSInstance = dss
        self._test_step: str = test_step
        self._extent: Volume4D = extent
        self._orig_oi_ref: Optional[OperationalIntentReference] = orig_oi_ref

    def __enter__(self) -> OpIntentValidator:
        self._before_oi_refs, self._before_query = self._dss.find_op_intent(
            self._extent
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._scenario.record_note(
                self._flight_planner.participant_id,
                f"Exception occurred during OpIntentValidator ({exc_type}: {exc_val}).",
            )
            raise exc_val

    def _find_after_oi(self, oi_id: str) -> Optional[OperationalIntentReference]:
        found = [oi_ref for oi_ref in self._after_oi_refs if oi_ref.id == oi_id]
        return found[0] if len(found) != 0 else None

    def _begin_step(self):
        self._after_oi_refs, self._after_query = self._dss.find_op_intent(self._extent)
        oi_ids_delta = {oi_ref.id for oi_ref in self._after_oi_refs} - {
            oi_ref.id for oi_ref in self._before_oi_refs
        }

        if (
            len(oi_ids_delta) > 1
        ):  # TODO: could a USS cut up a submitted flight intent into several op intents?
            raise TestRunCannotContinueError(
                f"unexpectedly got more than 1 new operational intent after planning request was created (IDs: {oi_ids_delta}): the test scenario might be malformed or some external requests might have interfered"
            )
        if len(oi_ids_delta) == 1:
            self._new_oi_ref = self._find_after_oi(oi_ids_delta.pop())

        self._scenario.begin_test_step(self._test_step)
        self._scenario.record_query(self._before_query)
        self._scenario.record_query(self._after_query)

        with self._scenario.check("DSS responses", [self._dss.participant_id]) as check:
            if self._before_query.status_code != 200:
                check.record_failed(
                    summary="Failed to query DSS for operational intents before planning request",
                    severity=Severity.High,
                    details=f"Received status code {self._before_query.status_code} from the DSS",
                    query_timestamps=[self._before_query.request.timestamp],
                )
            if self._after_query.status_code != 200:
                check.record_failed(
                    summary="Failed to query DSS for operational intents after planning request",
                    severity=Severity.High,
                    details=f"Received status code {self._after_query.status_code} from the DSS",
                    query_timestamps=[self._after_query.request.timestamp],
                )

    def expect_not_shared(self) -> None:
        """Validate that an operational intent information was not shared with the DSS.

        It implements the test step described in validate_not_shared_operational_intent.md.
        """
        self._begin_step()

        with self._scenario.check(
            "Operational intent not shared", [self._flight_planner.participant_id]
        ) as check:
            if self._new_oi_ref is not None:
                check.record_failed(
                    summary="Operational intent reference was incorrectly shared with DSS",
                    severity=Severity.High,
                    details=f"USS {self._flight_planner.participant_id} was not supposed to share an operational intent with the DSS, but the new operational intent with ID {self._new_oi_ref.id} was found",
                    query_timestamps=[self._after_query.request.timestamp],
                )

        self._scenario.end_test_step()

    def expect_shared(
        self,
        flight_intent: Union[InjectFlightRequest, FlightInfo],
        skip_if_not_found: bool = False,
    ) -> Optional[OperationalIntentReference]:
        """Validate that operational intent information was correctly shared for a flight intent.

        This function implements the test step described in validate_shared_operational_intent.md.

        :param flight_intent: the flight intent that was supposed to have been shared.
        :param skip_if_not_found: set to True to skip the execution of the checks if the operational intent was not found while it should have been modified.

        :returns: the shared operational intent reference. None if skipped because not found.
        """
        oi_ref = self._operational_intent_shared_check(flight_intent, skip_if_not_found)

        oi_full, oi_full_query = self._dss.get_full_op_intent(
            oi_ref, self._flight_planner.participant_id
        )
        self._scenario.record_query(oi_full_query)
        self._operational_intent_retrievable_check(oi_full_query)

        with self._scenario.check(
            "Operational intent details data format",
            [self._flight_planner.participant_id],
        ) as check:
            errors = schema_validation.validate(
                schema_validation.F3548_21.OpenAPIPath,
                schema_validation.F3548_21.GetOperationalIntentDetailsResponse,
                oi_full_query.response.json,
            )
            if errors:
                check.record_failed(
                    summary="Operational intent details response failed schema validation",
                    severity=Severity.Medium,
                    details="The response received from querying operational intent details failed validation against the required OpenAPI schema:\n"
                    + "\n".join(
                        f"At {e.json_path} in the response: {e.message}" for e in errors
                    ),
                    query_timestamps=[oi_full_query.request.timestamp],
                )

        with self._scenario.check(
            "Correct operational intent details", [self._flight_planner.participant_id]
        ) as check:
            priority = (
                flight_intent.operational_intent.priority
                if isinstance(flight_intent, InjectFlightRequest)
                else flight_intent.astm_f3548_21.priority
            )
            if isinstance(flight_intent, InjectFlightRequest):
                priority = flight_intent.operational_intent.priority
                vols = Volume4DCollection.from_interuss_scd_api(
                    flight_intent.operational_intent.volumes
                    + flight_intent.operational_intent.off_nominal_volumes
                )
            elif isinstance(flight_intent, FlightInfo):
                priority = flight_intent.astm_f3548_21.priority
                vols = flight_intent.basic_information.area

            error_text = validate_op_intent_details(
                oi_full.details,
                priority,
                vols.bounding_volume.to_f3548v21(),
            )
            if error_text:
                check.record_failed(
                    summary="Operational intent details do not match user flight intent",
                    severity=Severity.High,
                    details=error_text,
                    query_timestamps=[oi_full_query.request.timestamp],
                )

        with self._scenario.check(
            "Off-nominal volumes", [self._flight_planner.participant_id]
        ) as check:
            if (
                oi_full.reference.state == OperationalIntentState.Accepted
                or oi_full.reference.state == OperationalIntentState.Activated
            ) and oi_full.details.get("off_nominal_volumes", None):
                check.record_failed(
                    summary="Accepted or Activated operational intents are not allowed off-nominal volumes",
                    severity=Severity.Medium,
                    details=f"Operational intent {oi_full.reference.id} was {oi_full.reference.state} and had {len(oi_full.details.off_nominal_volumes)} off-nominal volumes",
                    query_timestamps=[oi_full_query.request.timestamp],
                )

        with self._scenario.check(
            "Vertices", [self._flight_planner.participant_id]
        ) as check:

            def volume_vertices(v4):
                if "outline_circle" in v4.volume:
                    return 1
                if "outline_polygon" in v4.volume:
                    return len(v4.volume.outline_polygon.vertices)

            all_volumes = oi_full.details.get("volumes", []) + oi_full.details.get(
                "off_nominal_volumes", []
            )
            n_vertices = sum(volume_vertices(v) for v in all_volumes)

            if n_vertices > 10000:
                check.record_failed(
                    summary="Too many vertices",
                    severity=Severity.Medium,
                    details=f"Operational intent {oi_full.reference.id} had {n_vertices} vertices total",
                    query_timestamps=[oi_full_query.request.timestamp],
                )

        self._scenario.end_test_step()
        return oi_full.reference

    def expect_shared_with_invalid_data(
        self,
        flight_intent: Union[InjectFlightRequest, FlightInfo],
        skip_if_not_found: bool = False,
    ) -> Optional[OperationalIntentReference]:
        """Validate that operational intent information was shared with dss for a flight intent, but shared invalid data with USS.

        This function implements the test step described in validate_sharing_operational_intent_but_with_invalid_interuss_data.

        :param skip_if_not_found: set to True to skip the execution of the checks if the operational intent was not found while it should have been modified.

        :returns: the shared operational intent reference. None if skipped because not found.
        """

        oi_ref = self._operational_intent_shared_check(flight_intent, skip_if_not_found)

        goidr_json, oi_full_query = self._dss.get_full_op_intent_without_validation(
            oi_ref, self._flight_planner.participant_id
        )

        self._scenario.record_query(oi_full_query)
        self._operational_intent_retrievable_check(oi_full_query)

        # validation errors expected check
        with self._scenario.check(
            "Invalid data in Operational intent details shared by Mock USS for negative test",
            [self._flight_planner.participant_id],
        ) as check:
            validation_errors = []
            try:
                goidr = ImplicitDict.parse(
                    goidr_json, GetOperationalIntentDetailsResponse
                )
                oi_full = goidr.operational_intent

                if (
                    oi_full.reference.state == OperationalIntentState.Accepted
                    or oi_full.reference.state == OperationalIntentState.Activated
                ) and oi_full.details.get("off_nominal_volumes", None):
                    details = f"Operational intent {oi_full.reference.id} had {len(oi_full.details.off_nominal_volumes)} off-nominal volumes in wrong state - {oi_full.reference.state}"
                    validation_errors.append(details)

                def volume_vertices(v4):
                    if "outline_circle" in v4.volume:
                        return 1
                    if "outline_polygon" in v4.volume:
                        return len(v4.volume.outline_polygon.vertices)

                all_volumes = oi_full.details.get("volumes", []) + oi_full.details.get(
                    "off_nominal_volumes", []
                )
                n_vertices = sum(volume_vertices(v) for v in all_volumes)

                if n_vertices > 10000:
                    details = (
                        f"Operational intent {oi_full.reference.id} had too many total vertices - {n_vertices}",
                    )
                    validation_errors.append(details)
            except (KeyError, ValueError) as e:
                validation_errors.append(e)

        if not validation_errors:
            check.record_failed(
                summary="This negative test case requires invalid data shared with other USS in Operational intent details ",
                severity=Severity.High,
                details=f"Data shared by Mock USS with other USSes had no invalid data. This test case required invalid data for testing.",
                query_timestamps=[oi_full_query.request.timestamp],
            )

        self._scenario.end_test_step()
        return oi_ref

    def _operational_intent_retrievable_check(self, oi_full_query):
        with self._scenario.check(
            "Operational intent details retrievable",
            [self._flight_planner.participant_id],
        ) as check:
            if oi_full_query.status_code != 200:
                check.record_failed(
                    summary="Operational intent details could not be retrieved from USS",
                    severity=Severity.High,
                    details=f"Received status code {oi_full_query.status_code} from {self._flight_planner.participant_id} when querying for details of operational intent {oi_ref.id}",
                    query_timestamps=[oi_full_query.request.timestamp],
                )

    def _operational_intent_shared_check(
        self,
        flight_intent: Union[InjectFlightRequest | FlightInfo],
        skip_if_not_found: bool,
    ) -> OperationalIntentReference:

        self._begin_step()

        with self._scenario.check(
            "Operational intent shared correctly", [self._flight_planner.participant_id]
        ) as check:
            if self._orig_oi_ref is None:
                # we expect a new op intent to have been created
                if self._new_oi_ref is None:
                    check.record_failed(
                        summary="Operational intent reference not found in DSS",
                        severity=Severity.High,
                        details=f"USS {self._flight_planner.participant_id} was supposed to have shared a new operational intent with the DSS, but no matching operational intent references were found in the DSS in the area of the flight intent",
                        query_timestamps=[self._after_query.request.timestamp],
                    )
                oi_ref = self._new_oi_ref

            elif self._new_oi_ref is None:
                # We expect the original op intent to have been either modified or left untouched, thus must be among
                # the returned op intents. If additionally the op intent corresponds to an active flight, we fail a
                # different appropriate check. Exception made if skip_if_not_found=True and op intent was deleted: step
                # is skipped.
                modified_oi_ref = self._find_after_oi(self._orig_oi_ref.id)
                if modified_oi_ref is None:
                    if not skip_if_not_found:
                        if (
                            (isinstance(flight_intent, InjectFlightRequest))
                            and (
                                flight_intent.operational_intent.state
                                == OperationalIntentState.Activated
                            )
                        ) or (
                            isinstance(flight_intent, FlightInfo)
                            and (
                                (
                                    flight_intent.basic_information.uas_state
                                    == UasState.Nominal
                                )
                                and (
                                    flight_intent.basic_information.usage_state
                                    == AirspaceUsageState.InUse
                                )
                            )
                        ):
                            with self._scenario.check(
                                "Operational intent for active flight not deleted",
                                [self._flight_planner.participant_id],
                            ) as active_flight_check:
                                active_flight_check.record_failed(
                                    summary="Operational intent reference for active flight not found in DSS",
                                    severity=Severity.High,
                                    details=f"USS {self._flight_planner.participant_id} was supposed to have shared with the DSS an updated operational intent by modifying it, but no matching operational intent references were found in the DSS in the area of the flight intent",
                                    query_timestamps=[
                                        self._after_query.request.timestamp
                                    ],
                                )
                        else:
                            check.record_failed(
                                summary="Operational intent reference not found in DSS",
                                severity=Severity.High,
                                details=f"USS {self._flight_planner.participant_id} was supposed to have shared with the DSS an updated operational intent by modifying it, but no matching operational intent references were found in the DSS in the area of the flight intent",
                                query_timestamps=[self._after_query.request.timestamp],
                            )
                    else:
                        self._scenario.record_note(
                            self._flight_planner.participant_id,
                            f"Operational intent reference with ID {self._orig_oi_ref.id} not found in DSS, instructed to skip test step.",
                        )
                        self._scenario.end_test_step()
                        return None
                oi_ref = modified_oi_ref

            else:
                # we expect the original op intent to have been replaced with a new one, thus old one must NOT be among the returned op intents
                if self._find_after_oi(self._orig_oi_ref.id) is not None:
                    check.record_failed(
                        summary="Operational intent reference found duplicated in DSS",
                        severity=Severity.High,
                        details=f"USS {self._flight_planner.participant_id} was supposed to have shared with the DSS an updated operational intent by replacing it, but it ended up duplicating the operational intent in the DSS",
                        query_timestamps=[self._after_query.request.timestamp],
                    )
                oi_ref = self._new_oi_ref

        return oi_ref


def set_uss_available(
    scenario: TestScenarioType,
    test_step: str,
    dss: DSSInstance,
    uss_sub: str,
) -> str:
    """Set the USS availability to 'Available'.

    This function implements the test step described in set_uss_available.md.

    Returns:
        The new version of the USS availability.
    """
    scenario.begin_test_step(test_step)
    availability_version, avail_query = dss.set_uss_availability(
        uss_sub,
        True,
    )
    scenario.record_query(avail_query)
    with scenario.check(
        "USS availability successfully set to 'Available'", [dss.participant_id]
    ) as check:
        if availability_version is None:
            check.record_failed(
                summary=f"Availability of USS {uss_sub} could not be set to available",
                severity=Severity.High,
                details=f"DSS responded code {avail_query.status_code}; error message: {avail_query.error_message}",
                query_timestamps=[avail_query.request.timestamp],
            )
    scenario.end_test_step()
    return availability_version


def set_uss_down(
    scenario: TestScenarioType,
    test_step: str,
    dss: DSSInstance,
    uss_sub: str,
) -> str:
    """Set the USS availability to 'Down'.

    This function implements the test step described in set_uss_down.md.

    Returns:
        The new version of the USS availability.
    """
    scenario.begin_test_step(test_step)
    availability_version, avail_query = dss.set_uss_availability(
        uss_sub,
        False,
    )
    scenario.record_query(avail_query)
    with scenario.check(
        "USS availability successfully set to 'Down'", [dss.participant_id]
    ) as check:
        if availability_version is None:
            check.record_failed(
                summary=f"Availability of USS {uss_sub} could not be set to down",
                severity=Severity.High,
                details=f"DSS responded code {avail_query.status_code}; error message: {avail_query.error_message}",
                query_timestamps=[avail_query.request.timestamp],
            )
    scenario.end_test_step()
    return availability_version
