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
    def get(request, alice, group_hash):
        data = {
            'cdms': get_cdms(alice, group_hash)
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


def get_last_cdm(alice):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.attachment_hash
                    FROM cdms c
                    LEFT JOIN transactions t ON t.id = c.tx_id
                    WHERE c.recipient='{alice}'
                    ORDER BY t.timestamp DESC
                    LIMIT 1
                """.format(
                    alice=alice
                ))
                cdm = cur.fetchone()


    except Exception as error:
        return bad_request(error)
    
    return cdm


def get_cdms(alice, group_hash):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                sql = """
                    SELECT
                        c.message,
                        c.hash,
                        t.id,
                        c.id,
                        t.attachment_hash,
                        t.timestamp,
                        t.sender_public_key,
                        c.recipient,
                        c.group_hash,
                        s.sender,
                        c.timestamp,
                        (
                            SELECT min(tt.timestamp)
                            FROM cdms cc
                            LEFT JOIN transactions tt on cc.tx_id = tt.id
                            WHERE cc.hash = c.hash
                        ) as min_ts
                    FROM cdms c
                    LEFT JOIN transactions t on c.tx_id = t.id
                    LEFT JOIN senders s ON s.cdm_id = c.id
                    WHERE c.group_hash='{group_hash}'
                    AND c.recipient='{alice}'
                    ORDER BY min_ts ASC
                    """.format(
                        group_hash=group_hash,
                        alice=alice
                    )

                cur.execute(sql)
                records = cur.fetchall()

                cdms = []
                for record in records:
                    cur.execute("""
                        SELECT c.recipient, c.tx_id, c.timestamp
                        FROM cdms c
                        WHERE c.hash='{hash}'
                        ORDER BY timestamp
                    """.format(
                        hash=record[1],
                        groupHash=record[7]
                    ))
                    recipients = cur.fetchall()
                    shared_with = []
                    for recipient in recipients:
                        shared_with.append({
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
                        "realSender": record[6],
                        "logicalSender": record[9] or record[6],
                        "recipient": record[7],
                        "sharedWith": shared_with
                    }
                    sender = record[9] or record[6]
                    if alice == sender:
                        data['type'] = 'outgoing'
                    else:
                        data['type'] = 'incoming'
                        
                    cdms.append(data)


    except Exception as error:
        return bad_request(error)
    
    return cdms

cdms.add_route(Cdms.as_view(), '/')
cdms.add_route(Cdms.as_view(), '/<alice>/<group_hash>')
