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

cdms = Blueprint('cdms_v1', url_prefix='/cdms')


class Cdms(HTTPMethodView):
    @staticmethod
    def post(request):
        message = request.form['message'][0]
        tx = send_cdm(message)
        
        data = {
            'message': message,
            'tx': tx
        }

        return json(data, status=201)

    @staticmethod
    def get(request, alice, bob):
        data = {
            'cdms': get_cdms(alice, bob)
        }
        return json(data, status=200)

def send_cdm(message):
    pw.setNode(node=config['blockchain']['host'], chain=config['blockchain']['network'])
    sponsor = pw.Address(seed=config['blockchain']['sponsor_seed'])
    
    asset = pw.Asset(config['blockchain']['asset_id'])
    feeAsset = pw.Asset(config['blockchain']['asset_id'])
    attachment = create_ipfs_file(message)

    tx = sponsor.sendAsset(
        recipient = sponsor,
        asset = asset,
        feeAsset = feeAsset,
        amount = 1,
        attachment = attachment['Hash'])

    return tx
    

def get_cdms(alice, group_hash):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.message, c.hash, t.id, t.cnfy_id, t.attachment_hash, t.timestamp, t.sender_public_key, c.recipient, c.group_hash
                    FROM cdms c
                    LEFT JOIN transactions t ON t.id = c.tx_id
                    WHERE c.group_hash='{group_hash}'
                    AND c.recipient='{alice}'
                    ORDER BY t.timestamp DESC""".format(
                        group_hash=group_hash,
                        alice=alice
                    ))
                records = cur.fetchall()

                cdms = []
                for record in records:
                    cur.execute("""
                        SELECT c.recipient, c.tx_id, c.timestamp
                        FROM cdms c
                        WHERE c.hash='{hash}' 
                        AND c.group_hash <> '{groupHash}'
                        ORDER BY timestamp
                    """.format(
                        hash=record[1],
                        groupHash=record[7]
                    ))
                    forwarded = cur.fetchall()
                    forwarded_to = []
                    for recipient in forwarded:
                        forwarded_to.append({
                            'publicKey': recipient[0],
                            'txId': recipient[1],
                            'timestamp': recipient[2]
                        })

                    data = {
                        "message": record[0],
                        "hash": record[1],
                        "txId": record[2],
                        "id": record[3],
                        "attachmentHash": record[4],
                        "timestamp": record[5],
                        "recipient": record[6],
                        "forwardedTo": forwarded_to
                    }
                    sender = record[6]
                    if alice == sender:
                        data['type'] = 'outgoing'
                    else:
                        data['type'] = 'incoming'
                        
                    cdms.insert(0, data)


    except Exception as error:
        return bad_request(error)
    
    return cdms

cdms.add_route(Cdms.as_view(), '/')
cdms.add_route(Cdms.as_view(), '/<alice>/<bob>')
