from typing import Optional
from urllib.parse import urlsplit
from loguru import logger
from uas_standards.astm.f3548.v21.api import OperationalIntentState

from monitoring.monitorlib import scd
from monitoring.monitorlib.scd_automated_testing.scd_injection_api import (
    Capability,
    MockUssFlightBehavior,
    MockUssInjectFlightRequest,
)
from monitoring.uss_qualifier.resources.astm.f3548.v21 import DSSInstanceResource
from monitoring.uss_qualifier.resources.astm.f3548.v21.dss import DSSInstance
from monitoring.uss_qualifier.resources.flight_planning import (
    FlightIntentsResource,
)
from monitoring.uss_qualifier.resources.flight_planning.flight_intent import (
    FlightIntent,
)
from monitoring.uss_qualifier.resources.flight_planning.flight_planner import (
    FlightPlanner,
)
from monitoring.uss_qualifier.resources.flight_planning.flight_planners import (
    FlightPlannerResource,
)
from monitoring.uss_qualifier.scenarios.astm.utm.test_steps import (
    validate_shared_operational_intent,
    ValidateNotSharedOperationalIntent,
    validate_post_interactions,
    validate_get_interactions,
    validate_no_post_interactions,
)

from monitoring.uss_qualifier.scenarios.astm.utm.interuss.data_exchange_validation.test_steps.test_steps import (
    plan_flight_intent_expect_failed,
    validate_sharing_operational_intent_with_invalid_interuss_data,
)

from monitoring.uss_qualifier.scenarios.scenario import (
    TestScenario,
    ScenarioCannotContinueError,
)
from monitoring.uss_qualifier.scenarios.flight_planning.test_steps import (
    clear_area,
    check_capabilities,
    plan_flight_intent,
    cleanup_flights,
    delete_flight_intent,
)
from monitoring.uss_qualifier.resources.interuss.mock_uss import (
    MockUSSClient,
    MockUSSResource,
)
from implicitdict import StringBasedDateTime
from datetime import datetime


