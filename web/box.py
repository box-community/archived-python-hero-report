#box.py

import os
import logging
from app import db 
from boxsdk import OAuth2, Client 
from models import Setting

class Box(object):
	
	def __init__(self, logger):
		self.logger = logger
		
	def get_setting(self, key):
		setting = Setting.query.filter(Setting.key == key).first()
		if setting is None:
			return None
		return setting.value
		
	def set_value(self, key, value):
		setting = Setting.query.filter(Setting.key == key).first()
		if setting is None:
			setting = Setting(key,'')
			db.session.add(setting)
		setting.value = value
		db.session.commit()

	def oauth2(self):
		return OAuth2(
			client_id=self.get_setting('client_id'),
			client_secret=self.get_setting('client_secret'),
			access_token=self.get_setting('access_token'),
			refresh_token=self.get_setting('refresh_token'),
			store_tokens=self.store_tokens)

	def client(self):
		return Client(self.oauth2())

	def import_tokens(self):
		self.set_value('client_id', os.environ['CLIENT_ID'])
		self.set_value('client_secret', os.environ['CLIENT_SECRET'])
		self.set_value('access_token', os.environ['ACCESS_TOKEN'])
		self.set_value('refresh_token', os.environ['REFRESH_TOKEN'])

	def store_tokens(self, access_token, refresh_token):
		self.logger.info('Updating access/refresh token pair')
		self.set_value('access_token', access_token)
		self.set_value('refresh_token', refresh_token)
	
	def is_authorized(self):
		try:
			access_token = self.get_setting('access_token')
			if access_token is None:
				self.logger.debug('Access token not set; user is not authorized')
				return False;

			user = self.client().user(user_id='me').get()
			self.logger.debug('User is authorized')
			return True
		except:
			self.logger.debug('User is not authorized')
			return False
	
	def authorization_url(self):
		auth_url, csrf_token = self.oauth2().get_authorization_url('http://192.168.99.100/')
		return auth_url
	
	def authorize(self, code):
		self.logger.info('Authorizing OAuth2 code...')
		access_token, refresh_token = self.oauth2().authenticate(code)
		self.logger.info('OAuth2 code authorized')
		self.store_tokens(access_token, refresh_token)	