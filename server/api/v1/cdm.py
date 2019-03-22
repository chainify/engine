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

    def get(self, request, address):
        conn = psycopg2.connect(**dsn)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, sender, recipient, attachment, timestamp, cnfy_id FROM transactions
                        WHERE fee_asset_id='{asset_id}' AND (sender='{address}' OR recipient='{address}')
                        ORDER BY timestamp DESC""".format(
                            asset_id=config['blockchain']['asset_id'],
                            address=address
                        ))
                    transactions = cur.fetchall()

                    messages = collections.OrderedDict()
                    files = {"saved": []}
                    accounts = []
                    for tx in transactions:
                        ipsf_hash = base58.b58decode(tx[3]).decode("utf-8")
                        ipfs_data = read_ipfs_file(ipsf_hash)

                        msg_type = 'outgoing' if tx[1] == address else 'incoming'

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

                        interlocutor = data['recipient'] if data['sender'] == address else data['sender']

                        if data['sender'] == data['recipient']:
                            files['saved'].append(data)
                        else:
                            if interlocutor in messages: 
                                messages[interlocutor]['txs'].insert(0, data)
                            else:
                                account = get_account(interlocutor)
                                if account:
                                    messages[interlocutor] = {
                                        'account': account,
                                        'txs': [data]
                                    }
                                    accounts.append(interlocutor)

        except Exception as error:
            return bad_request(error)

        data = {
            'messages': messages,
            'files': files,
            'accounts': accounts
        }

        return json(data, status=200)


cdm.add_route(Cdm.as_view(), '/<address>')