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


# TODO 2020-09-14: Move this to json file, Postgres or Redis depending on how we want to accept input from users
AREAS = {
    'Menlo Park': {
        'sensors': [
            '66025',  # Downtown Menlo Park @ University & Florence
            '19391',  # Menlo Atherton
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a1440/cC1&select={}#13.61/37.45215/-122.17725',
    },
    'East Alameda': {
        'sensors': [
            '61609',  # Bayview
            '60025',  # Alameda G's Lab
            '64067',  # Ravenscove
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#13.84/37.75869/-122.24729'
    },
    'West Alameda': {
        'sensors': [
            '61423',  # Ballena Bay
            '36653',  # BBYC Ballena Bay Yacht Club
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#13.84/37.76359/-122.28393'
    },
    'Dogpatch': {
        'sensors': [
            '64777',  # Dogpatch
            '35433',  # Dogpatch Digs
            '38745',  # Dogpatch2
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'SOMA': {
        'sensors': [
            '24223',  # South Beach Marina Apts
            '60019',  # Heron's Nest
            '2910',  # Tactrix rooftop
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Panhandle': {
        'sensors': [
            '17951',  # Lyon St Outside
            '22989',  # Lyon and page
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Golden Gate Park': {
        'sensors': [
            38825,  # Fulton and 12th St
            19159,  # Outer Sunset
            17763,  # MUD Upper Haight
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Ocean Beach': {
        'sensors': [
            1742,  # Outer Sunset - Ocean Beach at Kirkham
            56461,  # 38th and Kirkham
            55933,  # Outer Sunset 46th @ Judah/Kirkham
            17787,  # Outer Sunset Vincente
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Twin Peaks': {
        'sensors': [
            '54407',  # Karl,
            '20989',  # 25th & Grandview
            '65259',  # Midtown Terrace
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Marina': {
        'sensors': [
            '6014',  # Marina Distract SF
            '61185',  # Cow Hollow
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Presidio': {
        'sensors': [
            54129,  # El Polin Springs
            33633,  # 3031 Pacific
            62393,  # 11th & Lake
            52819,  # 1st and Balboa
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.19/37.75304/-122.45169',
    },
    'Tam': {
        'sensors': [
            56245,  # Green Gulch Farm
            20505,  # Tam Valley
            63229,  # Tamalpais Ave Middle Ridge
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.33/37.87731/-122.55398',
    },
    'San Anselmo': {
        'sensors': [
            '9834',  # Redhill South
            '3840',  # San Anselmo
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#13.01/37.95782/-122.57136',
    },
    'San Rafael': {
        'sensors': [
            '53325',  # San Rafael
            '64475',  #Newhall Drive
            '66447',  # 1945 5th SR
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#13.01/37.98143/-122.50923',
    },
    'Ross': {
        'sensors': [
            '27229',  # Ross
            '63153',  # B & R
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#13.3/37.97159/-122.55834'
    },
    'Novato': {
        'sensors': [
            '55335',  # Miss Sandie's School
            '4788',  # The Vistas
            '66347',  # San Marin East
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#12.8/38.08897/-122.57811'
    },
    'Mt. Ashland': {
        'sensors': [
            '30773',  # Mt. Ashland
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#11.09/42.1427/-122.681',
    },
    'Siskiyou Blvd': {
        'sensors': [
            '36263',  # GSI Office/ Siskiyou Blvd Ashland
        ],
        'link': 'https://www.purpleair.com/map?opt=1/i/mAQI/a10/cC1&select={}#11.09/42.1427/-122.681',
    },
}

try:
    ACCEPTABLE_AQI = int(os.getenv("ACCEPTABLE_AQI", 100))
except ValueError:
    ACCEPTABLE_AQI = 100

try:
    GOOD_AQI = int(os.getenv("GOOD_AQI", 50))
except ValueError:
    GOOD_AQI = 50

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
        "Welcome to Runair 🟢🏃🏻‍♀️! You're all set to receive alerts the first time the AQI drops below {}💛 and {}💚 each 24-hour period (according to AQandU conversion, powered by PurpleAir) for the following areas:\n{}".format(
            ACCEPTABLE_AQI, GOOD_AQI, '\n'.join(areas)
    ))


def poll_air_and_notify():
    for area_name, area in AREAS.items():
        sensor_ids = area['sensors']
        notify_numbers = redis_client.smembers(area_name)
        area_aqis = {}
        area_aqis_10m = {}
        for sensor_id in sensor_ids:
            url_to_poll = "https://www.purpleair.com/json?show={}".format(sensor_id)
            resp = requests.get(url_to_poll)
            if resp.status_code != 200:
                print("Couldn't get AQI info from Purple for sensor {}".format(sensor_id))
                continue
            avg_pms = []
            avg_pms_10m = []
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
                    try:
                        avg_10m = json.loads(r['Stats'])['v1']
                    except:
                        avg_10m = r['PM2_5Value']
                    avg_pms_10m.append(float(avg_10m))
                    print("Adding PM2.5 reading from {}: {}, 10-min avg: {}".format(r['Label'], r['PM2_5Value'], avg_10m))
            avg_pm = sum(avg_pms) / len(avg_pms)
            avg_pm_10m = sum(avg_pms_10m) / len(avg_pms_10m)
            print("Average PM2.5 of {}: {:2f}".format(', '.join(['{:2f}'.format(a) for a in avg_pms]), avg_pm))
            aqi = int((calculate_aqi(to_aqandu(avg_pm))))
            aqi_10m = int((calculate_aqi(to_aqandu(avg_pm_10m))))
            try:
                location_label = labels[0]
            except:
                location_label = "Sensor {}".format(sensor_id)
            print("AQandU from {}: {} (10-min avg: {})".format(location_label, aqi, aqi_10m))
            area_aqis[location_label] = aqi
            area_aqis_10m[location_label] = aqi_10m
        area_aqis_vals = area_aqis.values()
        area_aqis_10m_vals = area_aqis_10m.values()
        avg_aqi = int(sum(area_aqis_vals)/len(area_aqis_vals))
        avg_aqi_10m = int(sum(area_aqis_10m_vals)/len(area_aqis_10m_vals))
        print("Average AQI for {}: {} (10-min avg: {})".format(area_name, avg_aqi, avg_aqi_10m))
        if avg_aqi < GOOD_AQI:
            now_timestamp = int(time.time())
            try:
                last_notified = int(redis_client.get('{}:last-notified-good'.format(area_name)))
            except (TypeError, ValueError):
                last_notified = None
            if not last_notified or last_notified < now_timestamp - NOTIFICATION_INTERVAL_S:
                purple_link = area['link'].format(sensor_id)
                success_str = "AQI at {} is now {} 💚 (AQandU), 10-min avg: {}! Green means GOOOO 🟢 \n{}\n{}".format(
                    area_name, avg_aqi, avg_aqi_10m, '\n '.join(['{}: {} (10-min avg: {})'.format(name, val, area_aqis_10m.get(name, val)) for name, val in area_aqis.items()]),
                    purple_link)
                print(success_str)
                last_notified_dt = datetime.datetime.fromtimestamp(now_timestamp)
                redis_client.set('{}:last-notified-good'.format(area_name), now_timestamp)
                print("Updated last notified to {}".format(last_notified_dt.isoformat(sep=' ')))
                for number in notify_numbers:
                    print("Sending text to {}".format(number))
                    send_runair_sms(number, body=success_str)
            else:
                last_notified_dt = datetime.datetime.fromtimestamp(last_notified)
                print("Not notifiying for {} because we last notified at {}".format(
                    area_name, last_notified_dt.isoformat(sep=' ')))
        elif avg_aqi < ACCEPTABLE_AQI:
            now_timestamp = int(time.time())
            try:
                last_notified = int(redis_client.get('{}:last-notified'.format(area_name)))
            except (TypeError, ValueError):
                last_notified = None
            if not last_notified or last_notified < now_timestamp - NOTIFICATION_INTERVAL_S:
                purple_link = area['link'].format(sensor_id)
                success_str = "AQI at {} is now {} 💛 (AQandU), 10-min avg: {}! Please still exercise caution!\n{}\n{}".format(
                    area_name, avg_aqi, avg_aqi_10m, '\n '.join(['{}: {} (10-min avg: {})'.format(name, val, area_aqis_10m.get(name, val)) for name, val in area_aqis.items()]),
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
