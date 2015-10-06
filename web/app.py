# app.py

import os
import logging
from flask import Flask, request, Response, redirect, render_template, json
from flask.ext.sqlalchemy import SQLAlchemy
from config import BaseConfig

app = Flask(__name__)
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)

from tasks import BackgroundTasks
from box import Box
from models import *


@app.route('/', methods=['GET'])
def index():
	return render_template('index.html')

@app.route('/auth/is_authorized', methods=['GET'])
def is_authorized():
	box = Box(app.logger)
	authed = box.is_authorized()
	return Response(json.dumps(authed), mimetype='application/json')

@app.route('/auth/authorize', methods=['GET','POST'])
def authorize():
	box = Box(app.logger)
	code = request.args.get('code')
	
	if code is None:
		auth_url = box.authorization_url()
		app.logger.debug('redirecting to ' + auth_url)
		return redirect(auth_url, code=302)
		
	app.logger.debug('received auth code')
	box.authorize(code)
	return redirect('/', code=302)

@app.route('/auth/import', methods=['GET'])
def import_tokens():
	box = Box(app.logger)
	box.import_tokens();
	return redirect('/', code=302)

@app.route('/event/file', methods=['GET'])
def velocity_file():
	return render_template('event-file.html')

@app.route('/event/engagement', methods=['GET'])
def velocity_engagement():
	return render_template('event-engagement.html')

@app.route('/event/stat', methods=['GET'])
def velocity():
	result = []
	epoch = datetime.datetime.utcfromtimestamp(0)

	event_types = request.args.get('event_type').split(',')
	for event_type in event_types:
		series = [] 
		stats = Stat.query.filter(Stat.measure == event_type).order_by(Stat.starting.asc()).all()
		for stat in stats:
			series.append([(stat.starting - epoch).total_seconds() * 1000, stat.value])
		result.append(series)
	return Response(json.dumps(result),  mimetype='application/json')


@app.before_first_request
def init():
	app.logger.debug("Init pid {}".format(os.getpid()))
	statrec = BackgroundTasks(app.logger)
	statrec.schedule()

if __name__ == '__main__':
	app.run(debug=False, use_reloader=False)