# app.py

import os
from flask import Flask
from flask import request, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from config import BaseConfig
from boxsdk import OAuth2
from boxsdk import Client 
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)

from models import *

client = Client(OAuth2(
	client_id='foo',
	client_secret='bar',
	access_token=app.config['ACCESS_TOKEN']))

def get_velocity_stat():
	created_after = datetime.datetime.now(timezone.utc) + datetime.timedelta(minutes=-1)
	created_before = datetime.datetime.now(timezone.utc)
	events = client.events().get_enterprise_events(
		limit=500,
		event_type=['UPLOAD'], 
		created_after=created_after,		
		created_before=created_before)
	velocity = Stat(1, len(events['entries']), created_after, created_before)
	db.session.add(velocity)
	db.session.commit()	

@app.route('/', methods=['GET', 'POST'])
def index():
	stats = Stat.query.order_by(Stat.starting.desc()).all()
	return render_template('index.html', stats=stats)

@app.before_first_request
def initialize():
	get_velocity_stat()
	scheduler = BackgroundScheduler()
	scheduler.start()
	scheduler.add_job(get_velocity_stat, 'interval', minutes=1)

if __name__ == '__main__':
	app.run()