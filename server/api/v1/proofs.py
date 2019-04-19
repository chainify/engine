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

proofs = Blueprint('proofs_v1', url_prefix='/proofs')


class Proof(HTTPMethodView):
    @staticmethod
    def get(request, proof):
        
        data = {
            'proofs': get_proofs(proof),
        }

        return json(data, status=200)


def get_proofs(proof):
    major = '3N2ZM62bx8vUkpLjqqib1796uohShJBjSfj'
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM proofs p
                    LEFT JOIN transactions t ON p.tx_id = t.id
                    WHERE sender='{major}'
                    AND proof='{proof}'
                    AND t.valid = 1
                    """.format(
                        major=major,
                        proof=proof
                    ))
                proofs = cur.fetchone()[0]

    except Exception as error:
        return bad_request(error)
    
    return proofs

proofs.add_route(Proof.as_view(), '/<proof>')
