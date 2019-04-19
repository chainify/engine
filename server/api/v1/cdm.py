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
from .accounts import get_account
from .ipfs import read_ipfs_file
from time import time
import websockets
import contextvars
import collections

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

cdm = Blueprint('cdm_v1', url_prefix='/cdm')


class Cdm(HTTPMethodView):
    @staticmethod
    def get(request, alice, bob):
        
        data = {
            'cdms': get_cdms(alice,bob),
        }

        return json(data, status=200)

def get_cdms(alice, bob):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, sender, recipient, attachment, timestamp, cnfy_id FROM transactions
                    WHERE ((sender='{alice}' AND recipient='{bob}') 
                    OR (sender='{bob}' AND recipient='{alice}'))
                    AND valid = 1
                    ORDER BY timestamp DESC""".format(
                        alice=alice,
                        bob=bob
                    ))
                transactions = cur.fetchall()

                cdms = []
                for tx in transactions:
                    ipsf_hash = base58.b58decode(tx[3]).decode("utf-8")
                    ipfs_data = read_ipfs_file(ipsf_hash)

                    msg_type = 'incoming' if tx[1] == bob else 'outgoing'

                    data = {
                        "id": tx[5],
                        "txId": tx[0],
                        "sender": tx[1],
                        "recipient": tx[2],
                        "attachment": tx[3],
                        "timestamp": tx[4],
                        "message": ipfs_data,
                        "type": msg_type
                    }

                    if data['sender'] != data['recipient']:
                        cdms.insert(0, data)

    except Exception as error:
        return bad_request(error)
    
    return cdms

cdm.add_route(Cdm.as_view(), '/<alice>/<bob>')
