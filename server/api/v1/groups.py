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
import hashlib
from .accounts import get_account
from .cdms import get_cdms
from .errors import bad_request
import configparser
import base58

groups = Blueprint('groups_v1', url_prefix='/groups')

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


class Groups(HTTPMethodView):
    @staticmethod
    def get(request, alice):
        data = {
            'groups': get_groups(alice)
        }
        return json(data, status=200)


def get_groups(alice):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        array(
                            SELECT s.sender
                            FROM senders s
                            WHERE s.tx_id = t.id
                        ),
                        array(
                            SELECT c.recipient
                            FROM cdms c
                            WHERE c.tx_id = t.id
                        )
                        FROM transactions t
                        ORDER BY t.timestamp DESC""".format(
                        alice=alice
                    ))
                txs = cur.fetchall()
                selfGroupHash = hashlib.sha256(''.join([alice, alice]).encode('utf-8')).hexdigest()
                selfCdms = get_cdms(alice, alice)

                groups = [{
                    'index': 0,
                    'members': [get_account(alice)],
                    'groupHash': selfGroupHash,
                    'totalCdms': len(selfCdms),
                    'lastCdm': None if len(selfCdms) == 0 else selfCdms[-1]
                }]


                group_hashes = [selfGroupHash]
                for tx in txs:
                    senders = tx[0]
                    recipients = tx[1]
                    members = senders + recipients
                    members.sort()
                    if alice in members:
                        group_hash = hashlib.sha256(''.join(members).encode('utf-8')).hexdigest()
                        if group_hash not in group_hashes:
                            cdms = get_cdms(senders[0], recipients[0])
                            group = {
                                'index': len(groups),
                                'members': [get_account(member) for member in members],
                                'groupHash': group_hash,
                                'totalCdms': len(cdms),
                                'lastCdm': None if len(cdms) == 0 else cdms[-1]
                            }
                            groups.append(group)
                            group_hashes.append(group_hash)
                

    except Exception as error:
        return bad_request(error)
    
    return groups


groups.add_route(Groups.as_view(), '/<alice>')