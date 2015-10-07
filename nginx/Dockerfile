FROM tutum/nginx
RUN rm /etc/nginx/sites-enabled/default
COPY ssl-cert.pem /etc/ssl/certs/ssl-cert.pem
COPY ssl-cert.key /etc/ssl/private/ssl-cert.key
ADD sites-enabled/ /etc/nginx/sites-enabled