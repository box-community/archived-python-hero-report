# tasks.py

import os
import fcntl
import logging
import datetime
from app import db 
from boxsdk import OAuth2
from boxsdk import Client 
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.sql import exists
from models import Stat

class BackgroundTasks(object):
	
	velocity_event_types=['UPLOAD','DOWNLOAD','DELETE','COLLABORATION_INVITE','COLLABORATION_ACCEPT']
	limit = 500
	
	def __init__(self, db, logger, access_token, refresh_token):
		self.logger = logger
		self.scheduler = BackgroundScheduler()
		self.client = Client(OAuth2(
			client_id='foo',
			client_secret='bar',
			access_token=access_token,
			refresh_token=refresh_token))
			
	def get_velocity_events(self, event_types, created_after, created_before):
		total = 0
		next_stream_position = 0
		keep_going = True
		result = []
		while keep_going:
			events = self.client.events().get_enterprise_events(
				limit=BackgroundTasks.limit,
				event_type=event_types,
				stream_position=next_stream_position,
				created_after=created_after,		
				created_before=created_before,
			)
			result.extend(events['entries'])
			count = events['chunk_size']
			total = total + count
			next_stream_position = events['next_stream_position']
			keep_going = count == BackgroundTasks.limit

		return result
		
	def record_velocity(self):
		created_before = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0)
		created_after = created_before + datetime.timedelta(minutes=-1)
		events = self.get_velocity_events(BackgroundTasks.velocity_event_types, created_after, created_before)

		for event_type in BackgroundTasks.velocity_event_types:
			count = len([elem for elem in events if elem['event_type'] == event_type])
			stat = Stat(event_type, count, created_after, created_before)
			db.session.add(stat)
		db.session.commit()
	
	def schedule(self):
		self.logger.info("Starting scheduler")
		self.scheduler.start()
		self.scheduler.add_job(self.record_velocity, 'interval', minutes=1)		