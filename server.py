import os

# See .env.example for required environment variables
from dotenv import load_dotenv

from flask import (Flask, jsonify, redirect, render_template)

load_dotenv()

app = Flask(__name__)


@app.route('/', methods=['GET'])
def home():
    return "Welcome to RunAir!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
