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

cdm = Blueprint('cdm_v1', url_prefix='/cdm')


class Cdm(HTTPMethodView):
    @staticmethod
    def post(request):
        message = request.form['message'][0]
        recipient = request.form['recipient'][0]
        tx = send_cdm(message, recipient)

        data = {
            'message': message,
            'recipient': recipient,
            'tx': tx
        }

        return json(data, status=(201 if tx else 200))

    @staticmethod
    def get(request, alice, bob):
        data = {
            'cdms': get_cdms(alice, bob)
        }
        return json(data, status=200)

def send_cdm(message, recipient):
    pw.setNode(node=config['blockchain']['host'], chain='testnet')
    sponsor = pw.Address(seed=config['blockchain']['sponsor_seed'])
    
    asset = pw.Asset(config['blockchain']['asset_id'])
    feeAsset = pw.Asset(config['blockchain']['asset_id'])
    attachment = create_ipfs_file(message)

    tx = sponsor.sendAsset(
        recipient = pw.Address(publicKey=recipient),
        asset = asset,
        feeAsset = feeAsset,
        amount = 1,
        attachment = attachment['Hash'])

    return tx

def get_cdms(alice, bob):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.cnfy_id, t.id, c.recipient, c.message, c.hash, t.timestamp
                    FROM cdms c
                    LEFT JOIN transactions t ON c.tx_id = t.id
                    LEFT JOIN senders s ON s.cdm_id = c.id
                    WHERE ((s.sender='{alice}' AND c.recipient='{bob}') 
                    OR (s.sender='{bob}' AND c.recipient='{alice}'))
                    AND t.valid = 1
                    ORDER BY t.timestamp DESC""".format(
                        alice=alice,
                        bob=bob
                    ))
                records = cur.fetchall()

                cdms = []
                for record in records:
                    cur.execute("""
                        SELECT recipient FROM cdms
                        WHERE tx_id='{tx_id}'
                    """.format(
                        tx_id=record[1]
                    ))
                    recipients = cur.fetchall()

                    # cur.execute("""
                    #     SELECT c.recipient
                    #     FROM cdms c
                    #     WHERE c.hash='{hash}'
                    #     ORDER BY timestamp
                    # """.format(
                    #     hash=record[4]
                    # ))
                    # forwarded = cur.fetchall()
                    # forward_init = forwarded.pop(0)

                    data = {
                        "id": record[0],
                        "txId": record[1],
                        "recipient": record[2],
                        "message": record[3],
                        "hash": record[4],
                        "timestamp": record[5],
                        "recipients": [get_account(el[0]) for el in recipients]
                    }

                    if alice == bob:
                        data['type'] = 'outgoing'
                    else:
                        data['type'] = 'incoming' if record[2] == alice else 'outgoing'
                        
                    cdms.insert(0, data)


    except Exception as error:
        return bad_request(error)
    
    return cdms

cdm.add_route(Cdm.as_view(), '/')
cdm.add_route(Cdm.as_view(), '/<alice>/<bob>')
