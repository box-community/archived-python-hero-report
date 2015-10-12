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

	sql = '''SELECT Ending as Starting, Starting as Ending 
FROM
    (
        SELECT DISTINCT Starting, ROW_NUMBER() OVER (ORDER BY Starting) RN
        FROM Stats T1
        WHERE Measure IN ('{0}')
			AND NOT EXISTS (
                SELECT *
                FROM Stats T2
                WHERE T1.Starting > T2.Starting AND T1.Starting < T2.Ending
            )
        ) T1
    JOIN (
        SELECT DISTINCT Ending, ROW_NUMBER() OVER (ORDER BY Ending) RN
        FROM Stats T1
        WHERE Measure IN ('{0}')
			AND NOT EXISTS (
                SELECT *
                FROM Stats T2
                WHERE T1.Ending > T2.Starting AND T1.Ending < T2.Ending
            )
    ) T2
    ON T1.RN - 1 = T2.RN
WHERE
    Ending < Starting;'''

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
		self.logger.debug("  got {0} events from box starting {1}".format(len(events), created_after))
		for event_type in BackgroundTasks.velocity_event_types:
			count = len([elem for elem in events if elem['event_type'] == event_type])
			self.logger.debug("   found {0} {1} events".format(count, event_type))
			stat = Stat(event_type, count, created_after, created_before)
			db.session.add(stat)
			try:
				db.session.commit()
			except Exception as e:
				self.logger.debug('Caught exception: {}'.format(e))
				db.session.rollback()

		unique_user_count = len(set([elem['created_by']['login'] for elem in events]))
		stat = Stat('UNIQUE_USERS', unique_user_count, created_after, created_before)
		self.logger.debug("   found {0} UNIQUE_USERS".format(count, event_type))
		db.session.add(stat)
		try:
			db.session.commit()
		except:
			self.logger.debug('Caught exception when adding event stats: {}'.format(e))
			db.session.rollback()


	def backfill_velocity(self):
		# find oldest hour in stat database
		try:
			oldest_record = db.session.query(func.min(Stat.starting)).one()
		except NoResultFound:
			# exit backfill if database is empty
			self.logger.info("no database history found. exit backfill.")
			return

		# get all date/time gaps for event measures
		query = BackgroundTasks.sql.format("','".join(BackgroundTasks.velocity_event_types))
		gaps = db.engine.execute(query)
		
		self.logger.info("found {0} event gap(s) to backfill", len(gaps))
		
		for gap in gaps:
			starting = gap[0]	
			ending = gap[1]	
			# process each gap...
			while starting != ending:
				self.logger.info("backfilling events starting: {0}".format(starting))
				self.record_velocity(starting)
				# ...incrementing by 1 minute until the entire gap is filled
				starting = starting + datetime.timedelta(minutes=1)
				

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
		self.logger.debug("Scheduled backfill job to run every 15 minutes")

	def trigger_usage_job(self):
		self.scheduler.add_job(self.record_usage, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=1), coalesce=True)
		self.logger.debug("Scheduled on-demand usage job")

	def trigger_event_job(self):
		self.scheduler.add_job(self.record_velocity, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=1), coalesce=True)
		self.logger.debug("Scheduled on-demand event job")

	def trigger_event_backfill(self):
		self.scheduler.add_job(self.backfill_velocity, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=1), coalesce=True)
		self.logger.debug("Scheduled on-demand event backfill")
