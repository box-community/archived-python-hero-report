# tasks.py

import os
import fcntl
import logging
import datetime
import pytz
from app import db
from box import Box
from boxsdk import OAuth2
from boxsdk import Client
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.sql import exists
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func
from models import Stat

class BackgroundTasks(object):

	velocity_event_types=['UPLOAD','DOWNLOAD','DELETE','COLLABORATION_INVITE','COLLABORATION_ACCEPT','LOGIN']
	limit = 500
	backfill_max_days = 14
	backfill_max_

	def __init__(self, logger):
		self.logger = logger
		self.scheduler = BackgroundScheduler()


	def get_velocity_events(self, client, event_types, created_after, created_before):
		total = 0
		next_stream_position = 0
		keep_going = True
		result = []

		try:
			while keep_going:
				events = client.events().get_enterprise_events(
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
		except Exception as e:
			self.logger.warn("Failed to fetch event data from Box: {0}".format(e))
			return []

	def record_velocity(self):
		created_before = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0)
		created_after = created_before + datetime.timedelta(minutes=-1)
		client = Box(self.logger).client()
		if client is None:
			self.logger.warn("Client was not created. Events will not be fetched.")
			return

		events = self.get_velocity_events(client, BackgroundTasks.velocity_event_types, created_after, created_before)

		for event_type in BackgroundTasks.velocity_event_types:
			count = len([elem for elem in events if elem['event_type'] == event_type])
			stat = Stat(event_type, count, created_after, created_before)
			db.session.add(stat)
			try:
				db.session.commit()
			except Exception as e:
				self.logger.debug('Caught exception: {}'.format(e))
				db.session.rollback()

		unique_user_count = len(set([elem['created_by']['login'] for elem in events]))
		stat = Stat('UNIQUE_USERS', unique_user_count, created_after, created_before)
		db.session.add(stat)
		try:
			db.session.commit()
		except:
			self.logger.debug('Caught exception when adding event stats: {}'.format(e))
			db.session.rollback()
		else:
			self.logger.info("inserted %s unqiue users" % unique_user_count)

	def backfill_velocity(self):
		# set backfill end
		backfill_end = datetime.datetime.now(datetime.timezone.utc).replace(
			second=0, microsecond=0) - datetime.timedelta(days=BackgroundTasks.backfill_max_days)
		oldest_record = db.session.query(func.min(Stat.starting)).one()[0]
		oldest_record = pytz.utc.localize(oldest_record)
		if backfill_end < oldest_record:
			backfill_end = oldest_record
		self.logger.info("backfill_end: %s" % backfill_end)
		# set backfill start not to step on current record_velocity jobs
		backfill_start = datetime.datetime.now(datetime.timezone.utc).replace(
			second=0, microsecond=0) - datetime.timedelta(minutes=2)
		# query for distinct db stat minutes
		db_minutes = db.session.query(Stat.starting).filter(
			Stat.starting>=backfill_end, Stat.starting<=backfill_start).distinct().all()
		self.logger.info("select %s db_minutes" % len(db_minutes))

	def get_users(self, client):
		keep_going = True
		result = []

		try:
			while keep_going:
				users = client.user().get_enterprise_users(
					offset=len(result),
					limit=1000
				)
				result.extend(users['entries'])
				self.logger.info("got {0}/{1} enterprise users...".format(len(result), users['total_count']))
				keep_going = len(result) < users['total_count']

			return result
		except Exception as e:
			self.logger.warn("Failed to fetch user data from Box: {0}".format(e))
			return []

	def record_usage(self):
		client = Box(self.logger).client()
		if client is None:
			self.logger.warn("Client was not created. Users will not be fetched.")
			return

		starting = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
		ending = starting + datetime.timedelta(days=1)
		users = self.get_users(client)
		active = len([elem for elem in users if elem['status'] == 'active'])
		inactive = len([elem for elem in users if elem['status'] == 'inactive'])
		storage_used = sum(map(lambda user: user['space_used'], users))
		self.logger.debug("User stats: {0} active; {1} inactive; {2} GB used".format(active, inactive, storage_used/(1024*1024*1024)))
		db.session.add(Stat('ACTIVE_USERS', active, starting, ending))
		db.session.add(Stat('INACTIVE_USERS', inactive, starting, ending))
		db.session.add(Stat('STORAGE_USED_GB', storage_used/(1024*1024*1024), starting, ending))
		try:
			db.session.commit()
		except Exception as e:
			self.logger.debug('Caught exception when adding user stats: {}'.format(e))
			db.session.rollback()

	def schedule(self):
		self.logger.info("Starting scheduler")
		self.scheduler.start()
		self.scheduler.add_job(self.record_velocity, 'interval', minutes=1, coalesce=True)
		self.logger.debug("Scheduled event job to run every minute")
		self.scheduler.add_job(self.record_usage, 'interval', minutes=60, coalesce=True)
		self.logger.debug("Scheduled usage job to run every hour")
		# backoff later
		self.scheduler.add_job(self.backfill_velocity, 'interval', minutes=1, coalesce=True)
		self.logger.debug("Scheduled backfill job to run every minute")

	def trigger_usage_job(self):
		self.scheduler.add_job(self.record_usage, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=1), coalesce=True)
		self.logger.debug("Scheduled on-demand usage job")

	def trigger_event_job(self):
		self.scheduler.add_job(self.record_velocity, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=1), coalesce=True)
		self.logger.debug("Scheduled on-demand event job")
