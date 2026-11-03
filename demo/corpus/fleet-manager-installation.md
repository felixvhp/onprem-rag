# Fleet Manager Installation

The Fleet Manager runs on a single Linux server on the customer's network. This page covers a fresh installation; upgrades are described on the Upgrade Procedure page.

## Requirements

The server needs 8 CPU cores, 32 GB of memory and 500 GB of SSD storage for a fleet of up to 40 robots. Ubuntu 22.04 LTS is the supported operating system. The server must be reachable from the robot Wi-Fi network on TCP port 7700 and from operator workstations on TCP port 443.

## Installation steps

Download the installer bundle for the release train you are deploying and verify its checksum. Run the installer as root with the site identifier provided by Halden support, for example `sudo ./halden-fleet-install --site HAL-0421`. The installer creates the `fleet` system user, installs the PostgreSQL database, and registers the `halden-fleet` service with systemd. First start takes about three minutes while the database schema is created.

## Licensing

The Fleet Manager refuses robot connections until a licence file is placed in `/etc/halden/licence.key`. Licences are bound to the site identifier and list the maximum number of robots. A licence that is within 30 days of expiry triggers a warning banner in the Operator Console.

## Verifying the installation

Open the Operator Console at `https://<server>/console` and log in with the initial administrator account. The dashboard should show the site identifier, the release version and zero connected robots. Then follow the Robot Commissioning page to add the first robot.
