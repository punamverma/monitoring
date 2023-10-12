import arrow

from loguru import logger
from implicitdict import ImplicitDict
from monitoring.monitorlib import fetch
from monitoring.monitorlib.fetch import QueryError, Query
from monitoring.monitorlib.infrastructure import AuthAdapter, UTMClientSession
from monitoring.monitorlib.scd_automated_testing.scd_injection_api import (
    SCOPE_SCD_QUALIFIER_INJECT,
)
from monitoring.uss_qualifier.reports.report import ParticipantID
from monitoring.uss_qualifier.resources.communications import AuthAdapterResource
from monitoring.uss_qualifier.resources.resource import Resource
from monitoring.mock_uss.interaction_logging.interactions import (
    Interaction,
    ListLogsResponse,
)
from typing import Tuple, List
from implicitdict import StringBasedDateTime


class MockUSSClient(object):
    """Means to communicate with an InterUSS mock_uss instance"""

    def __init__(
        self,
        participant_id: str,
        base_url: str,
        auth_adapter: AuthAdapter,
    ):
        self.base_url = base_url
        self.session = UTMClientSession(base_url, auth_adapter)
        self.participant_id = participant_id

    def get_status(self) -> fetch.Query:
        return fetch.query_and_describe(
            self.session, "GET", "/scdsc/v1/status", scope=SCOPE_SCD_QUALIFIER_INJECT
        )

    # TODO: Add other methods to interact with the mock USS in other ways (like starting/stopping message signing data collection)

    def get_interactions(self, from_time: StringBasedDateTime) -> List[Interaction]:
        url = "{}/mock_uss/interuss_logging/logs?from_time={}".format(
            self.base_url, from_time
        )
        logger.debug(f"Getting interactions from {from_time} : {url}")
        query = fetch.query_and_describe(
            self.session, "GET", url, scope=SCOPE_SCD_QUALIFIER_INJECT
        )
        if query.status_code != 200:
            raise QueryError(
                f"Request to mock uss {url} returned a {query.status_code} ", [query]
            )
        try:
            response = ImplicitDict.parse(query.response.get("json"), ListLogsResponse)
        except KeyError:
            raise QueryError(
                msg=f"RecordedInteractionsResponse from mock_uss response did not contain JSON body",
                queries=[query],
            )
        except ValueError as e:
            raise QueryError(
                msg=f"RecordedInteractionsResponse from mock_uss response contained invalid JSON: {str(e)}",
                queries=[query],
            )
        return response.interactions


class MockUSSSpecification(ImplicitDict):
    mock_uss_base_url: str
    """The base URL for the mock USS.

    If the mock USS had scdsc enabled, for instance, then these URLs would be
    valid:
      * <mock_uss_base_url>/mock/scd/uss/v1/reports
      * <mock_uss_base_url>/scdsc/v1/status
    """

    participant_id: ParticipantID
    """Test participant responsible for this mock USS."""


class MockUSSResource(Resource[MockUSSSpecification]):
    mock_uss: MockUSSClient

    def __init__(
        self,
        specification: MockUSSSpecification,
        auth_adapter: AuthAdapterResource,
    ):
        self.mock_uss = MockUSSClient(
            specification.participant_id,
            specification.mock_uss_base_url,
            auth_adapter.adapter,
        )
