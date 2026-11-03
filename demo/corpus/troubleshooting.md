# Troubleshooting Guide

This page lists the most common fleet problems, their usual causes and the first thing to try. Open a support ticket with the robot's log bundle if the first fix does not help.

## Robot shows as offline

Nine times out of ten this is Wi-Fi. Check the signal heat map from the site survey for the robot's last known position, and check whether the robot can still be reached on its reserved IP address. If several robots go offline at the same time, check the access point that covers that area and the Fleet Manager's TCP port 7700.

## Localisation lost

The robot stops and its ring blinks amber. This happens when the surroundings differ too much from the site map, for example after racks are moved. Drive the robot to an alignment spot and re-enter its pose, then update the site map on the Fleet Manager so that other robots are not affected.

## Payload rejected

The robot refuses to lift a load it should carry. Run the payload calibration again with the reference weight; if the error persists, the load cell under the deck may be damaged.

## Charging does not start

Make sure the dock's status light is green and that the charging contacts are clean. A robot that approaches a dock but does not charge usually has a misaligned dock; docks must be bolted to the floor and re-taught in the Operator Console after being moved.

## Collecting logs

In the Operator Console, open the robot, choose "Export log bundle" and select the time window. The bundle contains controller logs, safety events and navigation traces and is the first thing Halden support asks for.
