import os
import sys
import re
from sanic import Blueprint
from sanic.response import json
from sanic.log import logger
import asyncio
import aiohttp
import requests
import psycopg2
import json as pjson
from psycopg2.extras import execute_values
import sendgrid
from sendgrid.helpers.mail import *
from hashlib import blake2b
from datetime import datetime
from time import time
from .errors import bad_request
import configparser
import uuid
import signal
import subprocess
import base58

config = configparser.ConfigParser()
config.read('config.ini')

parser = Blueprint('parser_v1', url_prefix='/parser')
# email = sendgrid.SendGridAPIClient(apikey=config['email']['api_key'])
dsn = {
    "user": config['DB']['user'],
    "password": config['DB']['password'],
    "database": config['DB']['database'],
    "host": config['DB']['host'],
    "port": config['DB']['port'],
    "sslmode": config['DB']['sslmode']
}


class Parser:
    def __init__(self):
        self.height = 1
        self.last_block = None
        self.step = 5
        self.blocks_to_check = 5

        self.db_reconnects = 0
        self.db_max_reconnects = 10
        self.transactions_inserted = 0

        self.sql_data_transactions = []
        self.sql_data_proofs = []
        self.sql_data_cdms = []

    async def emergency_stop_loop(self, title, error):
        # email_body = """
        #     <html><body><h2>{0}</h2><h3>Height: {1}</h3><h3>Error: {2}</h3></body></html>
        # """.format(title, self.height, error)
        # logger.info('Sending email')
        # from_email = Email("noreply@chainify.org")
        # to_email = Email('aboziev@gmail.com')
        # subject = "Parser error detected"
        # email_content = Content("text/html", email_body)
        # sg_mail = Mail(from_email, subject, to_email, email_content)
        # response = email.client.mail.send.post(request_body=sg_mail.get())
        # logger.info('Email sent. Status code {0}'.format(response.status_code))

        logger.info('Emergency loop stop request')
        logger.error(error)
        logger.info('Closing tasks')
        for task in asyncio.Task.all_tasks():
            task.cancel()

        logger.info('Stopping loop')
        loop = asyncio.get_running_loop()
        loop.stop()
        return bad_request(error)

    async def fetch_data(self, url, session):
        try:
            async with session.get(url) as response:
                data = await response.text()
                data = pjson.loads(data)
                cnfy_id = 'cnfy-{}'.format(str(uuid.uuid4()))
                for tx in data['transactions']:
                    if tx['type'] in [4] and tx['feeAssetId'] == config['blockchain']['asset_id']:
                        tx_data = (
                            tx['id'],
                            data['height'],
                            tx['type'],
                            tx['sender'],
                            tx['senderPublicKey'],
                            tx['recipient'],
                            tx['amount'],
                            tx['assetId'],
                            tx['feeAssetId'],
                            tx['feeAsset'],
                            tx['fee'],
                            tx['attachment'],
                            tx['version'],
                            datetime.fromtimestamp(tx['timestamp'] / 1e3),
                            cnfy_id
                        )

                        self.sql_data_transactions.append(tx_data)

                        for proof in tx['proofs']:
                            self.sql_data_proofs.append((tx['id'], proof))
                        
                        attachment_base58 = base58.b58decode(tx['attachment']).decode('utf-8')
                        attachment = requests.get('{0}:{1}/ipfs/{2}'.format(config['ipfs']['host'], config['ipfs']['get_port'], attachment_base58)).text

                        sha256_hash = None
                        sender = None
                        signature = None

                        sha256_regex = r"^-----BEGIN_SHA256-----$\n(.*)\n^-----END_SHA256-----$"
                        sha256_matches = re.finditer(sha256_regex, attachment, re.MULTILINE)

                        for match in sha256_matches:
                            sha256_hash = match.groups()[0]

                        signature_regex = r"^-----BEGIN_SIGNATURE (.*)-----$\n(.*)\n^-----END_SIGNATURE (.*)-----$"
                        signature_matches = re.finditer(signature_regex, attachment, re.MULTILINE)

                        for match in signature_matches:
                            sender = match.groups()[0]
                            signature = match.groups()[1]

                        messages_regex = r"^-----BEGIN_PK (.*)-----$\n(.*)\n^-----END_PK (.*)-----$"
                        messages_matches = re.finditer(messages_regex, attachment, re.MULTILINE)

                        for match in messages_matches:
                            cdm_id = str(uuid.uuid4())
                            recipient = match.groups()[0]
                            message = match.groups()[1]
                            self.sql_data_cdms.append((
                                cdm_id, tx['id'], sender, recipient, message, sha256_hash, signature))

        except asyncio.CancelledError:
            logger.info('Parser has been stopped')
            raise
        except Exception as error:
            logger.error(error)
            await self.emergency_stop_loop('Fetch data', error)

    async def save_data(self):
        conn = psycopg2.connect(**dsn)
        try:
            with conn:
                with conn.cursor() as cur:
                    if len(self.sql_data_transactions) > 0:
                        sql = """INSERT INTO transactions (id, height, type, sender, sender_public_key, recipient,
                        amount, asset_id, fee_asset_id, fee_asset, fee, attachment, version, timestamp, cnfy_id)
                        VALUES %s ON CONFLICT (id) DO UPDATE SET height = EXCLUDED.height"""
                        execute_values(cur, sql, self.sql_data_transactions)
                        if cur.rowcount > 0:
                            self.transactions_inserted += cur.rowcount

                        sql = """INSERT INTO proofs (tx_id, proof) VALUES %s ON CONFLICT DO NOTHING"""
                        execute_values(cur, sql, self.sql_data_proofs)

                        sql = """INSERT INTO cdms (id, tx_id, sender, recipient, message, hash, signature)
                        VALUES %s ON CONFLICT DO NOTHING"""
                        execute_values(cur, sql, self.sql_data_cdms)

                    conn.commit()
                    logger.info('Saved {0} transactions'.format(self.transactions_inserted))

        except psycopg2.IntegrityError:
            pass
        except asyncio.CancelledError:
            logger.info('Parser has been stopped')
            raise
        except Exception as error:
            logger.info('Height: {}'.format(self.height))
            logger.error('Batch insert error: {}'.format(error))
            await self.emergency_stop_loop('Batch insert error', error)
        finally:
            self.transactions_inserted = 0
            self.sql_data_transactions = []
            self.sql_data_proofs = []

    async def start(self):
        conn = psycopg2.connect(**dsn)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT max(height) FROM transactions")
                    max_height = cur.fetchone()

                    if max_height and max_height[0]:
                        if max_height[0] > self.blocks_to_check:
                            self.height = max_height[0] - self.blocks_to_check

                    if config['blockchain']['start_height']:
                        start_height = int(config['blockchain']['start_height'])
                        if self.height < start_height:
                            self.height = start_height

        except Exception as error:
            logger.error('Max height request error: {}'.format(error))
            await self.emergency_stop_loop('Max height request error', error)

        while True:
            try:
                req = requests.get('{0}/node/status'.format(config['blockchain']['host']))
                data = req.json()
                self.last_block = int(data['blockchainHeight'])
            except Exception as error:
                await self.emergency_stop_loop('Waves node is not responding', error)

            logger.info('Start height: {}, last block: {}'.format(self.height, self.last_block))
            logger.info('-' * 40)
            try:
                async with aiohttp.ClientSession() as session:
                    try:
                        while self.height < self.last_block:
                            t0 = time()
                            batch = self.height + self.step
                            if self.height + self.step >= self.last_block:
                                batch = self.last_block + 1

                            batch_range = (self.height, batch)
                            tasks = []
                            for i in range(batch_range[0], batch_range[1]):
                                url = '{0}/blocks/at/{1}'.format(config['blockchain']['host'], self.height)
                                task = asyncio.create_task(self.fetch_data(url, session))
                                tasks.append(task)
                                self.height += 1
                            logger.info('Height range {0} - {1}'.format(batch_range[0], batch_range[1]))
                            await asyncio.gather(*tasks)
                            await self.save_data()
                            logger.info('Parsing time: {0} sec'.format(time() - t0))
                            logger.info('-' * 40)

                    except asyncio.CancelledError:
                        logger.info('Parser stopping...')
                        raise
                    except Exception as error:
                        logger.error('Blocks session cycle error on height {0}: {1}'.format(self.height, error))
                        await self.emergency_stop_loop('Blocks session cycle error', error)

            except asyncio.CancelledError:
                logger.info('Parser has been stopped')
                raise
            except Exception as error:
                logger.error('Request blocks cycle error: {0}'.format(error))
                await self.emergency_stop_loop('Request blocks cycle', error)
            finally:
                self.height = self.height - self.blocks_to_check
                await asyncio.sleep(2)


controls = Parser()

@parser.listener('after_server_start')
def autostart(app, loop):
    loop.create_task(controls.start())
    logger.info('Autostart Success!')

@parser.listener('after_server_stop')
def gentle_exit(app, loop):
    logger.info('Killing the process')
    os.kill(os.getpid(), signal.SIGKILL)

@parser.route('/start', methods=['POST'])
def controls_start(request):
    loop = asyncio.get_running_loop()
    loop.create_task(controls.start())
    return json({"action": "start", "status": "OK"})

@parser.route('/healthcheck', methods=['GET'])
def container_healthcheck(request):
    return json({"action": "healthcheck", "status": "OK"})


@parser.route('/stop', methods=['POST'])
def controls_stop(request):
    try:
        loop = asyncio.get_running_loop()
        tasks = [t for t in asyncio.all_tasks() if t is not
                 asyncio.current_task()]

        [task.cancel() for task in tasks]

        logger.info('Canceling outstanding tasks')
        asyncio.gather(*tasks)
        loop.stop()
        logger.info('Shutdown complete.')

    except Exception as error:
        return bad_request(error)

    return json({"action": "stop", "status": "OK"})
