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
import datetime
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

last_cdm = Blueprint('last_cdm_v1', url_prefix='/last_cdm')


class LastCdm(HTTPMethodView):

    @staticmethod
    def get(request, alice):
        data = {
            'lastCdm': get_last_cdm(alice)
        }
        return json(data, status=200)

def get_last_cdm(alice):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.attachment_hash
                    FROM cdms c
                    LEFT JOIN transactions t ON t.id = c.tx_id
                    WHERE c.recipient='{alice}'
                    ORDER BY t.timestamp DESC
                    LIMIT 1
                """.format(
                    alice=alice
                ))
                cdm = cur.fetchone()


    except Exception as error:
        return bad_request(error)
    
    return cdm

last_cdm.add_route(LastCdm.as_view(), '/<alice>')
