# Usage Guide

## Quick start

```python
import asyncio

from pydrawise import Auth, Hydrawise


async def main():
    # Create a Hydrawise object and authenticate with your credentials.
    h = Hydrawise(Auth("username", "password"))

    # List the controllers attached to your account.
    controllers = await h.get_controllers()

    # List the zones controlled by the first controller.
    zones = await h.get_zones(controllers[0])

    # Start the first zone.
    await h.start_zone(zones[0])


if __name__ == "__main__":
    asyncio.run(main())
```

## Choosing a client

Pydrawise ships four client implementations, all of which implement the same
[`HydrawiseBase`][pydrawise.HydrawiseBase] interface:

| Client | Auth | Transport | When to use |
| --- | --- | --- | --- |
| [`Hydrawise`][pydrawise.Hydrawise] | [`Auth`][pydrawise.Auth] (username/password) | GraphQL | Default choice. Full-featured, asynchronous. |
| [`HybridClient`][pydrawise.hybrid.HybridClient] | [`HybridAuth`][pydrawise.auth.HybridAuth] (username/password + API key) | GraphQL, falling back to REST | Applications that poll frequently (e.g. Home Assistant) and want to stay within Hydrawise's GraphQL rate limits. |
| [`RestClient`][pydrawise.rest.RestClient] | [`RestAuth`][pydrawise.auth.RestAuth] (API key only) | REST v1 | You only have an API key, or don't need the features that require GraphQL (sensors, water reports, deleting a specific suspension). |
| [`LegacyHydrawise`][pydrawise.legacy.LegacyHydrawise] | API key only | REST v1 | Synchronous, drop-in replacement for [hydrawiser](https://github.com/ptcryan/hydrawiser). |

## Zone control

```python
# Run a zone for its default configured duration.
await h.start_zone(zone)

# Run a zone for a custom duration (in seconds).
await h.start_zone(zone, custom_run_duration=600)

# Stop a zone that's currently running.
await h.stop_zone(zone)

# Start or stop every zone on a controller at once.
await h.start_all_zones(controller, custom_run_duration=600)
await h.stop_all_zones(controller)
```

## Suspending and resuming zones

```python
from datetime import datetime, timedelta

# Suspend a single zone for 24 hours (e.g. because of a rain forecast).
until = datetime.now() + timedelta(days=1)
await h.suspend_zone(zone, until)
await h.resume_zone(zone)

# Suspend or resume every zone on a controller.
await h.suspend_all_zones(controller, until)
await h.resume_all_zones(controller)

# A zone can have multiple suspensions in effect; list and remove one specifically.
zones = await h.get_zones(controller)
for suspension in zones[0].suspensions:
    await h.delete_zone_suspension(suspension)
```

## Sensors and water usage

```python
from datetime import datetime, timedelta

controllers = await h.get_controllers(fetch_sensors=True)
controller = controllers[0]
sensors = await h.get_sensors(controller)

start = datetime.now() - timedelta(days=7)
end = datetime.now()

# Water flow reported by a specific flow sensor.
flow_summary = await h.get_water_flow_summary(controller, sensors[0], start, end)
print(f"{flow_summary.total_water_volume.value} {flow_summary.total_water_volume.unit}")

# Individual watering events (start/end time, duration, water used, why it stopped).
for entry in await h.get_watering_report(controller, start, end):
    run = entry.run_event
    print(f"{run.zone.name}: {run.reported_duration} starting {run.reported_start_time}")

# Aggregate water use across all zones, broken down by zone id.
summary = await h.get_water_use_summary(controller, start, end)
print(f"Active watering time: {summary.total_active_time}")
for zone_id, use in summary.active_use_by_zone_id.items():
    print(f"  zone {zone_id}: {use} {summary.unit}")
```

## Using the hybrid client

[`HybridClient`][pydrawise.hybrid.HybridClient] prefers the GraphQL API but
falls back to (and caches results from) the REST API once its GraphQL
throttle budget is exhausted. It implements the same interface as
[`Hydrawise`][pydrawise.Hydrawise], so it's a drop-in replacement for
applications that poll on a fixed interval:

```python
from pydrawise import Auth
from pydrawise.auth import HybridAuth
from pydrawise.hybrid import HybridClient

auth = HybridAuth("username", "password", "api_key")
h = HybridClient(auth)
controllers = await h.get_controllers()
```

## Using the REST-only client

If you only have a Hydrawise API key (no username/password), use
[`RestClient`][pydrawise.rest.RestClient] instead. Note that a handful of
methods aren't available through the v1 REST API and always raise
`NotImplementedError`: `get_controller`, `get_zone`,
`delete_zone_suspension`, `get_sensors`, `get_water_flow_summary`,
`get_watering_report`, and `get_water_use_summary`.

```python
from pydrawise.auth import RestAuth
from pydrawise.rest import RestClient

h = RestClient(RestAuth("api_key"))
controllers = await h.get_controllers()
```

## Handling errors

All pydrawise exceptions derive from [`Error`][pydrawise.Error]:

```python
from pydrawise import Auth, Hydrawise, NotAuthorizedError, ThrottledError, MutationError

h = Hydrawise(Auth("username", "password"))

try:
    await h.start_zone(zone)
except NotAuthorizedError:
    print("Invalid credentials.")
except ThrottledError:
    # Raised by HybridClient when a request is throttled and no cached
    # result is available yet.
    print("Rate limited; try again later.")
except MutationError as e:
    print(f"Hydrawise rejected the request: {e}")
```
