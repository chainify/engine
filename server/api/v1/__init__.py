from sanic import Blueprint
from .cdms import cdms
from .ipfs import ipfs
from .accounts import accounts
from .groups import groups

api_v1 = Blueprint.group(
  cdms,
  ipfs,
  accounts,
  groups,
  url_prefix='/v1'
)


