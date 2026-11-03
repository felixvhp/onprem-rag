# Release Notes 2025.3

Release train 2025.3 is available for all sites with a current support contract. Upgrade the Fleet Manager first; robots update themselves from the Fleet Manager the next time they dock.

## Highlights

Traffic resolution in narrow aisles has been reworked and reduces waiting time at aisle entrances by around 30 percent on dense sites. The Operator Console gained a maintenance dashboard that lists overdue safety checks and battery health per robot. The Atlas 600 Cold model is now supported in mixed fleets with standard units.

## Fixes

Robots no longer lose their Wi-Fi association when an access point changes channel. The log bundle export now completes for time windows longer than 24 hours. Payload calibration accepts the reference weight on the first attempt when the deck is not fully lowered.

## Known issues

Webhook deliveries can arrive out of order for jobs that change state more than once within a second. A fix is planned for 2025.4. Sites that use the legacy v1 API should migrate to v2 before 2026.1, when v1 will be removed.
