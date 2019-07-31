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
        last_timestamp = request.args['lastTimestamp'][0] if 'lastTimestamp' in request.args else None
        data = {
            'groups': get_groups(alice, last_timestamp)
        }
        return json(data, status=200)


def get_groups(alice, last_timestamp):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                query = """     
                    SELECT DISTINCT
                        c.group_hash,
                        array(
                            SELECT DISTINCT cc.recipient
                            FROM cdms cc
                            WHERE cc.group_hash = c.group_hash
                        ) as cdms,
                        c.timestamp
                    FROM cdms c
                    WHERE c.recipient = '{alice}'
                    AND c.timestamp IN (
                        SELECT max(cc.timestamp)
                        FROM cdms cc
                        WHERE cc.group_hash = c.group_hash
                    )
                """.format(
                    alice=alice
                )
                if last_timestamp:
                    query = query + "AND c.timestamp > (SELECT to_timestamp({last_timestamp}) AT TIME ZONE 'UTC')\n".format(
                        last_timestamp=last_timestamp
                    )

                query = query + 'ORDER BY c.timestamp DESC'
                cur.execute(query)
                records = cur.fetchall()

                nolilPublicKey = 'cEdRrkTRMkd61UdQHvs1c2pwLfuCXVTA4GaABmiEqrP'
                nolikGroupHash = hashlib.sha256(''.join(sorted([alice, nolilPublicKey])).encode('utf-8')).hexdigest()
                nolikCdms = get_cdms(alice, nolikGroupHash)

                
                # if alice != nolilPublicKey:
                #     groups.append({
                #         'members': [alice, nolilPublicKey],
                #         'groupHash': nolikGroupHash,
                #         'totalCdms': len(nolikCdms),
                #         'lastCdm': None if len(nolikCdms) == 0 else nolikCdms[-1]
                #     })

                # group_hashes = [nolikGroupHash]
                groups = []
                group_hashes = []
                for record in records:
                    group_hash = record[0]
                    if (group_hash in group_hashes):
                        continue
                    members = record[1]
                    cdms = get_cdms(alice, group_hash)
                    group = {
                        'members': members,
                        'groupHash': group_hash,
                        'totalCdms': len(cdms),
                        'lastCdm': None if len(cdms) == 0 else cdms[-1]
                    }
                    groups.append(group)

                

    except Exception as error:
        return bad_request(error)
    
    return groups


groups.add_route(Groups.as_view(), '/<alice>')
# groups.add_route(Groups.as_view(), '/<alice>/<lasl_cdm_hash>')