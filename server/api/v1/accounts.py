from sanic import Sanic
import os
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
account = Blueprint('account_v1', url_prefix='/account')

config = configparser.ConfigParser()
config.read('config.ini')

dsn = {
    "user": config['DB']['user'],
    "password": config['DB']['password'],
    "database": config['DB']['database'],
    "host": config['DB']['host'],
    "port": config['DB']['port'],
    "sslmode": config['DB']['sslmode']
}


class Accounts(HTTPMethodView):

    @staticmethod
    def post(request):
        address = request.form['address'][0]
        public_key = request.form['publicKey'][0]
        name = request.form['name'][0]

        try:
            conn = psycopg2.connect(**dsn)
            with conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        INSERT INTO accounts (address, public_key, name) VALUES (
                            '{address}', '{public_key}', '{name.strip()}'
                        ) ON CONFLICT (address) DO UPDATE SET name = EXCLUDED.name""")
                    conn.commit()
        except Exception as error:
            return bad_request(error)

        data = {
            'address': address,
            'publicKey': public_key,
            'name': name
        }

        return json(data, status=201)


class Account(HTTPMethodView):
    @staticmethod
    def get(request, public_key):
        data = get_account(public_key)
        return json(data, status=200 if data else 204)


def get_account(public_key):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                        SELECT address, public_key, name, created FROM accounts
                        WHERE public_key='{public_key}'
                    """)
                res = cur.fetchone()

                if not res:
                    return ''

    except Exception as error:
        return bad_request(error)

    data = {
        'address': res[0],
        'publicKey': res[1],
        'name': res[2],
        'created': res[3]
    }

    return data


accounts.add_route(Accounts.as_view(), '/')
account.add_route(Account.as_view(), '/<address>')