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

transactions = Blueprint('transactions_v1', url_prefix='/transactions')


class Transactions(HTTPMethodView):

    def get(self, request, id):
        conn = psycopg2.connect(**dsn)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT t.id, t.sender, t.recipient, t.attachment, t.timestamp, acs.name, acr.name
                        FROM transactions t
                        JOIN accounts acs ON acs.address = t.sender
                        JOIN accounts acr ON acr.address = t.recipient
                        WHERE t.cnfy_id='{id}'""".format(id=id))
                    tx = cur.fetchone()

        except Exception as error:
            return bad_request(error)

        if not tx:
            return '', 204

        data = {
            "tx": {
                "id": tx[0],
                "sender": tx[1],
                "recipient": tx[2],
                "ipfsHash": base58.b58decode(tx[3]).decode("utf-8"),
                "timestamp": tx[4],
                "senderName": tx[5],
                "recipientName": tx[6]
            }
        }

        return json(data, status=200)


transactions.add_route(Transactions.as_view(), '/<id>')