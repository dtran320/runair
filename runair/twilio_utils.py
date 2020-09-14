import os

from twilio.rest import Client

# See .env.example for required environment variables
from dotenv import load_dotenv
load_dotenv()

RUNAIR_NUMBER = os.getenv('RUNAIR_NUMBER', '+13198786247')


def get_twilio_client():
    return Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))


def send_runair_sms(to_number, body, media_url=None):
    return send_sms(to_number=to_number, from_number=RUNAIR_NUMBER, body=body, media_url=media_url)


def send_sms(to_number, from_number, body, media_url=None):
    client = get_twilio_client()
    if media_url is None:
        media_url = []
    try:
        client.messages.create(
            body=body,
            from_=from_number,
            to=to_number,
            media_url=media_url,
        )
    except TwilioRestException as exception:
        # Check for invalid mobile number error from Twilio
        if exception.code == 21614:
            print("Uh oh, looks like this caller can't receive SMS messages.")

