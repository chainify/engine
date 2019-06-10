from sanic import Blueprint
from .cdm import cdm
from .ipfs import ipfs
from .accounts import accounts
from .accounts import account
from .interlocutors import interlocutors
from .sql import sql
from .contacts import contact, contacts

api_v1 = Blueprint.group(
  cdm,
  ipfs,
  account,
  accounts,
  contact,
  contacts,
  interlocutors,
  sql,
  url_prefix='/v1'
)


