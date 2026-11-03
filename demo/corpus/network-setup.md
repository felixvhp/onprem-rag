# Network Setup

Reliable Wi-Fi is the single most common source of Atlas fleet problems, so network setup deserves care before the first robot is commissioned.

## Wi-Fi requirements

Robots connect on 5 GHz only. Every point of the operating area needs a signal of at least minus 67 dBm from at least one access point, and roaming between access points must complete in under 150 ms, which in practice means enabling 802.11r fast transition. A dedicated SSID for robots is strongly recommended so that client isolation and bandwidth policies for staff devices do not apply to the fleet.

## Addressing

Robots use DHCP with reservations keyed on their MAC address, so that each unit keeps a stable IP address that appears in logs and in the Operator Console. The Fleet Manager itself needs a static address. Multicast is not required.

## Firewall rules

The robot network must reach the Fleet Manager on TCP 7700 for job traffic and UDP 7701 for position telemetry. Operator workstations reach the Fleet Manager on TCP 443. No inbound connection from the Fleet Manager to a robot is needed except SSH on TCP 22, which support uses for diagnostics and which can be restricted to the server address.

## Site survey

Halden provides a survey tool that runs on an Atlas unit in survey mode and records signal strength along the drive path. Run it after any change to access point placement and keep the resulting heat map with the site documentation.
