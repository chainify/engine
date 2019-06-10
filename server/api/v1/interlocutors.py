from sanic import Sanic
import os
import time
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
from .contacts import get_contacts
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
    "sslmode": config['DB']['sslmode'],
    "target_session_attrs": config['DB']['target_session_attrs']
}


class Interlocutors(HTTPMethodView):
    @staticmethod
    def get(request, alice):
        data = {
            'contacts': get_contacts(alice),
            'interlocutors': get_interlocutors(alice)
        }
        return json(data, status=200)


def get_interlocutors(alice):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT s.sender, c.recipient, tx_id
                    FROM cdms c
                    LEFT JOIN transactions t ON c.tx_id = t.id
                    LEFT JOIN senders s ON s.cdm_id = c.id
                    WHERE (s.sender='{alice}' OR c.recipient='{alice}')
                    AND t.valid = 1
                    ORDER BY t.timestamp DESC""".format(
                        alice=alice
                    ))
                cdms = cur.fetchall()

                bobs = []
                for cdm in cdms:
                    sender = cdm[0]
                    recipient = cdm[1]

                    if sender != recipient:
                        interlocutor = sender if recipient == alice else recipient
                        if interlocutor not in bobs:
                            bobs.append(interlocutor)

                selfAccount = get_account(alice)
                if selfAccount:
                    selfAccount['name'] = 'SAVED'
                selfCdms = get_cdms(alice, alice)

                accounts = [{
                    'index': 0,
                    'accounts': [selfAccount or {
                        'publicKey': alice,
                        'firstName': None,
                        'lastName': None,
                        'created': '',
                        'lastActive': ''
                    }],
                    'inCdms': 0,
                    'totalCdms': len(selfCdms),
                    'cdm': None if len(selfCdms) == 0 else selfCdms[-1]
                }]

                for index, bob in enumerate(bobs):
                    account = get_account(bob)
                    if not account:
                        account = {
                            'publicKey': bob,
                            'firstName': None,
                            'lastName': None,
                            'created': int(time.time()),
                            'lastActive': int(time.time())
                        }
                    cdms = get_cdms(alice, bob)

                    inCdms = 0
                    for cdm in cdms:
                        if cdm['type'] == 'incoming':
                            inCdms += 1
                    
                    accounts.append({
                        'index': index + 1,
                        'accounts': [account],
                        'groupHash': '',
                        'inCdms': inCdms,
                        'totalCdms': len(cdms),
                        'cdm': None if len(cdms) == 0 else cdms[-1]
                    })
                

    except Exception as error:
        return bad_request(error)
    
    return accounts


interlocutors.add_route(Interlocutors.as_view(), '/<alice>')