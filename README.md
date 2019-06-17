# CDM backend engine

[CDM protocol](https://chainify.org/protocol.html) is designed to securely exchange information in Web 3.0 applications.


Check [Nolik Instant Messenger](https://nolik.im) that was build based on CDM protocol. Nolik does not store personal data and even does not store the messages. CDM protocol cryptographically guarantees that no one except Alice and Bob will have access to the content of the message.

Current realization is based on [Waves platform](https://wavesplatform.com) blockchain.

## How it works
Alice and Bob are going to have a conversation using Nolik. Each of them already installed the [Waves Keeper](https://wavesplatform.com/products-keeper) browser extension and created accounts. In order to use Nolik Alice and Bob simply log in with Waves Keeper and get personalized content without any registration.

Bob sends to Alice (with regular communication services) his public key. With that public key Alice encrypts the message and signs it on a client. That signed message is sent to the CDM engine API endpoint and saves to IPFS network.

CDM engine contains IPFS endpoint, Waves blockchain parser, and an API endpoint. Each of the mentioned parts runs in a separate docker container.

### IPSF endpoint
IPFS is a [protocol](https://ipfs.io) that allows to save files with a unique address and access them from any IPFS node.

After successful saving IPFS endpoint returns a unique hash - the file address that is generated based on file content (same file => same hash). That file is attached to blockchain transaction that is broadcasted to blockchain network with API endpoint.

### API endpoint
In order to send the transaction someone hash to pay a transaction fee. Currently, at Nolik all transaction s are free for users and paid by Chainify team. However, in this scenario, Alice and Bob have to trust Chainify that the transaction will be sent. It is possible to broadcast the transaction directly from the client but in this case, Alice and Bob will have to pay transaction fee but they will have a guarantee that the transaction will be broadcasted. 

### The parser
So the transaction is broadcasted and saved to the blockchain. The parser monitors every transaction and saves to the Postgres database transactions and the content of the attached file. The message is encrypted and Nolik does not know the decryption keys (only Alice and Bob know them and store them in Waves keeper extension). Parser duplicates the blockchain transaction only for the purpose of increasing productivity.

## Installation

You can use [Nolik](https://nolik.im) for secure messaging or use CDM engine and Nolik frontend locally or at your cloud server. In this case, you will have to provide (in the config file) the seed phrase of a Sponsor account that will pay for the transactions.

Make sure that you have [Docker](https://docker.com) installed on your machine.

```
mkdir cdm && cd cdm
git clone git@github.com:chainify/engine.git .
```

### Config the database

Run SQL script at PostgreSQL database.

```
create table transactions
(
  id                varchar(255) not null
    constraint transactions_pk
      primary key,
  height            integer      not null,
  type              integer      not null,
  sender            varchar(255) not null,
  sender_public_key varchar(255) not null,
  recipient         varchar(255) not null,
  amount            bigint,
  asset_id          varchar(255) default NULL::character varying,
  fee_asset_id      varchar(255) default NULL::character varying,
  fee_asset         varchar(255),
  fee               bigint,
  attachment        varchar(255),
  version           integer      not null,
  timestamp         timestamp    not null,
  cnfy_id           varchar(255),
  valid             integer      default 1,
  attachment_hash   varchar(255) not null
);

alter table transactions
  owner to root;

create index transactions_fee_asset_id_index
  on transactions (fee_asset_id);

create index transactions_recipient_index
  on transactions (recipient);

create index transactions_sender_index
  on transactions (sender);

create index transactions_asset_id_index
  on transactions (asset_id);

create index transactions_tx_id_index
  on transactions (cnfy_id);

create table proofs
(
  tx_id varchar(255) not null
    constraint proofs_transactions_id_fk
      references transactions
      on update cascade on delete cascade,
  proof varchar(255),
  id    serial       not null
    constraint proofs_pk
      primary key
);

alter table proofs
  owner to root;

create unique index proofs_tx_id_proof_uindex
  on proofs (tx_id, proof);

create table cdms
(
  id        varchar(255) not null
    constraint cdms_pk
      primary key,
  tx_id     varchar(255) not null
    constraint cdms_transactions_id_fk
      references transactions
      on update cascade on delete cascade,
  recipient varchar(255) not null,
  message   text         not null,
  hash      varchar(255),
  timestamp timestamp default CURRENT_TIMESTAMP
);

alter table cdms
  owner to root;

create index cdms_tx_id_index
  on cdms (tx_id);

create index cdms_recipient_index
  on cdms (recipient);

create unique index cdms_tx_id_hash_uindex
  on cdms (tx_id, hash);

create table accounts
(
  public_key  varchar(255) not null
    constraint accounts_pk
      primary key,
  last_active timestamp default CURRENT_TIMESTAMP,
  created     timestamp default CURRENT_TIMESTAMP
);

alter table accounts
  owner to root;

create table contacts
(
  id         varchar(255) not null
    constraint contacts_pk
      primary key,
  account    varchar(255) not null
    constraint contacts_accounts_public_key_fk
      references accounts
      on update cascade on delete cascade,
  public_key varchar(255) not null,
  first_name varchar(255),
  last_name  varchar(255),
  created    timestamp default CURRENT_TIMESTAMP
);

alter table contacts
  owner to root;

create unique index contacts_account_public_key_uindex
  on contacts (account, public_key);

create table senders
(
  id        varchar(255) not null
    constraint s_pk
      primary key,
  tx_id     varchar(255)
    constraint senders_transactions_id_fk
      references transactions
      on update cascade on delete cascade,
  sender    varchar(255),
  signature text,
  verified  boolean   default false,
  timestamp timestamp default CURRENT_TIMESTAMP
);

alter table senders
  owner to root;

create index senders_sender_index
  on senders (sender);

create unique index senders_tx_id_sender_uindex
  on senders (tx_id, sender);

create index senders_tx_id_index
  on senders (tx_id);

```

### Update config.ini files

#### API endpoint at `server/config.ini`

```
[DB]
user = root
password = pass
database = chainify
host = postgres
port = 5432
sslmode = disable

[app]
workers = 1
debug = true
host = 0.0.0.0
port = 8080
origins = http://localhost:3000

[aes]
iv = AES_IV #Example VSzLK9dYPESM1Tk7
key = AES_KEY #Example VEhdtAbCAPjdGUWCU39nBQpN95JSRmCP

[blockchain]
host = https://testnodes.wavesnodes.com
network = testnet
asset_id = ASSET_ID #Example 5BRZ5qVLtCR9vGtjdNdmRtuSqq5uRDe275m4EdPLoqr9
root_seed = ROOT_WALLEST_SEED_KEY #Example cube tumble fly day drift manage square paper toddler rebuild word prosper peanut despair unveil

[email]
api_key = EMAIL_PROVIDER_API_KEY #example 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

[ipfs]
host = http://ipfs
post_port = 5001
get_port = 8080
```

#### Parser service at `parser/config.ini`
```
[DB]
user = root
password = pass
database = chainify
host = postgres
port = 5432
sslmode = disable

[app]
workers = 1
debug = true
host = 0.0.0.0
port = 8080

[blockchain]
start_height = null
host = https://testnode1.wavesnodes.com
asset_id = ASSET_ID
priv_key = ACCOUNT_PRIVATE_KEY

[email]
api_key = EMAIL_PROVIDER_API_KEY
```

### Run the docker containers
```
docker-compose up -d
```

