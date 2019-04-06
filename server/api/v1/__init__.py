from sanic import Blueprint
from .cdm import cdm
from .ipfs import ipfs
from .accounts import accounts
from .accounts import account
from .interlocutors import interlocutors
from .transactions import transactions
from .faucet import faucet
from .sql import sql

api_v1 = Blueprint.group(
  cdm,
  ipfs,
  account,
  accounts,
  interlocutors,
  transactions,
  faucet,
  sql,
  url_prefix='/v1'
)


