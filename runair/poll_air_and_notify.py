import os
import json
import time
import datetime

from flask import Flask
from flask_redis import FlaskRedis
import requests

from .twilio_utils import send_runair_sms

# See .env.example for required environment variables
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

app.config['REDIS_URL'] = os.getenv("REDIS_URL")

redis_client = FlaskRedis(app, decode_responses=True)


AREAS = json.load(open("data/areas.json"))

try:
    ACCEPTABLE_AQI = int(os.getenv("ACCEPTABLE_AQI", 100))
except ValueError:
    ACCEPTABLE_AQI = 100

try:
    GOOD_AQI = int(os.getenv("GOOD_AQI", 50))
except ValueError:
    GOOD_AQI = 50

NOTIFICATION_INTERVAL_S = 60 * 60 * 24

ALERTS = [
    {
        'threshold': GOOD_AQI,
        'key': 'last-notified-good',
        'message': "AQI at {} is now {} 💚 (US EPA)! Green means GOOOO 🟢 \n{}\n{}",
    },
    {
        'threshold': ACCEPTABLE_AQI,
        'key': 'last-notified',
        'message': "AQI at {} is now {} 💛 (US EPA)! Please still exercise caution!\n{}\n{}",
    },
]


# From Purple
# r.prototype.aqiFromPM = function(t) {
#             return t < 0 ? t : 350.5 < t ? n(t, 500, 401, 500, 350.5) : 250.5 < t ? n(t, 400, 301, 350.4, 250.5) : 150.5 < t ? n(t, 300, 201, 250.4, 150.5) : 55.5 < t ? n(t, 200, 151, 150.4, 55.5) : 35.5 < t ? n(t, 150, 101, 55.4, 35.5) : 12.1 < t ? n(t, 100, 51, 35.4, 12.1) : 0 <= t ? n(t, 50, 0, 12, 0) : -1
#         }
#         ,
# https://github.com/SANdood/homebridge-purpleair/blob/master/index.js#L178

PM_AND_AQI_RANGES = {
    350.5: [350.5, 500, 401, 500],
    250.5: [250.5, 350.4, 301, 400],
    150.5: [150.5, 250.4, 201, 300],
    55.5: [55.5, 150.4, 151, 200],
    35.5: [35.5, 55.4, 101, 150],
    12.0: [12.0, 35.4, 51, 100],
    0.0: [0.0, 11.9, 1, 50],
}


def pm_to_aqi(pm_val, pm_low, pm_high, aqi_low, aqi_high):
    """PM2.5 reading to AQI via https://forum.airnowtech.org/t/the-aqi-equation/169"""
    aqi_range = aqi_high - aqi_low
    pm_range = pm_high - pm_low
    scale_factor = aqi_range / pm_range

    return (pm_val - pm_low) * scale_factor + aqi_low


# TODO 2020-09-15 Add some tests for this using known values
# See https://github.com/skalnik/aqi-wtf/blob/450ffb9163f840e101ee50e8ec7f658f99e5712a/app.js#L233
def calculate_aqi(pm):
    """PM2.5 reading to AQI via The AQI equation https://forum.airnowtech.org/t/the-aqi-equation/169"""
    if pm > 500:
        return 500
    for pm_range_low in [350.5, 250.5, 150.5, 55.5, 35.5, 12.0, 0]:
        if pm >= pm_range_low:
            return pm_to_aqi(pm, *PM_AND_AQI_RANGES[pm_range_low])
    return 0.0


def to_aqandu(val):
    return .778 * val + 2.65


# From https://www.reddit.com/r/PurpleAir/comments/irs1j7/any_api_usage_tips_examples/
def to_lrapa(val):
    return 0.5 * val - 0.66


# From PurpleAir Site
# See Paper: https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=349513&Lab=CEMM&simplesearch=0&showcriteria=2&sortby=pubDate&timstype=&datebeginpublishedpresented=08/25/2018
def to_us_epa(pm25_cf1, humidity):
    return 0.534 * pm25_cf1 - 0.0844 * humidity + 5.604


