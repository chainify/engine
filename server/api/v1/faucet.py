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
from .errors import bad_request
import configparser
import base58
import pywaves as pw

faucet = Blueprint('faucet_v1', url_prefix='/faucet')

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


class Faucet(HTTPMethodView):

    def __init__(self):
        self.amount = 100000000

    def post(self, request):
    
        if 'address' not in request.form:
            return bad_request('Address is not provided')

        address = request.form['address'][0]

        pw.setNode(config['blockchain']['host'], 'testnet')
        root = pw.Address(seed=config['blockchain']['root_seed'])
        asset = pw.Asset(config['blockchain']['asset_id'])
        recipient = pw.Address(address)

        try:
            tx = root.sendAsset(
                recipient=recipient,
                asset=asset,
                amount=self.amount
            )

            try:
                conn = psycopg2.connect(**dsn)
                with conn:
                    with conn.cursor() as cur:
                        faucet_id = str(uuid.uuid4())
                        cur.execute("""
                            INSERT INTO faucet (id, address, amount, tx_id)
                            VALUES ('{id}', '{address}', '{amount}', '{tx_id}')
                        """.format(
                                id=faucet_id,
                                address=address,
                                amount=self.amount,
                                tx_id=tx['id']
                            ))

                        conn.commit()

            except Exception as error:
                logger.error(error)
                return bad_request(error)
        except Exception as error:
            logger.error(error)
            return bad_request(error)

        data = {
            'address': address,
            'amount': self.amount,
            'id': faucet_id,
            'tx': tx
        }

        return json(data, status=201)



faucet.add_route(Faucet.as_view(), '/')