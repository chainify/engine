from sanic import Sanic
from api import api_v1
import configparser

from sanic_cors import CORS, cross_origin

config = configparser.ConfigParser()
config.read('config.ini')

app = Sanic('engine')
app.blueprint(api_v1)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

if __name__ == "__main__":
    app.run(
        debug=config['app']['debug'] == 'true',
        host=config['app']['host'],
        port=int(config['app']['port']),
        workers=int(config['app']['workers'])
    )
