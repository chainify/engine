from sanic import Sanic
import os
import time
from datetime import datetime

from sanic import Blueprint
from sanic.views import HTTPMethodView
from sanic.response import text
from sanic.log import logger
from sanic.response import json
import uuid
import asyncio
import aiohttp
import requests
import psycopg2
from .errors import bad_request
import configparser
import base58

accounts = Blueprint('accounts_v1', url_prefix='/accounts')

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


class Accounts(HTTPMethodView):
    @staticmethod
    def get(request, public_key):
        data = get_account(public_key)
        return json(data, status=200 if data else 204)



def get_account(public_key):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        a.public_key,
                        a.last_active,
                        unnest(array(SELECT distinct c.group_hash from cdms c where c.recipient = a.public_key)) as group_hash
                    FROM accounts a
                    WHERE a.last_active >= now() - INTERVAL '4 seconds'
                    AND a.public_key <> '{public_key}'
                    ORDER BY a.last_active desc;
                """.format(
                    public_key=public_key
                ))
                accounts = cur.fetchall()

    except Exception as error:
        return bad_request(error)

    data = [{
        'publicKey': account[0],
        'lastActive': account[1],
        'groupHash': account[2]
    } for account in accounts]

    return data


accounts.add_route(Accounts.as_view(), '/')
accounts.add_route(Accounts.as_view(), '/<public_key>')