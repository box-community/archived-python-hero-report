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
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import func
from models import Stat

class BackgroundTasks(object):

	velocity_event_types=['UPLOAD','DOWNLOAD','DELETE','COLLABORATION_INVITE','COLLABORATION_ACCEPT','LOGIN']
	limit = 500
	backfill_max_days = 14 # default past days to backfill if stats are missing
	backfill_max_hours = 8 # max hours per backfill run
	backfill_marker = 'HOUR_COMPLETE'

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

	def record_velocity(self, created_after=None):
		if not created_after:
			# record stats for previous minute
			created_before = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0)
			created_after = created_before + datetime.timedelta(minutes=-1)
		else:
			# records stats for created_after minute
			created_before = created_after + datetime.timedelta(minutes=1)
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

	def backfill_hour(self, hour):
		"""Attempt to backfill all minutes in given hour. Assumes that if any
		event type exists for a given minute, all velocity_event_types have been
		recorded."""
		# start backfill at <hour>:59
		backfill_start = hour + datetime.timedelta(minutes=59)
		# make sure backfill_step isn't in the future
		current_minute = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0)
		if backfill_start >= current_minute:
			backfill_start = current_minute - datetime.timedelta(minutes=2)
		self.logger.info("backfilling minutes %s to %s" % (
			backfill_start, hour))
		# load existing Stat.starting timestamps for this hour
		db_minutes = db.session.query(Stat.starting).filter(
			Stat.starting>=hour, Stat.starting<=backfill_start).distinct().all()
		db_minutes = [pytz.utc.localize(m[0]) for m in db_minutes]
		# loop through and backfill any missing minutes
		mc = 0
		minute_step = backfill_start
		while minute_step >= hour:
			if minute_step not in db_minutes:
				self.record_velocity(minute_step)
				mc += 1
			minute_step = minute_step - datetime.timedelta(minutes=1)
		self.logger.info("backfilled %s minutes in hour %s" % (mc, hour))
		# if 59 distinct minutes exist for this hour, mark as complete
		if db.session.query(Stat.starting).filter(Stat.starting>=hour,
		Stat.starting<=backfill_start).distinct().count() == 60:
			stat = Stat(BackgroundTasks.backfill_marker, 1, hour, backfill_start)
			db.session.add(stat)
			try:
				db.session.commit()
			except Exception as e:
				self.logger.debug('Caught exception: {}'.format(e))
				db.session.rollback()
			else:
				self.logger.info("marked hour %s as complete" % hour)

	def backfill_velocity(self):
		# find oldest hour in stat database
		try:
			oldest_record = db.session.query(func.min(Stat.starting)).one()
		except NoResultFound:
			# exit backfill if database is empty
			self.logger.info("no database history found. exit backfill.")
			return
		oldest_hour = pytz.utc.localize(oldest_record[0]).replace(
			minute=0, second=0, microsecond=0)
		# set start and end backfill hours
		backfill_start = datetime.datetime.now(
			datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
		backfill_end = backfill_start - datetime.timedelta(
			days=BackgroundTasks.backfill_max_days)
		# don't backfill beyond oldest database record
		if backfill_end < oldest_hour:
			backfill_end = oldest_hour
		self.logger.info("backfill %s to %s" % (backfill_start, backfill_end))
		# query for completed hours
		completed_hours = db.session.query(Stat.starting).filter(
			Stat.measure==BackgroundTasks.backfill_marker,
			Stat.starting>=backfill_end, Stat.starting<=backfill_start
			).distinct().all()
		completed_hours = [pytz.utc.localize(h[0]) for h in completed_hours]
		self.logger.info("found %s completed hours" % len(completed_hours))
		# loop and backfill as many as 'backfill_max_hours' incomplete hours
		hc = 0
		hour_step = backfill_start
		while hour_step >= backfill_end:
			if hour_step not in completed_hours:
				self.logger.info("backfilling hour %s" % hour_step)
				self.backfill_hour(hour_step)
				hc += 1
			if hc == BackgroundTasks.backfill_max_hours:
				break
			hour_step = hour_step - datetime.timedelta(hours=1)
		self.logger.info("backfilled %s hours" % hc)

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
		self.scheduler.add_job(self.backfill_velocity, 'interval', minutes=15, coalesce=True)
		self.logger.debug("Scheduled backfill job to run every minute")

	def trigger_usage_job(self):
		self.scheduler.add_job(self.record_usage, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=1), coalesce=True)
		self.logger.debug("Scheduled on-demand usage job")

	def trigger_event_job(self):
		self.scheduler.add_job(self.record_velocity, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=1), coalesce=True)
		self.logger.debug("Scheduled on-demand event job")
