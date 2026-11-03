# Atlas AMR Overview

Atlas is Halden Robotics' autonomous mobile robot for warehouse logistics. Each Atlas unit carries up to 600 kg on a lifting deck, navigates with a 2D safety lidar and a 3D depth camera, and receives jobs from the Fleet Manager over Wi-Fi. A typical site runs between 5 and 40 robots on a single Fleet Manager.

## Models

Three models ship today. Atlas 600 is the standard unit with a 600 kg payload and a top speed of 1.8 m/s. Atlas 600 Cold is the same platform rated for freezer operation down to minus 25 degrees Celsius, with heated battery packs and a reduced top speed of 1.2 m/s. Atlas 1200 doubles the payload to 1200 kg and uses a longer chassis, so it needs aisles of at least 1.6 m.

## Battery and charging

All models use a 48 V lithium iron phosphate pack. A full charge takes about 70 minutes at a Halden charging dock and lasts 8 to 10 hours of mixed operation. Robots return to a dock automatically when the state of charge drops below 20 percent, or earlier if the Fleet Manager predicts an idle window.

## Software components

The platform has three software components: the robot controller running on each unit, the Fleet Manager that assigns jobs and resolves traffic, and the Operator Console, a web application for monitoring and manual control. All three are versioned together in a release train named by year and quarter, for example 2025.3.
