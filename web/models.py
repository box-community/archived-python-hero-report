# models.py


import datetime
from app import db
from sqlalchemy import UniqueConstraint

class Setting(db.Model):
	
	__tablename__ = 'settings'
	
	id = db.Column(db.Integer, primary_key=True)
	key = db.Column(db.String, nullable=False)
	value = db.Column(db.String, nullable=False)
	
	def __init__(self, key, value):
		self.key = key
		self.value = value
		
		
class Stat(db.Model):
	
	__tablename__ = 'stats'
	__table_args__ = (UniqueConstraint('measure', 'starting'),)

	id = db.Column(db.Integer, primary_key=True)
	measure = db.Column(db.String, nullable=False)
	value = db.Column(db.Float, nullable=False)
	starting = db.Column(db.DateTime, nullable=False)
	ending = db.Column(db.DateTime, nullable=False)
	
	def __init__(self, measure, value, starting, ending):
		self.measure = measure
		self.value = value
		self.starting = starting
		self.ending = ending