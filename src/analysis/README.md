# Precomputed Log Checks

The precomputed log checks are checks run on the raw wpilog data to check for known issues that may arrise during the match. These checks are designed to be auto calculated upon uploading of the log file and are then available in a the log summary page.

Log check results are classified into four categories
1. ok - all checks passed
2. warning - there is something of convern but it may not be critical to in match performance
3. fail - a critical failure occurred and the robot likely needs repair to fic the problem
4. not_applicable - the log does not contain information to run the check

Below I describe which logs are checked and how those checks are implemented.

## CAN bus utilization

CAN bus utilization is an obvious starting point for a l


### Zero-Order-Hold Integration

a sample's value is held constant until the next sample arrives. When you read 0.98 at t=6.000s, you assume the bus stayed at 0.98 for the entire 20ms until the next sample at t=6.020s replaces it. The value is a flat line ("held") from each sample to the next, creating a staircase shape rather than a smooth curve.
Picture the signal as a step function:
```
value
0.98 ┤    ┌────┐
     │    │    │
0.50 ┤────┘    └────┐
     │              │
0.25 ┤              └────
     └────┬────┬────┬────
        6.00 6.02 6.04   time
```
Each horizontal segment is one sample's value, held flat until the next sample steps it up or down. That's ZOH — a staircase.