from unittest import mock

from pytest import fixture

from pydrawise.schema import Controller, Sensor, User, Zone
from pydrawise.schema_utils import deserialize


@fixture
def rain_sensor(rain_sensor_json):
    yield deserialize(Sensor, rain_sensor_json)


@fixture
def rain_sensor_json():
    yield {
        "id": 337844,
        "name": "Rain sensor ",
        "model": {
            "id": 3318,
            "name": "Rain Sensor (normally closed wire)",
            "active": True,
            "offLevel": 1,
            "offTimer": 0,
            "delay": 0,
            "divisor": 0,
            "flowRate": 0,
            "sensorType": "LEVEL_CLOSED",
        },
        "status": {
            "waterFlow": None,
            "active": False,
        },
    }


@fixture
def flow_sensor_json():
    yield {
        "id": 337845,
        "name": "Flow meter",
        "model": {
            "id": 3324,
            "name": "1, 1½ or 2 inch NPT Flow Meter",
            "active": True,
            "offLevel": 0,
            "offTimer": 0,
            "delay": 0,
            "divisor": 0.52834,
            "flowRate": 3.7854,
            "sensorType": "FLOW",
        },
        "status": {
            "waterFlow": {
                "value": 542.0042035155608,
                "unit": "gal",
            },
            "active": None,
        },
    }


@fixture
def flow_summary_json(request):
    if request.param:
        yield {"totalWaterVolume": {"value": 23134.67952992029, "unit": "gal"}}
    else:
        yield None


@fixture
def user(user_json):
    yield deserialize(User, user_json)


@fixture
def user_json(controller_json):
    yield {
        "id": 1234,
        "customerId": 2222,
        "name": "My Name",
        "email": "me@asdf.com",
        "controllers": [controller_json],
    }


@fixture
def controller(controller_json):
    yield deserialize(Controller, controller_json)


@fixture
def controller_json(rain_sensor_json, flow_sensor_json):
    yield {
        "id": 9876,
        "name": "Main Controller",
        "softwareVersion": "s0",
        "hardware": {
            "serialNumber": "A0B1C2D3",
            "version": "1.0",
            "status": "All good!",
            "model": {
                "name": "HPC 10",
                "description": "HPC 10 Station Controller",
            },
            "firmware": [{"type": "A", "version": "1.0"}],
        },
        "lastContactTime": {
            "timestamp": 1672531200,
            "value": "Sun, 01 Jan 23 00:12:00",
        },
        "lastAction": {
            "timestamp": 1672531200,
            "value": "Sun, 01 Jan 23 00:12:00",
        },
        "online": True,
        "sensors": [rain_sensor_json, flow_sensor_json],
        "permittedProgramStartTimes": [],
        "status": {
            "summary": "All good!",
            "online": True,
            "actualWaterTime": {"value": 10},
            "normalWaterTime": {"value": 10},
            "lastContact": {
                "timestamp": 1672531200,
                "value": "Sun, 01 Jan 23 00:12:00",
            },
        },
    }


@fixture
def zone(zone_json):
    yield deserialize(Zone, zone_json)


@fixture
def zone_json():
    yield {
        "id": 0x10A,
        "number": {
            "value": 1,
            "label": "One",
        },
        "name": "Zone A",
        "wateringSettings": {
            "fixedWateringAdjustment": 100,
            "cycleAndSoakSettings": None,
            "advancedProgram": {
                "id": 4729361,
                "name": "",
                "schedulingMethod": {"value": 0, "label": "Time Based"},
                "monthlyWateringAdjustments": [
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                    100,
                ],
                "appliesToZones": [
                    {
                        "id": 5955343,
                        "number": {"value": 1, "label": "Zone 1"},
                        "name": "Front Lawn",
                    }
                ],
                "zoneSpecific": True,
                "advancedProgramId": 5655942,
                "wateringFrequency": {
                    "label": "Frequency",
                    "period": {
                        "value": None,
                        "label": "Every Program Start Time",
                    },
                    "description": (
                        "Every Program Start Time unless modified by your "
                        "Watering Triggers"
                    ),
                },
                "runTimeGroup": {
                    "id": 49923604,
                    "name": None,
                    "duration": 20,
                },
            },
        },
        "scheduledRuns": {
            "summary": "",
            "currentRun": None,
            "nextRun": None,
            "status": None,
        },
        "pastRuns": {"lastRun": None, "runs": []},
        "status": {
            "relativeWaterBalance": 0,
            "suspendedUntil": {
                "timestamp": 1672531200,
                "value": "Sun, 01 Jan 23 00:12:00",
            },
        },
        "suspensions": [],
    }


