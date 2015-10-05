# app.py

import os
import logging
from flask import Flask
from flask import request, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from config import BaseConfig

app = Flask(__name__)
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)

from tasks import BackgroundTasks
from models import *


@app.route('/', methods=['GET', 'POST'])
def index():
	stats = Stat.query.order_by(Stat.starting.desc()).all()
	return render_template('index.html', stats=stats)


@app.before_first_request
def init():
	statrec = BackgroundTasks(db, app.logger, app.config['ACCESS_TOKEN'], app.config['REFRESH_TOKEN'])
	statrec.schedule()

if __name__ == '__main__':
	app.run(debug=False, use_reloader=False)