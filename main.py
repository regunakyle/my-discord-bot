from bot import MyClient
import configparser

config = configparser.ConfigParser()
config.read('app.cfg')
TOKEN = config['Discord']['TOKEN']

client = MyClient()
client.run(TOKEN)