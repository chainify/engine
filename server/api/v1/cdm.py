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
from .ipfs import create_ipfs_file, read_ipfs_file
from time import time
import websockets
import contextvars
import collections
import pywaves as pw

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
        recipient = recipient,
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
                    SELECT t.cnfy_id, t.id, c.sender, c.recipient, c.message, c.hash, c.signature, t.timestamp
                    FROM cdms c
                    LEFT JOIN transactions t ON c.tx_id = t.id
                    WHERE ((c.sender='{alice}' AND c.recipient='{bob}') 
                    OR (c.sender='{bob}' AND c.recipient='{alice}'))
                    AND t.valid = 1
                    ORDER BY t.timestamp DESC""".format(
                        alice=alice,
                        bob=bob
                    ))
                records = cur.fetchall()

                cdms = []
                for record in records:
                    data = {
                        "id": record[0],
                        "txId": record[1],
                        "sender": record[2],
                        "recipient": record[3],
                        "message": record[4],
                        "hash": record[5],
                        "signature": record[6],
                        "timestamp": record[7]
                    }

                    if record[2] != record[3]:
                        data['type'] = 'incoming' if record[2] == bob else 'outgoing'
                    else:
                        data['type'] = 'outgoing'

                    cdms.insert(0, data)


    except Exception as error:
        return bad_request(error)
    
    return cdms

def get_cdms1(alice, bob):
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


                    if tx[1] != tx[2]:
                        msg_type = 'incoming' if tx[1] == bob else 'outgoing'
                    else:
                        msg_type = 'outgoing'


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

                    cdms.insert(0, data)

    except Exception as error:
        return bad_request(error)
    
    return cdms

cdm.add_route(Cdm.as_view(), '/')
cdm.add_route(Cdm.as_view(), '/<alice>/<bob>')