class ScdGetOpResponseDataValidationBySUT(TestScenario):
    flight_1_id: Optional[str] = None
    flight_1_planned_time_range_A: FlightIntent
    flight_1_activated_time_range_A: FlightIntent
    flight_1_planned_time_range_B: FlightIntent

    flight_2_id: Optional[str] = None
    flight_2_planned_time_range_A: FlightIntent
    flight_2_activated_time_range_A: FlightIntent
    flight_2_equal_prio_planned_time_range_B: FlightIntent

    sut: FlightPlanner
    control_uss: FlightPlanner
    dss: DSSInstance
    mock_uss: MockUSSClient

    def __init__(
        self,
        sut: FlightPlannerResource,
        control_uss: FlightPlannerResource,
        dss: DSSInstanceResource,
        mock_uss: MockUSSResource,
        flight_intents: Optional[FlightIntentsResource] = None,
    ):
        super().__init__()
        self.sut = sut.flight_planner
        self.control_uss = control_uss.flight_planner
        self.dss = dss.dss
        self.mock_uss = mock_uss.mock_uss

        if not flight_intents:
            msg = f"No FlightIntentsResource was provided as input to this test, it is assumed that the jurisdiction of the tested USS ({self.tested_uss.config.participant_id}) does not allow any same priority conflicts, execution of the scenario was stopped without failure"
            self.record_note(
                "Jurisdiction of tested USS does not allow any same priority conflicts",
                msg,
            )
            raise ScenarioCannotContinueError(msg)

        flight_intents = flight_intents.get_flight_intents()
        try:
            (
                self.flight_1_planned_time_range_A,
                self.flight_1_activated_time_range_A,
                self.flight_1_planned_time_range_B,
                self.flight_2_planned_time_range_A,
                self.flight_2_activated_time_range_A,
                self.flight_2_equal_prio_planned_time_range_B,
            ) = (
                flight_intents["flight_1_planned_time_range_A"],
                flight_intents["flight_1_activated_time_range_A"],
                flight_intents["flight_1_planned_time_range_B"],
                flight_intents["flight_2_planned_time_range_A"],
                flight_intents["flight_2_activated_time_range_A"],
                flight_intents["flight_2_equal_prio_planned_time_range_B"],
            )

            assert (
                self.flight_1_planned_time_range_A.request.operational_intent.state
                == OperationalIntentState.Accepted
            ), "flight_1_planned_time_range_A must have state Accepted"
            assert (
                self.flight_1_activated_time_range_A.request.operational_intent.state
                == OperationalIntentState.Activated
            ), "flight_1_activated_time_range_A must have state Activated"
            assert (
                self.flight_1_planned_time_range_B.request.operational_intent.state
                == OperationalIntentState.Accepted
            ), "flight_1_planned_time_range_B must have state Accepted"
            assert (
                self.flight_2_planned_time_range_A.request.operational_intent.state
                == OperationalIntentState.Accepted
            ), "flight_2_planned_time_range_A must have state Accepted"
            assert (
                self.flight_2_activated_time_range_A.request.operational_intent.state
                == OperationalIntentState.Activated
            ), "flight_2_activated_time_range_A must have state Activated"

            assert (
                self.flight_2_equal_prio_planned_time_range_B.request.operational_intent.priority
                == self.flight_1_planned_time_range_A.request.operational_intent.priority
            ), "flight_2 must have priority equal to flight_1"
            assert not scd.vol4s_intersect(
                self.flight_1_planned_time_range_A.request.operational_intent.volumes,
                self.flight_2_planned_time_range_A.request.operational_intent.volumes,
            ), "flight_1_planned_time_range_A and flight_2_planned_time_range_A must not intersect"
            assert not scd.vol4s_intersect(
                self.flight_1_planned_time_range_A.request.operational_intent.volumes,
                self.flight_2_equal_prio_planned_time_range_B.request.operational_intent.volumes,
            ), "flight_1_planned_time_range_A and flight_2_equal_prio_planned_time_range_B must not intersect"

        except KeyError as e:
            raise ValueError(
                f"`{self.me()}` TestScenario requirements for flight_intents not met: missing flight intent {e}"
            )
        except AssertionError as e:
            raise ValueError(
                f"`{self.me()}` TestScenario requirements for flight_intents not met: {e}"
            )

    def run(self):
        self.begin_test_scenario()

        self.record_note(
            "System Under Test",
            f"{self.sut.config.participant_id}",
        )
        self.record_note(
            "Control USS",
            f"{self.control_uss.config.participant_id}",
        )

        self.begin_test_case("Setup")
        if not self._setup():
            return
        self.end_test_case()

        self.begin_test_case(
            "Attempt to plan no conflict flight - near existing flight"
        )
        self._sut_plans_deconflicted_flight_near_existing_flight()
        self.end_test_case()

        self.begin_test_case(
            "Attempt to plan deconflicted flight - near a flight sharing invalid data"
        )
        self._sut_plans_deconflicted_flight_near_invalid_shared_existing_flight()
        self.end_test_case()

        self.end_test_scenario()

    def _setup(self) -> bool:
        if not check_capabilities(
            self,
            "Check for necessary capabilities",
            required_capabilities=[
                (
                    [self.sut, self.control_uss],
                    Capability.BasicStrategicConflictDetection,
                )
            ],
        ):
            return False

        clear_area(
            self,
            "Area clearing",
            [
                self.flight_1_planned_time_range_A,
                self.flight_1_activated_time_range_A,
                self.flight_1_planned_time_range_B,
                self.flight_2_planned_time_range_A,
                self.flight_2_activated_time_range_A,
                self.flight_2_equal_prio_planned_time_range_B,
            ],
            [self.sut, self.control_uss],
        )

        return True

    def _sut_plans_deconflicted_flight_near_existing_flight(self):
        req = self.flight_2_planned_time_range_A.request

        resp_flight_2, self.flight_2_id = plan_flight_intent(
            self,
            "Plan Control USS flight - flight 2",
            self.control_uss,
            req,
            self.mock_uss,
        )

        validate_shared_operational_intent(
            self,
            self.control_uss,
            self.dss,
            "Validate flight 2 sharing",
            self.flight_2_planned_time_range_A.request,
            resp_flight_2.operational_intent_id,
        )

        st = StringBasedDateTime(datetime.utcnow())

        resp_flight_1, self.flight_1_id = plan_flight_intent(
            self,
            "SUT plans flight 1",
            self.sut,
            self.flight_1_planned_time_range_B.request,
        )
        validate_shared_operational_intent(
            self,
            self.sut,
            self.dss,
            "Validate flight 1 sharing",
            self.flight_1_planned_time_range_B.request,
            resp_flight_1.operational_intent_id,
        )

        control_uss_domain = "{0.scheme}://{0.netloc}/".format(
            urlsplit(self.control_uss.config.injection_base_url)
        )
        validate_get_interactions(
            self,
            self.mock_uss,
            st,
            control_uss_domain,
            resp_flight_2.operational_intent_id,
            "Validate flight2 GET",
        )
        validate_post_interactions(
            self,
            self.mock_uss,
            st,
            control_uss_domain,
            "Validate flight2 Notification",
        )

        delete_flight_intent(self, "Delete sut flight", self.sut, self.flight_1_id)
        delete_flight_intent(
            self, "Delete control flight", self.control_uss, self.flight_2_id
        )

    def _sut_plans_deconflicted_flight_near_invalid_shared_existing_flight(self):
        req = self.flight_2_planned_time_range_A.request
        mod = MockUssFlightBehavior(
            modify_sharing_methods=["GET", "POST"],
            modify_fields={
                "operational_intent_reference": {"state": "Flying"},
                "operational_intent_details": {"prioirity": -1},
            },
        )
        mod_req = MockUssInjectFlightRequest(
            operational_intent=req.operational_intent,
            flight_authorisation=req.flight_authorisation,
            mock_uss_flight_behavior=mod,
        )
        resp_flight_2, self.flight_2_id = plan_flight_intent(
            self,
            "Plan Control USS flight - flight 2, sharing invalid interuss data",
            self.control_uss,
            mod_req,
            self.mock_uss,
        )
        validate_sharing_operational_intent_with_invalid_interuss_data(
            self,
            self.control_uss,
            self.dss,
            "Validate flight 2 shared intent with invalid interuss data",
            self.flight_2_planned_time_range_A.request,
            resp_flight_2.operational_intent_id,
        )

        st = StringBasedDateTime(datetime.utcnow())
        with ValidateNotSharedOperationalIntent(
            self,
            self.sut,
            self.dss,
            "Validate flight 1 not shared",
            self.flight_1_planned_time_range_B.request,
        ):
            resp_flight_1, self.flight_1_id = plan_flight_intent_expect_failed(
                self,
                "SUT attempts to plan flight 1, expect failure",
                self.sut,
                self.flight_1_planned_time_range_B.request,
            )

            logger.debug(f"Response on submission to SUT: {resp_flight_1}")

        control_uss_domain = "{0.scheme}://{0.netloc}/".format(
            urlsplit(self.control_uss.config.injection_base_url)
        )
        validate_get_interactions(
            self,
            self.mock_uss,
            st,
            control_uss_domain,
            resp_flight_2.operational_intent_id,
            "Validate flight2 GET",
        )
        validate_no_post_interactions(
            self,
            self.mock_uss,
            st,
            control_uss_domain,
            "Validate flight2 Notification not sent",
        )

        delete_flight_intent(
            self, "Delete Control USS flight", self.control_uss, self.flight_2_id
        )

    def cleanup(self):
        self.begin_cleanup()
        cleanup_flights(self, (self.control_uss, self.sut))
        self.end_cleanup()
