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


AREAS = {
    'Tam': {
        'sensors': [
            56245, # Green Gulch Farm
            20505, # Tam Valley
            63229, # Tamalpais Ave Middle Ridge
        ],
        'numbers': redis_client.smembers("Tam"),
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.33/37.87731/-122.55398',
    },
    'Presidio': {
        'sensors': [
            54129, # El Polin Springs
            33633, # 3031 Pacific
            62393, # 11th & Lake
            52819, # 1st and Balboa
        ],
        'numbers': redis_client.smembers("Presidio"),
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Golden Gate Park': {
        'sensors': [
            38825, # Fulton and 12th St
            19159, # Outer Sunset
            17763, # MUD Upper Haight
        ],
        'numbers': redis_client.smembers("Golden Gate Park"),
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Ocean Beach': {
        'sensors': [
            19159, # Outer Sunset
            55933, # Outer Sunset 46th @ Judah/Kirkham
            17787, # Outer Sunset Vincente
        ],
        'numbers': redis_client.smembers("Ocean Beach"),
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    }
}

try:
    ACCEPTABLE_AQI = int(os.getenv("ACCEPTABLE_AQI", 100))
except ValueError:
    ACCEPTABLE_AQI = 100

NOTIFICATION_INTERVAL_S = 60 * 60 * 24


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


def add_number_for_areas(number, areas):
    for area in areas:
        if area not in AREAS:
            print("Bad area: {}".format(area))
        redis_client.sadd(area, number)
        print("Added {} for area {}".format(number, area))
    send_runair_sms(
        number,
        "Welcome to Runair 🟢🏃🏻‍♀️! You're all set to receive an alert when the AQI drops below {} for the following areas:\n{}".format(
        ACCEPTABLE_AQI,
        '\n'.join(areas)
    ))



def poll_air_and_notify():
    for area_name, area in AREAS.items():
        sensor_ids = area['sensors']
        notify_numbers = redis_client.smembers(area_name)
        area_aqis = {}
        for sensor_id in sensor_ids:
            url_to_poll = "https://www.purpleair.com/json?show={}".format(sensor_id)
            resp = requests.get(url_to_poll)
            if resp.status_code != 200:
                print("Couldn't get AQI info from Purple for sensor".format(sensor_id))
                continue
            avg_pms = []
            result_json = resp.json()
            results = result_json['results']
            labels = []
            if not results:
                print("No results for sensor {}".format(sensor_id))
                continue
            for r in results:
                if 'PM2_5Value' in r:
                    avg_pms.append(float(r['PM2_5Value']))
                    labels.append(r['Label'])
                    print("Adding PM2.5 reading from {}: {}".format(r['Label'], r['PM2_5Value']))
            avg_pm = sum(avg_pms) / len(avg_pms)
            print("Average PM2.5 of {}: {:2f}".format(', '.join(['{:2f}'.format(a) for a in avg_pms]), avg_pm))
            aqi = int((calculate_aqi(to_aqandu(avg_pm))))
            try:
                location_label = labels[0]
            except:
                location_label = "Sensor {}".format(sensor_id)
            print("AQandU from {}: {}".format(location_label, aqi))
            area_aqis[location_label] = aqi
        area_aqis_vals = area_aqis.values()
        avg_aqi = int(sum(area_aqis_vals)/len(area_aqis_vals))
        print("Average AQI for {}: {}".format(area_name, avg_aqi))
        if avg_aqi < ACCEPTABLE_AQI:
            now_timestamp = int(time.time())
            try:
                last_notified = int(redis_client.get('{}:last-notified'.format(area_name)))
            except (TypeError, ValueError):
                last_notified = None
            if not last_notified or last_notified < now_timestamp - NOTIFICATION_INTERVAL_S:
                purple_link = area['link'].format(sensor_id)
                success_str = "AQI at {} is now {}! Please still exercise caution!\n{}\n{}".format(
                    area_name, aqi, '\n '.join(['{}: {}'.format(name, val) for name, val in area_aqis.items()]),
                    purple_link)
                print(success_str)
                last_notified_dt = datetime.datetime.fromtimestamp(now_timestamp)
                redis_client.set('{}:last-notified'.format(area_name), now_timestamp)
                print("Updated last notified to {}".format(last_notified_dt.isoformat(sep=' ')))
                for number in notify_numbers:
                    print("Sending text to {}".format(number))
                    send_runair_sms(number, body=success_str)
            else:
                last_notified_dt = datetime.datetime.fromtimestamp(last_notified)
                print("Not notifiying for {} because we last notified at {}".format(
                    area_name, last_notified_dt.isoformat(sep=' ')))
        print("\n----\n")