def add_number_for_areas(number, areas):
    for area in areas:
        if area not in AREAS:
            print("Bad area: {}".format(area))
        redis_client.sadd(area, number)
        print("Added {} for area {}".format(number, area))
    send_runair_sms(
        number,
        "Welcome to Runair 🟢🏃🏻‍♀️! You're all set to receive alerts the first time the AQI drops below {}💛 and {}💚 each 24-hour period (according to LRAPA conversion, powered by PurpleAir) for the following areas:\n{}".format(
            ACCEPTABLE_AQI, GOOD_AQI, '\n'.join(areas)
        )
    )


def poll_air_and_notify():
    for area_name, area in AREAS.items():
        sensor_ids = area['sensors']
        notify_numbers = redis_client.smembers(area_name)
        area_aqis = {}
        for sensor_id in sensor_ids:
            # TODO 2020-09-17 Check timestamps for offline sensors!
            url_to_poll = "https://www.purpleair.com/json?show={}".format(sensor_id)
            resp = requests.get(url_to_poll)
            if resp.status_code != 200:
                print("Couldn't get AQI info from Purple for sensor {}".format(sensor_id))
                continue

            result_json = resp.json()
            results = result_json['results']
            if not results:
                print("No results for sensor {}".format(sensor_id))
                continue
            result = results[0]
            try:
                humidity = float(result['humidity'])
            except (IndexError, ValueError):
                print("Couldn't get humidity for sensor {}".format(sensor_id))
                continue
            try:
                location_label = result['Label']
            except IndexError as e:
                print(e)
                location_label = "Sensor {}".format(sensor_id)
            # TODO 2020-10-07: Double-check this?
            # Slides say PA_cf1(avgAB)] = PurpleAir higher correction factor data averaged from the A and B channels
            pm25s = []
            for r in results:
                try:
                    pm25 = float(r['pm2_5_cf_1'])
                except (IndexError, ValueError):
                    print("Couldn't get PM2.5 CF=1 for sensor {}".format(sensor_id))
                    continue
                pm25s.append(pm25)
                print("PM 2.5 CF=1: {:2f}, sensor {}".format(pm25, r.get('Label', 'Unknown channel')))
            pm25 = sum(pm25s) / len(pm25s)
            print("PM2.5 CF=1 of {:2f}, humidity = {}".format(pm25, humidity))
            aqi = int((calculate_aqi(to_us_epa(pm25, humidity))))
          
            print("US-EPA from {}: {}".format(location_label, aqi))
            area_aqis[location_label] = aqi

        area_aqis_vals = area_aqis.values()
        avg_aqi = int(sum(area_aqis_vals) / len(area_aqis_vals))
        print("Average AQI for {}: {}".format(area_name, avg_aqi))

        now_timestamp = int(time.time())
        for alert in ALERTS:
            if avg_aqi < alert['threshold']:
                now_timestamp = int(time.time())
                try:
                    last_notified = int(redis_client.get('{}:{}'.format(area_name, alert['key'])))
                except (TypeError, ValueError):
                    last_notified = None
                if not last_notified or last_notified < now_timestamp - NOTIFICATION_INTERVAL_S:
                    purple_link = area['link'].format(sensor_id)
                    success_str = alert['message'].format(
                        area_name, avg_aqi, '\n'.join(['{}: {}'.format(name, val) for name, val in area_aqis.items()]),
                        purple_link)
                    print(success_str)
                    last_notified_dt = datetime.datetime.fromtimestamp(now_timestamp)
                    redis_client.set('{}:{}'.format(area_name, alert['key']), now_timestamp)
                    print("Updated last notified to {}".format(last_notified_dt.isoformat(sep=' ')))
                    for number in notify_numbers:
                        print("Sending text to {}".format(number))
                        send_runair_sms(number, body=success_str)
                else:
                    last_notified_dt = datetime.datetime.fromtimestamp(last_notified)
                    print("Not notifiying for {} because we last notified at {}".format(
                        area_name, last_notified_dt.isoformat(sep=' ')))
                break
        print("\n----\n")
