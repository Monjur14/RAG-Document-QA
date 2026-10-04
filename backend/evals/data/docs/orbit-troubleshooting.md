# Troubleshooting

This guide covers common problems. Check the daemon log first; it is at /var/log/orbit/daemon.log.

## Daemon will not start

If the daemon fails to start, the most common cause is that port 7070 is already in use. Change the port with the `listen_port` setting or stop the other program using it.

## Jobs are not running

If a job never runs, verify that its YAML file has no syntax errors by running `orbit validate`. Also confirm that the system clock and time zone are correct, because schedules use the local time zone.

## High memory usage

Memory use grows with the number of jobs kept in history. Lower `history_limit` to keep fewer finished runs; the default is 1000.

## Getting help

Ask questions in the community forum, or open an issue on the project's tracker. Include the output of `orbit version` and the relevant lines from the daemon log.
