import requests
import re
import json
from datetime import datetime, UTC
from JMapper.utils import Logger

def generate_id(name):
    name = name.lower().strip()
    name = name.replace('&', 'and').replace('+','plus')
    name = re.sub(r'[\s\-\/]+', '.', name)
    name = re.sub(r'[^a-z0-9\.]', '', name)
    name = re.sub(r'\.+', '.', name).strip('.')
    return f'{name}.it'

def extract_channels(json_channel):
    icon_prefix = 'https://services.sg101.prd.sctv.ch/content/images/tv/channel/'
    icon_suffix = '_image_7_w90.png'
    master_channels = {}
    for channel in json_channel:
        languages = channel.get('Languages', [])
        if not 'it' in languages:
            continue
        status = channel.get('State', 'Active')
        if status != 'Active':
            continue
        blue_id = channel.get('Identifier', None)
        name = channel.get('Title', 'NoName')
        if name.startswith(('3D Demo', 'blue', 'Test Italia', 'Netflix', 'Session', 'Enjoy St.', 'MySports', 'Amazon', 'ALTAMEGA Plus', 'EU Parliament', 'RAI Italia', 'Explorer', 'Best of ESC I', 'Info Channel', 'The Filmclub', 'HBO Max App')):
            continue
        icon = icon_prefix + blue_id + icon_suffix
        ch_id = generate_id(name)
        if blue_id:
           master_channels[blue_id]= {
               'id':ch_id,
               'name':name,
               'icon':icon,
               'programs':[
                    ['$program', {
                        'title':'',
                        'subtitle':'',
                        'description':'',
                        'duration':'',
                        'start':'',
                        'end': '',
                        'poster':None
                        }
                     ]
                ]
           }
    Logger.log_message(f'{len(master_channels)} Channels extracted', 'INFO')
    return master_channels
            
def get_channel():
    url = 'https://services.sg101.prd.sctv.ch/portfolio/tv/channels'
    headers={
    'accept':'application/json, text/plain, */*',
    'referer':'https://tv.blue.ch/',
    'sec-ch-ua':'"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    'user-agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        Logger.log_message(f'Channels request to {url} successful', 'INFO')
    except requests.exceptions.RequestException as e:
        logger.log_message(f'Channels request to {url} failed: {e}', 'ERROR')
        return None

    try:
        json_response = response.json()
    except json.JSONDecodeError:
        logger.log_message(f'Impossible to retrieve Channels using url {url}: no json to process', 'ERROR')
        logger.log_message(f'Response text: {response.text}', 'ERROR')
        return None
    logger.log_message(f'Channels obtained', 'INFO')
    return json_response

####################### main #########################################
start_time = datetime.now(UTC)
logger.log_message('Program started', 'INFO')
logger.log_message('Getting channels', 'INFO')
json_channel = get_channel()
if json_channel:
    master_channels = extract_channels(json_channel)

if master_channels:
    with open('master_channels.json', 'w') as f:
        json.dump(master_channels, f, indent=4)
else:
    logger.log_message('No channels found', 'ERROR')
