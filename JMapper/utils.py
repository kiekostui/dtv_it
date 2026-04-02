import requests
import json
from datetime import datetime, UTC, timezone
import re

class NotValid:
    def __init__(self, message:str):
        self.error_message = message

class AnsiColors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    ENDC = '\033[00m'

class Logger:
    DEFAULT_LEVEL = 'INFO'

    @staticmethod
    def timestamp():
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

    @staticmethod
    def log_message(message, level=DEFAULT_LEVEL):
        if not isinstance(message, str):
            print(f'{Logger.timestamp()} {AnsiColors.YELLOW}[WARNING]{AnsiColors.ENDC} Orginal message was not a string. Converted to string')
            out_message = str(message)
        else:
            out_message = message
        upper_level = str(level).upper()
        match upper_level:
            case 'ERROR':
                color = AnsiColors.RED
            case 'WARNING':
                color = AnsiColors.YELLOW
            case 'INFO':
                color = AnsiColors.CYAN
            case 'DEBUG':
                color = AnsiColors.GREEN
            case _:
                color = AnsiColors.WHITE
        print(f'{Logger.timestamp()} {color}[{upper_level}]{AnsiColors.ENDC} {out_message}')


class HTTP:

    @staticmethod
    def get_response(request_parts, is_json=False, debug=False, http_session=None):

        if http_session:
            handler = http_session
        else:
            handler = requests

        response = None
        req_method = request_parts.pop('method', 'GET').upper()
        timeout = request_parts.pop('timeout', 15)
        url = request_parts.pop('url', None)
        if not url:
            Logger.log_message(f'Missing url', level='ERROR')
            return None
        if debug:
            Logger.log_message(f'Try request to {url}', level='DEBUG')
        try:
            response = handler.request(req_method, url,timeout=timeout, **request_parts)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            Logger.log_message(f'Request to {url} failed: {e}', level='ERROR')
            if response is not None and hasattr(response, 'text'):
                Logger.log_message(f'Server response: {response.text[:200]}', level='ERROR')
            return None

        if is_json:
            try:
                response_json = response.json()
                return response_json
            except:
                Logger.log_message(f'Response is not a valid json', level='ERROR')
                return None

        return response


    '''utility for to convert date format'''

class DateManager:

    @staticmethod
    def format_date_epg(date_object, log_fail=True):
        '''Convert date and time to epg format ('YYYYmmddHHMMSS +/-hh:mm'). Return void string in case of ERROR'''
        try:
            # try conversion from ISO 8601 formatted date
            date_obj = datetime.fromisoformat(date_object)
            if date_obj.tzinfo:
                date_formatted = date_obj.strftime('%Y%m%d%H%M%S %z')
            else:
                date_formatted = date_obj.strftime('%Y%m%d%H%M%S +0000')
            return date_formatted
        except Exception:
            pass

        try:
            date_obj = datetime.fromtimestamp(date_object, tz=timezone.utc)
            date_formatted = date_obj.strftime('%Y%m%d%H%M%S +0000')
            return date_formatted
        except Exception:
            pass
        if log_fail:
            Logger.log_message(f'Failed to convert date: {str(date_object)}', level='ERROR')
        return ''



def clean_path(path):
    if not isinstance(path, (list,str)):
        raise ValueError(f'Argument path must be a string or list', 'ERROR')
    elif isinstance(path, str):
        tokenized_path = path.replace(r'\.', '__DOT__').replace(r'\#', '__HASH__').replace(r'\ ','__SPACE__')
        cleaned_tokenized = [k.strip('# ') for k in tokenized_path.split('.') if k.strip('# ')]
    elif isinstance(path, list):
        tokenized_list = [str(k).replace(r'\.', '__DOT__').replace(r'\#', '__HASH__').replace(r'\ ','__SPACE__') for k in path]
        cleaned_tokenized = [str(k).strip('# ') for k in tokenized_list if str(k).strip('# ')]
    clean_path = [k.replace('__DOT__', '.').replace('__HASH__', '#').replace('__SPACE__', ' ') for k in cleaned_tokenized]
    return clean_path