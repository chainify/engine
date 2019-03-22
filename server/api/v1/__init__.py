from sanic import Blueprint
from .cdm import cdm
from .ipfs import ipfs
from .accounts import accounts
from .accounts import account
from .transactions import transactions
from .faucet import faucet

api_v1 = Blueprint.group(
  cdm,
  ipfs,
  account,
  accounts,
  transactions,
  faucet,
  url_prefix='/v1'
)


