# SCD Validation of operational intents test scenario

## Description
This test checks that the USS validates correctly the operational intents it creates.
Notably the following requirements:
- **[astm.f3548.v21.OPIN0015](../../../../../requirements/astm/f3548/v21.md)**
- **[astm.f3548.v21.OPIN0020](../../../../../requirements/astm/f3548/v21.md)**
- **[astm.f3548.v21.OPIN0030](../../../../../requirements/astm/f3548/v21.md)**
- **[astm.f3548.v21.OPIN0040](../../../../../requirements/astm/f3548/v21.md)**
- **[astm.f3548.v21.GEN0500](../../../../../requirements/astm/f3548/v21.md)**


## Resources
### flight_intents
FlightIntentsResource that provides the following flight intents:
- `priority_preemption` :

### sut
FlightPlannerResource that will be tested for its validation of operational intents.

### dss
DSSInstanceResource that provides access to a DSS instance where flight creation/sharing can be verified.

### mock_uss
MockUSSResource

## Setup test case
### Check for necessary capabilities test step
Both USSs are queried for their capabilities to ensure this test can proceed.

#### Valid responses check
If either USS does not respond appropriately to the endpoint queried to determine capability, this check will fail.

#### Support BasicStrategicConflictDetection check
This check will fail if the first flight planner does not support BasicStrategicConflictDetection per
**[astm.f3548.v21.GEN0310](../../../../../requirements/astm/f3548/v21.md)** as the USS does not support the InterUSS
implementation of that requirement.

### Area clearing test step
UUT and Mock Uss are requested to remove all flights from the area under test.

#### Area cleared successfully check
**[interuss.automated_testing.flight_planning.ClearArea](../../../../../requirements/interuss/automated_testing/flight_planning.md)**


## Attempt to plan no conflict flight - near existing flight test case
### [Plan Control USS flight - flight 2 test step](../../../../flight_planning/plan_flight_intent.md)
Flight 2 on time range B should be successfully planned by the control USS.

### [Validate flight 2 sharing test step](../../validate_shared_operational_intent.md)
Validate that flight 2 is planned

### [SUT plans flight 1 test step](../../../../flight_planning/plan_flight_intent.md)
The test driver attempts to plan the flight 1 on time range B via the tested USS. It checks if any conflicts with flight 2
which is of equal priority and came first.
per **[astm.f3548.v21.SCD0035](../../../../../requirements/astm/f3548/v21.md)**.

### [Validate flight 1 sharing test step](../../validate_shared_operational_intent.md)
Validate Flight 1 is planned.

### [Validate flight2 GET test step](test_steps/validate_get_operational_intent.md)
Flight1 when being planned, SUT needs to GET information of flight 2

### [Validate flight2 Notification test step](test_steps/validate_notification_operational_intent.md)
Flight 2 not notified. As per **[astm.f3548.v21.USS0105 and SCD0085](../../../../../requirements/astm/f3548/v21.md)**

### [Delete sut flight test step](../../../../flight_planning/delete_flight_intent.md)
Delete sut flight

### [Delete control flight test step](../../../../flight_planning/delete_flight_intent.md)
Delete sut flight

## Attempt to plan deconflicted flight - near a flight sharing invalid data test case
### [Plan Control USS flight - flight 2, sharing invalid interuss data test step](../../../../flight_planning/plan_flight_intent.md)
Flight 2 on time range B should be successfully planned by the control USS.

### [Validate flight 2 shared intent with invalid interuss data test step](test_steps/validate_sharing_operational_intent_with_invalid_interuss_data.md)
Validate that flight 2 is planned

### [SUT attempts to plan flight 1, expect failure test step](test_steps/plan_flight_intent_expect_failed.md)
The test driver attempts to plan the flight 1 on time range B via the tested USS. It checks if any conflicts with flight 2
which is of equal priority and came first.
per **[astm.f3548.v21.SCD0035](../../../../../requirements/astm/f3548/v21.md)**.

### [Validate flight 1 not shared test step](../../validate_not_shared_operational_intent.md)
Validate Flight 1 is not shared.

### [Validate flight2 GET test step](test_steps/validate_get_operational_intent.md)
When Flight1 is being planned, SUT needs to GET information of flight 2

### [Validate flight2 Notification not sent test step](test_steps/validate_no_notification_operational_intent.md)

### [Delete Control USS flight test step](../../../../flight_planning/delete_flight_intent.md)
Delete control USS flight 2

### [Delete SUT flight test step](../../../../flight_planning/delete_flight_intent.md)
Delete control USS flight 2
## Cleanup
### Successful flight deletion check
**[interuss.automated_testing.flight_planning.DeleteFlightSuccess](../../../../../requirements/interuss/automated_testing/flight_planning.md)**
