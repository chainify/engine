from sanic import Blueprint
from .cdms import cdms
from .ipfs import ipfs
from .accounts import accounts
from .groups import groups
from .last_cdm import last_cdm

api_v1 = Blueprint.group(
  cdms,
  ipfs,
  accounts,
  groups,
  last_cdm,
  url_prefix='/v1'
)


