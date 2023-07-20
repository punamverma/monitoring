# Test Scenario - Validation of operational intent data exchanged with USS-Under-Test

##Description
These tests aim at ensuring that the USS-Under-Test (UUT) is exchanging correct operational intent data as per the spec.
And the USS-Under-Test, should also not accept any data from another USS that is not as per the spec.

###Feature
Requirement **astm.f3548.v21.USS0105** (A2.5.2 (3)) states -
_notifyOperationalIntentDetailsChanged—this interface is called by a managing USS after the DSS informs it that a peer USS has a subscription relevant to a new, modified, or deleted operational intent.__

The USS owning an operation needs to notify other USSes subscribed in that area about the changes in its operation.
This shared operation should be validated as per the [UTM API spec](https://github.com/astm-utm/Protocol/blob/v1.0.0/utm.yaml#L3614)

It involves the USS-Under-Test and Mock USS both subscribed in an area.
And Operational intents with their volumes within this subscribed area.

###Scenario -
  1. Given USS is subscribed in an area
  2. When an operation is planned/changed in the area.
  3. The USS should be informed about it with correct data

## Sequence
ToDo

## Resources

1. ###uss_under_test
   - FlightPlannerResource that is under test.
2. ###mock_uss
   - Mock USS - FlightPlannerResource that will POST various test intents to USS-Under-Test.
   - Mock USS - USS that will receive POSTs
3. ###dss
   - DSSInstanceResource that provides access to a DSS instance where flight creation/sharing can be verified.
4. ###flight_intents
   - valid_flight_intent
   - invalid_flight_intent_missing_field
   - invalid_flight_intent_invalid_field_value_type
   - invalid_flight_intent_invalid_value_range
5. ###subscription_area
   - subscription area covering the flight_intents


## Validation of operational intent shared to a USS-Under-Test

### Test Case 1 - Valid intent by Mock Uss
1. Setup - USS-Under-Test is subscribed in the area.
2. UssQualifier injects an intent for Mock Uss to submit an operation.
3. [*](##*) Mock Uss Shares the operation with DSS. Operation gets ACCEPTED.
4. Mock USS notifies the operational details of the operation to USS-Under-Test with valid data as per spec.
5. Mock USS records the interaction response of the USS-Under-Test.
6. Uss Qualifier GETs the interaction record from Mock Uss.
7. If USS-Under-Test response is other than 200, then the check fails.


### Test Case 2 - Invalid intent by Mock Uss (missing field/ wrong value type)
1. Setup - USS-Under-Test is subscribed in the area.
2. UssQualifier injects an intent for Mock Uss to submit an operation.
3. [*](##*) Mock Uss Shares the operation with DSS. Operation gets ACCEPTED.
4. Mock USS notifies the operational details of the operation to USS-Under-Test with invalid data as per spec.
5. Mock USS records the interaction response of the USS-Under-Test.
6. Uss Qualifier GETs the interaction record from Mock Uss.
7. If USS-Under-Test response is other than 400, then the check fails

### Test Case 3 - Valid Intent notified in Activated state
1. [*](##*) Test Case 1 steps as setup.
2. [*](##*) Uss Qualifier signals Mock Uss to Activate the operation.
3. [*](##*) Mock USS shares the Operation state change with DSS.
4. [*](##*) Mock USS Activates the op.
5. Mock USS notifies the Test Uss with valid intent.
6. Mock USS records the interaction response of the USS-Under-Test.
7. Uss Qualifier GETs the interaction record from Mock Uss.
8. If USS-Under-Test response is other than 200, then the check fails.


### Test Case 4 - Invalid fields in the Intent notified in Activated state
1. [*](##*) Test Case 1 steps as setup.
2. [*](##*) Uss Qualifier signals Mock Uss to Activate the operation.
3. [*](##*) Uss Qualifier shares the Operation state change with DSS.
4. [*](##*) Mock USS Activates the op.
5. Mock USS notifies the Test Uss with invalid intent.
6. Mock USS records the interaction response of the USS-Under-Test.
7. Uss Qualifier GETs the interaction record from Mock Uss.
8. If USS-Under-Test response is other than 400, then the check fails.


### Test Case 5 - Invalid fields in the Intent in NonConforming state
... To get in a nonconforming state Would need Uss qualifier interface spec to add position injection endpoint.
However, if we have an endpoint in mock_uss for direct submission to subscribed USSes, we can do this test without
injecting positions.

---------------------------------------------------------------
## Validation of operational intent shared by USS-Under-Test

1. Setup - Mock uss is subscribed in the area.
2. Uss qualifier injects an intent for USS-Under-Test to submit an operation.
3. USS-Under-Test shares the operation with DSS. Operation gets ACCEPTED.
4. USS-Under-Test notifies the operational details of the ACCEPTED operation to mock uss.
5. Mock Uss validates the operational intent submitted to it, as per the spec, and returns a response accordingly.
6. Mock Uss records this interaction query.
7. UssQualifier GETs the interaction record from mock uss.
8. If mock uss response in interaction contains a non-200 the test fails.
   1. The mock_uss tests for the missing fields per spec, value types, value range to give a 200 response.
   2. If mock_uss gives 200, the Uss qualifier checks the interaction for the operational intent that Uss-Under-Test
   notified mock_uss, in order to verify the values are as per what was injected in the USS-Under-Test. If the values do
   not match the test fails.

Notes -
####* Alternative to submitting operations to DSS from mock_uss
We dont need to submit operations to DSS from mock_uss. If we can have an endpoint in mock_uss,
where we can submit an intent in a particular state directly for announcement to USS-under-test in the subscription area.


#### Check with Ben if this test needs to go under file [validate_shared_operational_intent.md](./validate_shared_operational_intent.md)

