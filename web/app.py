# app.py

from flask import Flask
from flask import request, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from config import BaseConfig
from boxsdk import OAuth2
from boxsdk import Client 
from datetime import datetime, timezone

app = Flask(__name__)
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)

from models import *

@app.route('/', methods=['GET', 'POST'])
#def index():
#	if request.method == 'POST':
#		text = request.form['text']
#		post = Post(text)
#		db.session.add(post)
#		db.session.commit()
#	posts = Post.query.order_by(Post.date_posted.desc()).all()
#	return render_template('index.html', key=app.config['SECRET_KEY'])

def index():
	
	oauth = OAuth2(
		client_id='foo',
		client_secret='bar',
		access_token=app.config['ACCESS_TOKEN']	
		)
	
	client = Client(oauth)
	events = client.events().get_enterprise_events(
		limit=5,
		event_type=['UPLOAD'], 
		created_after=datetime.datetime.now(timezone.utc) + datetime.timedelta(minutes=-5),		
		)
	
	return render_template('index.html', key=events)

if __name__ == '__main__':
	app.run()