@fixture
def watering_report_json():
    yield {
        "watering": [
            {
                "runEvent": {
                    "id": "35220026902",
                    "zone": {
                        "id": 5955343,
                        "number": {"value": 1, "label": "Zone 1"},
                        "name": "Front Lawn",
                    },
                    "standardProgram": {
                        "id": 343434,
                        "name": "",
                    },
                    "advancedProgram": {"id": 4729361, "name": ""},
                    "reportedStartTime": {
                        "value": "Fri, 01 Dec 23 04:00:00 -0800",
                        "timestamp": 1701432000,
                    },
                    "reportedEndTime": {
                        "value": "Fri, 01 Dec 23 04:20:00 -0800",
                        "timestamp": 1701433200,
                    },
                    "reportedDuration": 1200,
                    "reportedStatus": {
                        "value": 1,
                        "label": "Normal watering cycle",
                    },
                    "reportedWaterUsage": {
                        "value": 34.000263855044786,
                        "unit": "gal",
                    },
                    "reportedStopReason": {
                        "finishedNormally": True,
                        "description": ["Finished normally"],
                    },
                    "reportedCurrent": {"value": 280, "unit": "mA"},
                }
            },
        ]
    }


@fixture
def watering_report_without_sensor_json():
    yield {
        "watering": [
            {
                "runEvent": {
                    "id": "35220026902",
                    "zone": {
                        "id": 5955343,
                        "number": {"value": 1, "label": "Zone 1"},
                        "name": "Front Lawn",
                    },
                    "standardProgram": {
                        "id": 343434,
                        "name": "",
                    },
                    "advancedProgram": {"id": 4729361, "name": ""},
                    "reportedStartTime": {
                        "value": "Fri, 01 Dec 23 04:00:00 -0800",
                        "timestamp": 1701432000,
                    },
                    "reportedEndTime": {
                        "value": "Fri, 01 Dec 23 04:20:00 -0800",
                        "timestamp": 1701433200,
                    },
                    "reportedDuration": 1200,
                    "reportedStatus": {
                        "value": 1,
                        "label": "Normal watering cycle",
                    },
                    "reportedStopReason": {
                        "finishedNormally": True,
                        "description": ["Finished normally"],
                    },
                    "reportedCurrent": {"value": 280, "unit": "mA"},
                }
            },
        ]
    }


@fixture
def customer_details():
    yield {
        "controller_id": 9876,
        "customer_id": 2222,
        "current_controller": "Home Controller",
        "controllers": [
            {
                "name": "Main Controller",
                "last_contact": 1672531200,
                "serial_number": "A0B1C2D3",
                "controller_id": 9876,
                "status": "Unknown",
            },
            {
                "name": "Other Controller",
                "last_contact": 1672531200,
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
                "name": "Zone A",
                "period": 259200,
                "relay": 1,
                "relay_id": 0x10A,
                "run": 1800,
                "stop": 1,
                "time": 5400,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Zone B",
                "period": 259200,
                "relay": 2,
                "relay_id": 0x10B,
                "run": 1788,
                "stop": 1,
                "time": 1,
                "timestr": "Now",
                "type": 106,
            },
            {
                "name": "Zone C",
                "period": 259200,
                "relay": 3,
                "relay_id": 0x10C,
                "run": 1800,
                "stop": 1,
                "time": 1576800000,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Zone D",
                "period": 259200,
                "relay": 4,
                "relay_id": 0x10D,
                "run": 180,
                "stop": 1,
                "time": 335997,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Zone E",
                "period": 259200,
                "relay": 5,
                "relay_id": 0x10E,
                "run": 1800,
                "stop": 1,
                "time": 336177,
                "timestr": "Sat",
                "type": 1,
            },
            {
                "name": "Zone F",
                "period": 259200,
                "relay": 6,
                "relay_id": 0x10F,
                "run": 1800,
                "stop": 1,
                "time": 337977,
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
                    {"id": 0x10A},
                    {"id": 0x10B},
                    {"id": 0x10C},
                    {"id": 0x10D},
                    {"id": 0x10E},
                    {"id": 0x10F},
                ],
                "timer": 0,
                "type": 1,
            }
        ],
        "simRelays": 1,
        "stupdate": 0,
        "time": 1672531200,
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
