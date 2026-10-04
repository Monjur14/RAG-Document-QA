# Installing Orbit

Orbit runs on Linux and macOS. Install it with your package manager: run `brew install orbit` on macOS or `apt install orbit` on Debian. Windows is supported only through WSL 2.

## System requirements

Orbit needs 2 GB of RAM and 500 MB of free disk space. A 64-bit CPU is required. The daemon listens on port 7070 by default.

## Upgrading

To upgrade, stop the daemon, install the new package, and start the daemon again. Configuration files are migrated automatically on first start. Always back up the data directory before a major version upgrade.

## Uninstalling

Remove the package with your package manager. The data directory at ~/.orbit is not deleted automatically; delete it manually if you no longer need your job history.
