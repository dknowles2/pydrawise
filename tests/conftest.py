from unittest import mock

from pytest import fixture


@fixture
def customer_details():
    yield {
        "controller_id": 52496,
        "customer_id": 47076,
        "current_controller": "Home Controller",
        "controllers": [
            {
                "name": "Home Controller",
                "last_contact": 1693292420,
                "serial_number": "0310b36090",
                "controller_id": 52496,
                "status": "Unknown",
            },
            {
                "name": "Other Controller",
                "last_contact": 1693292420,
                "serial_number": "1310b36091",
                "controller_id": 63507,
                "status": "Unknown",
            },
        ],
    }


@fixture
def status_schedule():
    yield {
        "expanders": [],
        "master": 0,
        "master_post_timer": 0,
        "master_timer": 0,
        "message": "",
        "nextpoll": 60,
        "options": 1,
        "relays": [
            {
                "name": "Drips - House",
                "period": 259200,
                "relay": 1,
                "relay_id": 5965394,
                "run": 1800,
                "stop": 1,
                "time": 5400,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Drips - Fence",
                "period": 259200,
                "relay": 2,
                "relay_id": 5965395,
                "run": 1788,
                "stop": 1,
                "time": 1,
                "timestr": "Now",
                "type": 106,
            },
            {
                "name": "Rotary - Front",
                "period": 259200,
                "relay": 3,
                "relay_id": 5965396,
                "run": 1800,
                "stop": 1,
                "time": 1576800000,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Sprays - Side L",
                "period": 259200,
                "relay": 4,
                "relay_id": 5965397,
                "run": 180,
                "stop": 1,
                "time": 335997,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Rotary - Back N",
                "period": 259200,
                "relay": 5,
                "relay_id": 5965398,
                "run": 1800,
                "stop": 1,
                "time": 336177,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Rotary - Back C",
                "period": 259200,
                "relay": 6,
                "relay_id": 5965399,
                "run": 1800,
                "stop": 1,
                "time": 337977,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Rotary - Back F",
                "period": 259200,
                "relay": 7,
                "relay_id": 5965400,
                "run": 1200,
                "stop": 1,
                "time": 339777,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Sprays - Side R",
                "period": 259200,
                "relay": 8,
                "relay_id": 5965401,
                "run": 480,
                "stop": 1,
                "time": 340977,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Sprays - Drivew",
                "period": 259200,
                "relay": 9,
                "relay_id": 5965402,
                "run": 900,
                "stop": 1,
                "time": 341457,
                "timestr": "Sat",
                "type": 1,
            },
        ],
        "sensors": [
            {
                "input": 0,
                "mode": 1,
                "offtimer": 0,
                "relays": [
                    {"id": 5965394},
                    {"id": 5965395},
                    {"id": 5965396},
                    {"id": 5965397},
                    {"id": 5965398},
                    {"id": 5965399},
                    {"id": 5965400},
                    {"id": 5965401},
                    {"id": 5965402},
                ],
                "timer": 0,
                "type": 1,
            }
        ],
        "simRelays": 1,
        "stupdate": 0,
        "time": 1693303803,
    }


@fixture
def success_status():
    yield {"message": "Successful message", "message_type": "info"}


@fixture
def mock_request(customer_details, status_schedule):
    with mock.patch("requests.get") as req:
        controller_info_resp = mock.Mock(return_code=200)
        controller_info_resp.json.return_value = customer_details
        controller_status_resp = mock.Mock(return_code=200)
        controller_status_resp.json.return_value = status_schedule
        req.side_effect = [controller_info_resp, controller_status_resp]
        yield req
