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
    "sslmode": config['DB']['sslmode']
}


class Contact(HTTPMethodView):

    @staticmethod
    def post(request):
        account = request.form['account'][0]
        public_key = request.form['publicKey'][0]
        name = request.form['name'][0]
        contact_id = str(uuid.uuid4())
        try:
            conn = psycopg2.connect(**dsn)
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO contacts (id, account, public_key, name)
                        VALUES ('{id}', '{account}', '{public_key}', '{name}')
                    """.format(
                        id=contact_id,
                        account=account,
                        public_key=public_key,
                        name=name
                    ))
                    conn.commit()
        except Exception as error:
            return bad_request(error)

        data = {
            'publicKey': public_key,
        }

        return json(data, status=201)

    @staticmethod
    def put(request):
        account = request.form['account'][0]
        public_key = request.form['publicKey'][0]
        name = request.form['name'][0]

        try:
            conn = psycopg2.connect(**dsn)
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE contacts SET name='{name}'
                        WHERE account='{account}'
                        AND public_key='{public_key}'
                    """.format(
                        name=name,
                        account=account,
                        public_key=public_key
                    ))
                    conn.commit()
        except Exception as error:
            return bad_request(error)

        data = {
            'account': account,
            'publicKey': public_key,
            'name': name
        }

        return json(data, status=200)


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
                        SELECT id, public_key, name, created FROM contacts
                        WHERE account='{public_key}'
                    """.format(
                        public_key=public_key
                    ))
                contacts = cur.fetchone()

    except Exception as error:
        return bad_request(error)

    data = [{
        'id': contact[0],
        'publicKey': contact[1],
        'name': contact[2],
        'created': contact[3]
    } for contact in contacts]

    return data


contact.add_route(Contact.as_view(), '/')
contacts.add_route(Contacts.as_view(), '/<public_key>')