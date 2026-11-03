# Robot Commissioning

Commissioning registers a new Atlas unit with a Fleet Manager and teaches it the site map. Allow about 30 minutes per robot.

## Pairing

Power on the robot and wait for the status ring to turn blue. Connect a laptop to the robot's service hotspot, open `http://192.168.4.1`, and enter the Fleet Manager address, the robot Wi-Fi credentials and the site identifier. The robot reboots, joins the site network and appears in the Operator Console as "pending". An administrator approves it there and assigns a fleet name such as ATLAS-07.

## Map alignment

A robot does not need to build its own map. The site map is maintained once on the Fleet Manager and pushed to every robot. During commissioning the robot has to be placed on a marked alignment spot and told its initial pose in the Operator Console; after that, localisation runs continuously from the lidar.

## Payload calibration

Each robot calibrates its lifting deck against a reference weight supplied with the unit. Skipping this step makes the overload protection trip early and causes the robot to refuse heavy loads, which is a frequent cause of "payload rejected" tickets.

## Acceptance test

Finish with the built-in acceptance test, which drives a loop through the site at full speed, triggers the safety fields with a test target, and docks for charging. The test report is stored on the Fleet Manager and should be attached to the handover document.
