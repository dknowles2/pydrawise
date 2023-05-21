# Pydrawise

[![Build and Test](https://github.com/dknowles2/pydrawise/workflows/Build%20and%20Test/badge.svg)](https://github.com/dknowles2/pydrawise/actions/workflows/build-and-test.yml)
[![pypi version](https://img.shields.io/pypi/v/pydrawise.svg)](https://pypi.python.org/pypi/pydrawise)
[![docs](https://readthedocs.org/projects/pydrawise/badge/?version=latest)](https://pydrawise.readthedocs.io/en/latest/?badge=latest)

Pydrawise is an asynchronous Python 3 library for interacting with Hydrawise sprinkler controllers.

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
    zones = await h.get_zones(controllers[0])

    # Start the first zone.
    await h.start_zone(zones[0])


if __name__ == "__main__":
    asyncio.run(main())
```

## Installation

### Pip

To install pydrawse, run this command in your terminal:

```sh
$ pip install pydrawise
```

### Source code

Pydrawise is actively developed on Github, where the code is [always available](https://github.com/dknowles2/pydrawise).

You can either clone the public repository:

```sh
$ git clone https://github.com/dknowles2/pydrawise
```

Or download the latest [tarball](https://github.com/dknowles2/pydrawise/tarball/main):

```sh
$ curl -OL https://github.com/dknowles2/pydrawise/tarball/main
```

Once you have a copy of the source, you can embed it in your own Python package, or install it into your site-packages easily:

```sh
$ cd pydrawise
$ python -m pip install .
```
