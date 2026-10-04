# Defining jobs

A job is described in a YAML file with a name, a command, and a schedule. Place job files in the jobs directory and Orbit loads them automatically.

## Schedules

Schedules use cron syntax, for example `0 3 * * *` runs a job every day at 3 AM. You can also use shortcuts such as @hourly and @daily.

## Retries and timeouts

If a job fails, Orbit retries it up to three times with exponential backoff. The default timeout is 30 minutes; set `timeout` in the job file to change it. A job that exceeds its timeout is killed and marked as failed.

## Environment variables

Secrets such as API tokens should be passed through environment variables, not written in the job file. Use the `env` block to reference variables from the host or from the secrets store.
