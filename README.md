# Box Hero Reports

This web app provides dynamic reporting for Box enterprises. (These instructions will be fleshed out over time.)

## Goals

* Provide dynamic reporting of Box enterprise *events* (e.g. uploads/downloads) and *usage* (e.g. total users/storage)
* Automatically pull event information once a minute, and usage information once a day
* Provide an API to expose reporting information to other services
* Use Docker to simplify boostrapping and deployment
 
## Dev Deployment

*Note*: This application requires Docker, which works best on Mac or Linux.

### Gather Box Credentials

1. Create a Box app with the 'manage an enterprise' scope.
2. Use a [token generator application](https://box-oauth2-mvc.azurewebsites.net) to fetch an initial access/refresh token pair. The authorizing account **must** be a Box enterprise admin or co-admin.

### Create Docker Container

1. Install [docker-compose](http://docs.docker.com/compose/install/) and [docker-machine](https://docs.docker.com/machine/#installation).
1. Clone this repository
1. Edit the `/.env` file. Set the following values:
   * `CLIENT_ID` = your Box app Client ID
   * `CLIENT_SECRET` = your Box app Client Secret
   * `ACCESS_TOKEN` = your initial access token
   * `REFRESH_TOKEN` = your initial refresh token
1. Open a terminal shell
1. Create the virtual machine to host your Docker container
  * `$ docker-machine create -d virtualbox dev;`
1. Make the `dev` VM your default
  * `$ eval "$(docker-machine env dev)"`
1. Change to the directory when you cloned this repo
  * `$ cd ~/Documents/github/box-hero-report`
1. Build the Docker container. This may take a bit.
  * `box-hero-report$ docker-compose build`
  * `box-hero-report$ docker-compose up -d`

### Run The Application 

1. Create the database
  * `box-hero-report$ docker-compose run web /usr/local/bin/python create_db.py`
1. List your Docker VMs and view the IP address for `dev`. Open that IP address in a browser.
  * `$ docker-machine ls`
1. Click the `Import Tokens` button at the top right of the screen to save your tokens to the database.
1. The screen should refresh and the app should begin pulling data from Box and storing them in the database. The graphs will dynamically update with new data once per minute. The app will continue to pull data until the container is shut down.

Notes:
* To view Docker logs: `$ docker-compose logs`
* To deploy changes, re-run steps 7-8.

