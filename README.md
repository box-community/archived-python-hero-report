# Box Hero Reports

This web app provides dynamic reporting for Box enterprises. (These instructions will be fleshed out over time.)

## Goals

* Provide dynamic reporting of Box enterprise *events* (e.g. uploads/downloads) and *usage* (e.g. total users/storage)
* Automatically pull event information once a minute, and usage information once a day
* Provide an API to expose reporting information to other services
* Use Docker to simplify boostrapping and deployment

# Deployment

A few notes before we begin:
  * This application requires Docker, which works best on Mac or Linux.
  * Throughout these instructions we refer to our Docker VM by the name `MACHINE-NAME`. You can pick whatever name you want for your VM, for example `test`, `dev`, or `report-prod`. Name it such that you'll be able to recognize it later.

## Prerequisites

* Install [docker-compose](http://docs.docker.com/compose/install/) and [docker-machine](https://docs.docker.com/machine/#installation).
* Clone this repository
* Open a terminal shell

## Create Docker VM

### On Local Machine

* Create the virtualbox vm to host your Docker container
```
$ docker-machine create -d virtualbox MACHINE-NAME
Creating VirtualBox VM...
Creating SSH key...
Starting VirtualBox VM...
Starting VM...
To see how to connect Docker to this machine, run: docker-machine env MACHINE-NAME
```

### On Azure

These deployment instructions were borrowed from [Microsoft's documentation](https://azure.microsoft.com/en-us/documentation/articles/virtual-machines-docker-machine/).

* Create management certs
```
$ openssl req -x509 -nodes -days 365 -newkey rsa:1024 -keyout mycert.pem -out mycert.pem
$ openssl pkcs12 -export -out mycert.pfx -in mycert.pem -name "My Certificate"
Enter Export Password: *****
Verifying - Enter Export Password:  *****
$ openssl x509 -inform pem -in mycert.pem -outform der -out mycert.cer
```
* Log into your Azure portal. From the left rail browse to **Settings**, then to the **Management Certificates** tab.
* Click the **Upload** button and select the `mycert.cer` that you just created.
* Browse to the **Subscriptions** tab. Note the *Subscription ID* of your Azure subscription.
* Create the virtual machine in Azure
```
$ docker-machine create -d azure \
                        --azure-subscription-id="SUBSCRIPTION-ID" \
                        --azure-subscription-cert="mycert.pem" \ 
                        MACHINE-NAME
Creating Azure machine...
To see how to connect Docker to this machine, run: docker-machine env MACHINE-NAME
```
* Finally, we'll need to allow HTTP/HTTPS connections through the VM firewall. HTTP will automatically redirect to HTTPS. 
  * In the Azure portal, from the left rail bowse to **Virtual Machines**
  * You should see a new virtual machine named `MACHINE-NAME`. Click on it and browse to the **Endpoints** tab.
  * Click **Add** -> **Add A Stand-Alone Endpoint** -> **HTTPS** (from dropdown). Click the checkmark to save the endpoint.
  * Repeat the previous step to add an **HTTP** endpoint.

### Configure SSL Certificates

In order to authenticate with Box the web app must have SSL enabled.

* Make the `dev` VM your default
```
$ eval "$(docker-machine env MACHINE-NAME)"
```
* Change to the directory when you cloned this repo
```
$ cd ~/Documents/github/box-hero-report
box-hero-report$
```

#### To generate a self-signed test certificate/key pair

**Note**: This cert is self-signed and will not be trusted by browsers. You'll get a warning message when you try to connect to the site, which you can ignore. This is OK for testing but not for production! Your sysadmin will be very angry and you will have a bad day.

```
box-hero-report$ openssl genrsa -out nginx/ssl-cert.key 2048
box-hero-report$ openssl req -new -x509 -key nginx/ssl-cert.key -out nginx/ssl-cert.pem -days 1095
```

#### To use a production certificate/key pair

1. Copy your certificate/key pair to `box-hero-app/nginx`
2. If your certificate/key pair has a different name than `ssl-cert.pem` and `ssl-cert.key`, then:

* Modify `box-hero-app/nginx/Dockerfile` to reflect your certificate/key filenames
```
FROM tutum/nginx
RUN rm /etc/nginx/sites-enabled/default
COPY YOUR-CERT /etc/ssl/certs/YOUR-CERT
COPY YOUR-KEY /etc/ssl/private/YOUR-KEY
ADD sites-enabled/ /etc/nginx/sites-enabled
```
 * Modify `box-hero-app/nginx/sites-enabled/flask_project` to reflect your certificate/key filenames
```
<-- snip -->
server {
	listen 443;

	ssl on;
	ssl_certificate /etc/ssl/certs/YOUR-CERT;
	ssl_certificate_key /etc/ssl/private/YOUR-KEY;
<-- snip -->
}
```

### Run The Application

* Build the Docker container. This will take a while.
```
box-hero-report$ docker-compose build
box-hero-report$ docker-compose up -d
```
* Create the database
```
box-hero-report$ docker-compose run web /usr/local/bin/python create_db.py
```
* List your Docker VMs and view the IP address for `MACHINE-NAME` under the *URL* column. Open that IP address in a browser. For example, with a `MACHINE-NAME` instance running at tcp://*HOST*:2376, you'd browse to https://*HOST*.
```
box-hero-report$ docker-machine ls
NAME            ACTIVE   DRIVER       STATE     URL                         SWARM
default                  virtualbox   Stopped
MACHINE-NAME    *        <driver>     Running   tcp://HOST:2376
```

### Connect to Box

1. In a separate tab, [create a Box app](https://app.box.com/developers/services) with the following settings:
  * Redirect URI: `https://YOUR-HOST/auth/authorize`
  * Scope: `manage an enterprise`
1. On the reporting page, click the `Settings` button in the top right of the page
1. Set the `Box App Client ID` to the value in the Box app's `client_id` field
1. Set the `Box App Client Secret` to the value in the Box app's `client_secret` field
1. Click `Save`. You will be redirected back to the main page.
1. Click red `Authorize` button on the top right of the page. This will kick off the Box app authorization flow.
1. Sign into Box with a Box enterprise account that has **admin** or **co-admin** privileges and grant access to the application.
1. You will be redirected back to the reporting page. You should now see a green `Authorized` button.

### All Done!

The reporting app should begin pulling data from Box and storing them in the database. The graphs will dynamically update with new data once per minute. The app will continue to pull data until the container is shut down.

## Logs

To view Docker logs: `$ docker-compose logs`

## API

An API is exposed so that external applications can pull reporting data.

### Events

* Endpoint: http://*host*/event/stat?event_type=*event_type[,event_type]*
* Supported *event_type*:
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
