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
        return json({'interlocutors': data}, status=200)


def get_interlocutors(alice):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.sender, t.recipient
                    FROM transactions t
                    WHERE (sender='{alice}' OR recipient='{alice}')
                    AND t.valid = 1
                    ORDER BY timestamp DESC""".format(
                        alice=alice
                    ))
                transactions = cur.fetchall()

                # # groups = []
                # group_txs = []
                # non_group_txs = []
                # attachments = []
                # for tx in transactions:
                #     att = tx[3]
                #     if att in attachments:
                #         group_txs.append(tx)
                #     else:
                #         non_group_txs.append(tx)
                #         attachments.append(att)

                # print('***non_group_txs')
                # print(non_group_txs)

                bobs = []
                for tx in transactions:
                    sender = tx[0]
                    recipient = tx[1]

                    if sender != recipient:
                        interlocutor = sender if recipient == alice else recipient
                        if interlocutor not in bobs:
                            bobs.append(interlocutor)

                accounts = []
                for index, bob in enumerate(bobs):
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
                        'index': index,
                        'accounts': [account],
                        'totalCdms': len(cdms),
                        'cdm': None if len(cdms) == 0 else cdms[-1]
                    })
                
                # accounts.append({
                #     'index': len(accounts) + 1,
                #     'accounts': [
                #         {
                #             'address': '3N7ji8NgvVDDMKxtPY3jRV6xM7JTjMrw2Xk',
                #             'publicKey': '6xFRZDmMT4DWmvVLyD8t3KbwzUXyusRRpEjPWCwFeo6k',
                #             'name': 'Fred',
                #             'created': ''
                #         },
                #         {
                #             'address': '3MquQjG5Grs4EF1JUgkZ1RLQ2Hife7GsSAp',
                #             'publicKey': '2zRUoYjmWL6Mp7m3dv2EgVkSPLFA5jPqLYV1DfYhrnTD',
                #             'name': 'Greg',
                #             'created': ''
                #         }
                #     ],
                #     'totalCdms': 0,
                #     'cdm': None
                # })


    except Exception as error:
        return bad_request(error)
    
    return accounts


interlocutors.add_route(Interlocutors.as_view(), '/<alice>')