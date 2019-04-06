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
from .accounts import get_account
from .cdm import get_cdms
from .errors import bad_request
import configparser
import base58

interlocutors = Blueprint('interlocutors_v1', url_prefix='/interlocutors')

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


class Interlocutors(HTTPMethodView):
    @staticmethod
    def get(request, alice):
        data = get_interlocutors(alice)
        return json({'interlocutors': data}, status=200 if len(data) > 0 else 204)


def get_interlocutors(alice):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.sender, t.recipient
                    FROM transactions t
                    WHERE sender='{alice}' OR recipient='{alice}'
                    ORDER BY timestamp DESC""".format(
                        alice=alice
                    ))
                transactions = cur.fetchall()

                bobs = []
                for tx in transactions:
                    sender = tx[0]
                    recipient = tx[1]

                    if sender != recipient:
                        interlocutor = sender if recipient == alice else recipient
                        if interlocutor not in bobs:
                            bobs.append(interlocutor)

                accounts = []
                for bob in bobs:
                    account = get_account(bob)
                    if not account:
                        account = {
                            'address': bob,
                            'publicKey': '',
                            'name': bob,
                            'created': ''
                        }
                    cdms = get_cdms(alice, bob)

                    accounts.append({
                        'account': account,
                        'totalCdms': len(cdms),
                        'readCdms': 0,
                        'newCdms': 0,
                        'cdm': None if len(cdms) == 0 else cdms[-1]
                    })

    except Exception as error:
        return bad_request(error)
    
    return accounts


interlocutors.add_route(Interlocutors.as_view(), '/<alice>')