# pydrawise
Python 3 library for interacting with Hydrawise sprinkler controllers.

*Note that this project has no official relationship with Hydrawise or Hunter. Use at your own risk.*

## Usage

```python
import asyncio

from pydrawise import Auth, Hydrawise


async def main():
    # Create a Hydrawise object and authenticate with your credentials.
    h = Hydrawise(Auth("username", "password"))

    # List the controllers attached to your account.
    controllers = await h.get_controllers()

    # List the zones controlled by the first controller.
    zones = await controllers[0].get_zones()
    
    # Start the first zone.
    await zones[0].start()


if __name__ == "__main__":
    asyncio.run(main())
```
