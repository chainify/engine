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
    def post(request):
        public_key = request.form['publicKey'][0]
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
            'publicKey': public_key,
            'created': last_active,
            'lastActive': last_active
        }

        return json(data, status=201)


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
                        SELECT a.last_active
                        FROM accounts a
                        WHERE a.public_key='{public_key}'
                    """.format(
                        public_key=public_key
                    ))
                account = cur.fetchone()

    except Exception as error:
        return bad_request(error)

    data = {
        'publicKey': public_key,
        'lastActive': account[0] if account else None
    }

    return data


accounts.add_route(Accounts.as_view(), '/')
accounts.add_route(Accounts.as_view(), '/<public_key>')