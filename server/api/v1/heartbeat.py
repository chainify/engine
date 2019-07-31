from sanic import Sanic
import os
from sanic import Blueprint
from sanic.views import HTTPMethodView
from sanic.log import logger
from sanic.response import json
import requests
import psycopg2
from .errors import bad_request
import configparser
import base58
from .ipfs import create_ipfs_file, read_ipfs_file
import time
import websockets
import contextvars
import collections
import pywaves as pw
from datetime import datetime
from .cdms import get_last_cdm
from .groups import get_groups
import redis

config = configparser.ConfigParser()
config.read('config.ini')

dsn = {
    "user": config['DB']['user'],
    "password": config['DB']['password'],
    "database": config['DB']['database'],
    "host": config['DB']['host'],
    "port": config['DB']['port'],
    "sslmode": config['DB']['sslmode'],
    "target_session_attrs": config['DB']['target_session_attrs']
}

heartbeat = Blueprint('heartbeat_v1', url_prefix='/heartbeat')


class HeartBeat(HTTPMethodView):

    @staticmethod
    def post(request):
        now = datetime.now()
        public_key = request.form['publicKey'][0]
        last_timestamp = request.form['lastTimestamp'][0]

        pool = redis.ConnectionPool(host='redis', port=6379, db=0)
        r = redis.Redis(connection_pool=pool)

        pipe = r.pipeline()
        pipe.set(public_key, last_timestamp).expire(public_key, 2).execute()

        # print('\npublic_key', r.get(public_key))
        # print('sleeping...')
        # time.sleep(3)
        # print('\npublic_key', r.get(public_key))

        data = {
            'groups': get_groups(public_key, last_timestamp)
        }
        return json(data, status=201)


        # get_last_cdm(public_key)

        # try:/
            # conn = psycopg2.connect(**dsn)
            # with conn:
            #     with conn.cursor() as cur:
            #         pass
                    # cur.execute("""
                    #     INSERT INTO accounts (public_key) VALUES ('{public_key}')
                    #     ON CONFLICT (public_key) DO UPDATE SET last_active='{last_active}'
                    # """.format(
                    #     public_key=public_key,
                    #     last_active=last_active
                    # ))
                    # conn.commit()

                    # cur.execute("""
                    #     SELECT
                    #         a.public_key,
                    #         a.last_active,
                    #         unnest(array(
                    #             SELECT distinct c.group_hash 
                    #             FROM cdms c 
                    #             WHERE c.recipient = a.public_key
                    #             AND c.timestamp >= (SELECT to_timestamp({last_timestamp}) AT TIME ZONE 'UTC')
                    #         )) as group_hash
                    #     FROM accounts a
                    #     WHERE a.last_active >= now() - INTERVAL '4 seconds'
                    #     AND a.public_key <> '{public_key}'
                    #     ORDER BY a.last_active desc;
                    # """.format(
                    #     public_key=public_key,
                    #     last_timestamp=last_timestamp
                    # ))

        # except Exception as error:
        #     return bad_request(error)

        

heartbeat.add_route(HeartBeat.as_view(), '/')
