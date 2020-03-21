import sys
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from pyHS100 import SmartPlug, SmartDeviceException
import argparse
from datetime import datetime
import time

powerPlugAddresses = [
    ['Dishwasher', '192.168.50.104'],
    ['Fridge Freezer', '192.168.50.105'],
    ['Garage Dehumidifier', '192.168.50.103'],
    ['Garage Fridge Freezer', '192.168.50.101'],
    ['Garage Media Server', '192.168.50.106'],
    ['Garage Nest Camera', '192.168.50.107'],
    ['Garage Server', '192.168.50.108'],
    ['Living Room Home Entertainment', '192.168.50.109'],
    ['Network Rack', '192.168.50.110'],
    ['Play Room Home Entertainment', '192.168.50.190'],
    ['Garage Switch', '192.168.50.216'],
    ['Quooker Tap', '192.168.50.111'],
    ['Study', '192.168.50.112'],
    ['Synology DS1513+', '192.168.50.102'],
    ['Synology DS1817+', '192.168.50.100'],
    ['Tumble Dryer', '192.168.50.113'],
    ['Washing Machine', '192.168.50.114']
]

version = 1.0
parser = argparse.ArgumentParser(description="TP-Link Wi-Fi Smart Plug Monitoring Client v" + str(version))
parser.add_argument("-is", "--influxServer", metavar="<influxServer>", required=True, help="Influx Server")
parser.add_argument("-idb", "--influxDb", metavar="<influxDb>", required=True, help="Influx Database")
parser.add_argument("-iusr", "--influxUser", metavar="<influxUser>", required=True, help="Influx Username")
parser.add_argument("-ipass", "--influxPass", metavar="<influxPass>", required=True, help="Influx Password")
args = parser.parse_args()

influxServer = args.influxServer
influxDb = args.influxDb
influxUser = args.influxUser
influxPass = args.influxPass

def gatherStatsAndPost(host, ip, timeNow):
    print('Getting usage for {} ({})'.format(host, ip))
    today = datetime.today()

    plug = SmartPlug(ip)
    # print("Hardware: %s" % pf(plug.hw_info))
    # print("Full sysinfo: %s" % pf(plug.get_sysinfo()))  # this prints lots of information about the device
    # print("Power status: %s" % pf(plug.get_emeter_realtime()))

    hwInfo = plug.hw_info
    sysInfo = plug.get_sysinfo()
    powerStats = plug.get_emeter_realtime()
    dayStats = plug.get_emeter_daily(year=today.year, month=today.month)

    alias = sysInfo['alias']
    hwver = sysInfo['hw_ver']
    swver = sysInfo['sw_ver']

    if hwver == "1.0":
        amps = float(powerStats['current'])
        volts = float(powerStats['voltage'])
        watts = float(powerStats['power'])
        total = float(powerStats['total'])
    elif hwver == "2.0" or hwver == "2.1":
        amps = float(powerStats['current_ma']) / float(1000)
        volts = float(powerStats['voltage_mv']) / float(1000)
        watts = float(powerStats['power_mw']) / float(1000)
        total = float(powerStats['total_wh']) / float(1000)
    else:
        raise ValueError('Invalid hardware version detected: {}, software version: {})'.format(hwver, swver))

    json_body = [
        {
            "measurement": "power_usage",
            "tags": {
                "alias": alias,
                "hwver": hwver,
                "swver": swver
            },
            "time": timeNow,
            "fields": {
                "amps": float(amps),
                "volts": float(volts),
                "watts": float(watts),
                "total": float(total)
            }
        }
    ]

    client = InfluxDBClient(influxServer, 8086, influxUser, influxPass, influxDb)

    # print('Sending instant power usage for {} to influx {}:{}'.format(alias, influxServer, 8086))
    client.write_points(json_body)

    totaltoday = 0

    if today.day in dayStats:
        totaltoday = dayStats[today.day]

    historicjson_body = [
            {
                "measurement": "energy",
                "tags": {
                    "alias": alias,
                    "hwver": hwver,
                    "swver": swver
                },
                "time": timeNow,
                "fields": {
                    "kWh": float(totaltoday)
                }
            }
        ]

    # print('Sending historic power usage for {} to influx {}:{}'.format(alias, influxServer, 8086))
    client.write_points(historicjson_body)

    del historicjson_body
    del json_body
    del client


while True:
    timeNow = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    # print("Checking power usage at {}".format(timeNow))
    for powerPlugAddress in powerPlugAddresses:
        try:
            gatherStatsAndPost(powerPlugAddress[0], powerPlugAddress[1], timeNow)
        except InfluxDBClientError as e:
            print("{}: {} - InfluxDB error: {}".format(timeNow, powerPlugAddress[0], str(e)))
        except SmartDeviceException as e:
            print("{}: {} - SmartDeviceException: {}".format(timeNow, powerPlugAddress[0], str(e)))
        except Exception as e:
            print("{}: {} - Unexpected error: {}".format(timeNow, powerPlugAddress[0], str(e)))
    # print('Finished checking power usage')
    time.sleep(10)
