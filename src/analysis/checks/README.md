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


## Battery Brownout

FRC batteries are nominally `12V` and the main breaker is nominally `120A`. In practice, the battery becomes discharged throughout the match (lowering initial voltage) and the breaker trip time chart actually allows `240A` of current for short bursts (<10s). Combine this with the internal resistance of the battery and the voltage drop during peak current events can brownout the CPU (i.e. roborio) on the robot, which occurs officially at `6.75V`.

In practice, the logs are subject to sampling error, so the roborio's brownout protection (when power to motors is killed to free up voltage for the rio) can kick in before or without the voltage reaching brownout according to the logs. Typically brownouts are very momentary (<0.1s), owing to a spike in current draw as the robot accelerates and a let up as brownout protection kicks in. This back and forth can create a stutter that can generate lots of "positive" intervals and make the robot undrivable without lowering current limits on the motor controllers.

The brownout detection log cheking tool is designed with these facts in mind. It will report all instances of actual brownout, along with a list of intervals where brownout occurred. In case of no actual brownout, it will still return a list of all intervals where the battery voltage entered the brownout warning stage. If the battery never reaches the warning level then the checks pass.

Due to lack of measurement precision and desire to keep nerarby brownouts as one event, the intervals are padded to end an extra 0.1s after the voltage recovers from the brownout warning zone.