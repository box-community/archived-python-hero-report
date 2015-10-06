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

* Install [docker-compose](http://docs.docker.com/compose/install/) and [docker-machine](https://docs.docker.com/machine/#installation).
* Clone this repository
* Edit the `/.env` file. Set the following values:
   * `CLIENT_ID` = your Box app Client ID
   * `CLIENT_SECRET` = your Box app Client Secret
   * `ACCESS_TOKEN` = your initial access token
   * `REFRESH_TOKEN` = your initial refresh token
* Open a terminal shell
* Create the virtual machine to host your Docker container
```
$ docker-machine create -d virtualbox dev
Creating VirtualBox VM...
Creating SSH key...
Starting VirtualBox VM...
Starting VM...
To see how to connect Docker to this machine, run: docker-machine env test
```
* Make the `dev` VM your default
```
$ eval "$(docker-machine env dev)"
```
* Change to the directory when you cloned this repo
```
$ cd ~/Documents/github/box-hero-report
box-hero-report$ 
```
* Build the Docker container. This may take a bit.
```
$ box-hero-report$ docker-compose build
..... lots of stuff happens .....
$ box-hero-report$ docker-compose up -d
..... lots of stuff happens .....
```
### Run The Application 

* Create the database
```
box-hero-report$ docker-compose run web /usr/local/bin/python create_db.py
```
* List your Docker VMs and view the IP address for `dev` under the *URL* column. Open that IP address in a browser. The application is hosted on port 80.
```
box-hero-report$ docker-machine ls
NAME      ACTIVE   DRIVER       STATE     URL                         SWARM
default            virtualbox   Stopped                               
dev       *        virtualbox   Running   tcp://192.168.99.100:2376   
```
* Click the `Import Tokens` button at the top right of the screen to save your tokens to the database.
* The screen should refresh and the app should begin pulling data from Box and storing them in the database. The graphs will dynamically update with new data once per minute. The app will continue to pull data until the container is shut down.

Notes:
* To view Docker logs: `$ docker-compose logs`
* To deploy changes, re-run steps 7-8.

## API

An API is exposed so that external applications can pull reporting data.

### Events

* Endpoint: <host>/event/stat?event_type=<event_types>
* Supported <event_types>: 
  * UPLOAD
  * DOWNLOAD
  * DELETE
  * LOGIN 
  * COLLABORATION_INVITE
  * COLLABORATION_ACCEPT
* Result: An array of array of event datapoints, where a datapoint is a `tick` (ms from epoch) and a `count`

#### Example
```
GET http://host/event/stat?event_type=UPLOAD,DOWNLOAD

[
  [ 
    /* UPLOAD events        */
    /* tick,          count */
    [1444156320000.0, 110.0], 
    [1444156380000.0, 121.0]
  ],
  [ 
    /* DOWNLOAD events      */
    [1444156320000.0, 195.0], 
    [1444156380000.0, 201.0]
  ]
]
```
