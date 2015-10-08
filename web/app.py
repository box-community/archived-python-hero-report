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

tasks = BackgroundTasks(app.logger)

@app.route('/', methods=['GET'])
def index():
	return render_template('index.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
	if request.method == 'POST':
		app.logger.debug("Received post '{0}', '{1}'".format(request.form['client_id'], request.form['client_secret']))
		box = Box(app.logger)
		box.set_value('client_id', request.form['client_id'])
		box.set_value('client_secret', request.form['client_secret'])
		return redirect('/', code=302)
	return render_template('settings.html')

@app.route('/auth/is_authorized', methods=['GET'])
def is_authorized():
	authorized = Box(app.logger).is_authorized()
	return Response(json.dumps(authorized), mimetype='application/json')

@app.route('/auth/authorize', methods=['GET','POST'])
def authorize():
	box = Box(app.logger)
	code = request.args.get('code')

	if code is None:
		callback = 'https://' + request.headers.get('Host') + '/auth/authorize'
		auth_url = box.authorization_url(callback)
		return redirect(auth_url, code=302)

	box.authorize(code)
	return redirect('/', code=302)

@app.route('/event/file', methods=['GET'])
def velocity_file():
	return render_template('event-file.html')

@app.route('/event/engagement', methods=['GET'])
def velocity_engagement():
	return render_template('event-engagement.html')

@app.route('/event/uniqueusers', methods=['GET'])
def velocity_uniqueusers():
	return render_template('unique-users.html')

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

@app.route('/usage/user', methods=['GET'])
def usage_user():
	return render_template('usage-user.html')

@app.route('/usage/stat', methods=['GET'])
def usage():
	result = []
	epoch = datetime.datetime.utcfromtimestamp(0)

	event_types = request.args.get('type').split(',')
	for event_type in event_types:
		series = []
		stats = Stat.query.filter(Stat.measure == event_type).order_by(Stat.starting.asc()).all()
		for stat in stats:
			series.append([(stat.starting - epoch).total_seconds() * 1000, stat.value])
		result.append(series)
	return Response(json.dumps(result),  mimetype='application/json')

@app.route('/usage/trigger', methods=['GET'])
def usage_trigger():
	tasks.trigger_usage_job()
	return Response(json.dumps("OK"),  mimetype='application/json')

@app.route('/event/trigger', methods=['GET'])
def event_trigger():
	tasks.trigger_event_job()
	return Response(json.dumps("OK"),  mimetype='application/json')

@app.before_first_request
def init():
	app.logger.debug("Init pid {}".format(os.getpid()))
	tasks.schedule()

if __name__ == '__main__':
	app.run(debug=False, use_reloader=False)
