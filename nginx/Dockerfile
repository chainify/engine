FROM nginx:latest

# RUN apt-get update
# RUN apt-get install -y sqlite3 libsqlite3-dev

# RUN mkdir /opt/db
# RUN touch /opt/db/test.db

COPY nginx.prod.conf /etc/nginx/nginx.conf

# RUN /usr/bin/sqlite3 /opt/db/test.db
# COPY dhparam.pem /etc/nginx/dhparam.pem
# COPY ssl_params.conf /etc/nginx/ssl_params.conf

# COPY ssl/chainify.org.crt /etc/nginx/chainify.org.crt
# COPY ssl/chainify.org.key /etc/nginx/chainify.org.key

# COPY ssl/api.chainify.org.crt /etc/nginx/api.chainify.org.crt
# COPY ssl/api.chainify.org.key /etc/nginx/api.chainify.org.key