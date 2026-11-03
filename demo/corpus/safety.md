# Safety System

Atlas robots are designed to operate among people. The safety system is independent of the navigation software and cannot be disabled from the Operator Console.

## Safety fields

The safety lidar defines three fields in front of the robot. An intrusion into the warning field slows the robot to 0.5 m/s. An intrusion into the protective field stops it within its braking distance. The fields scale with speed and with payload, and they switch to a narrower set when the robot drives through a doorway marked as such on the site map.

## Emergency stop

Every robot has two emergency stop buttons, one on each side of the chassis. Pressing either cuts drive power immediately and raises an alarm in the Operator Console. The robot stays stopped until the button is released and an operator acknowledges the event on the robot's touch panel. A fleet-wide emergency stop is available in the Operator Console and from an optional wall-mounted button connected to the Fleet Manager.

## Audible and visual signals

Robots sound a short chime before starting to move and a continuous tone while reversing. The status ring shows blue when idle, green when driving, amber when slowed by a warning field intrusion, and red when stopped by the protective field or an emergency stop.

## Periodic checks

The safety fields must be verified with the test target every six months and after any change to the lidar mounting. The Fleet Manager records the date of the last check for every robot and lists overdue units on the maintenance dashboard.
