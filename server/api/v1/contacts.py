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
from .errors import bad_request
import configparser
import base58

contacts = Blueprint('contacts_v1', url_prefix='/contacts')
contact = Blueprint('contact_v1', url_prefix='/contact')

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


class Contact(HTTPMethodView):

    @staticmethod
    def post(request):
        account = request.form['account'][0]
        public_key = request.form['publicKey'][0]
        first_name = request.form['firstName'][0]
        last_name = request.form['lastName'][0]
        contact_id = str(uuid.uuid4())
        try:
            conn = psycopg2.connect(**dsn)
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM contacts
                        WHERE account='{account}'
                        AND public_key='{public_key}'
                    """.format(
                        account=account,
                        public_key=public_key
                    ))
                    count_records = cur.fetchone()[0]

                    if count_records == 0:
                        cur.execute("""
                            INSERT INTO contacts (id, account, public_key, first_name, last_name)
                            VALUES ('{id}', '{account}', '{public_key}', '{first_name}', '{last_name}')
                        """.format(
                            id=contact_id,
                            account=account,
                            public_key=public_key,
                            first_name=first_name,
                            last_name=last_name
                        ))
                    else:
                        cur.execute("""
                            UPDATE contacts SET first_name='{first_name}', last_name='{last_name}'
                            WHERE public_key='{public_key}'
                        """.format(
                            first_name=first_name,
                            last_name=last_name,
                            public_key=public_key
                        ))
                    conn.commit()
        except Exception as error:
            return bad_request(error)

        data = {
            'id': contact_id,
            'account': account,
            'publicKey': public_key,
            'firstName': first_name,
            'lastName': last_name
        }

        return json(data, status=201)


class Contacts(HTTPMethodView):
    @staticmethod
    def get(request, public_key):
        data = {
            'contacts': get_contacts(public_key)
        }
        return json(data, status=200 if data else 204)


def get_contacts(public_key):
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                        SELECT id, public_key, first_name, last_name, created FROM contacts
                        WHERE account='{public_key}'
                    """.format(
                        public_key=public_key
                    ))
                contacts = cur.fetchall()

    except Exception as error:
        return bad_request(error)

    data = [{
        'id': contact[0],
        'publicKey': contact[1],
        'firstName': contact[2],
        'lastName': contact[3],
        'created': contact[4]
    } for contact in contacts]

    return data


contact.add_route(Contact.as_view(), '/')
contacts.add_route(Contacts.as_view(), '/<public_key>')