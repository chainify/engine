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
from time import time
import websockets
import contextvars
import collections
import pywaves as pw
from datetime import datetime
from .cdms import get_last_cdm
from .accounts import get_account

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
    def post(request, public_key):
        last_active = datetime.now()

        try:
            conn = psycopg2.connect(**dsn)
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO accounts (public_key) VALUES ('{public_key}')
                        ON CONFLICT (public_key) DO UPDATE SET last_active='{last_active}'
                    """.format(
                        public_key=public_key,
                        last_active=last_active
                    ))
                    conn.commit()

        except Exception as error:
            return bad_request(error)

        data = {
            'online': get_account(public_key),
            'lastCdm': get_last_cdm(public_key)
        }
        return json(data, status=201)


heartbeat.add_route(HeartBeat.as_view(), '/<public_key>')
