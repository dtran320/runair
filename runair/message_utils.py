import os

from flask import Flask
from flask_redis import FlaskRedis

from .poll_air_and_notify import AREAS
from .twilio_utils import send_runair_sms

# See .env.example for required environment variables
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

app.config['REDIS_URL'] = os.getenv("REDIS_URL")

redis_client = FlaskRedis(app, decode_responses=True)


def get_all_numbers():
    """Return all numbers subscribed to alerts."""
    pipe = redis_client.pipeline()
    for area_name, area in AREAS.items():
        pipe.smembers(area_name)
    return set.union(*pipe.execute())


def message_all_numbers(message):
    """Message all numbers subscribed to alerts."""
    numbers = get_all_numbers()
    for number in numbers:
        send_runair_sms(number, message)
    print("Successfully sent {} messages!".format(len(numbers)))