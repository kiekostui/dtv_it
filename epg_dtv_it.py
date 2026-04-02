import requests
import json
from datetime import datetime, timedelta, UTC, timezone
import time
import xml.etree.ElementTree as ET
from JMapper.JMapper import JMap, JMapError
from JMapper.JTemplate import JTemplate, JTemplateError
from JMapper.utils import Logger

epg_time_frame = 48  # finestra temporale in ore per l'epg
channels_chunk = 50  # numero canali per singola richiesta
timeframe_chunk = 4  # finestra temporale per singola richiesta
master_channels = 'master_channels.json'
epg_map = 'map.json'
epg_output = 'epg_tv_it.xml'


def date_converter(date_string):
    try:
        date_obj = datetime.fromisoformat(date_string)
        if date_obj.tzinfo:
            date_formatted = date_obj.strftime('%Y%m%d%H%M%S %z')
        else:
            date_formatted = date_obj.strftime('%Y%m%d%H%M%S +0000')
        return date_formatted
    except Exception:
        Logger.log_message(f'Failed to convert date: {date_string}', 'ERROR')
        return ''

def get_epg(id_chunk, chunk_start, chunk_end):
    time.sleep(1)
    url_prefix = 'https://services.sg101.prd.sctv.ch/catalog/tv/channels/list/'
    url_ids = ','.join(id_chunk)
    url_start = chunk_start.strftime('%Y%m%d%H%M')
    url_end = chunk_end.strftime('%Y%m%d%H%M')
    url =f'{url_prefix}(end={url_end};ids={url_ids};level=enorm;start={url_start})'
    headers={
    'accept':'application/json, text/plain, */*',
    'referer':'https://tv.blue.ch/',
    'sec-ch-ua':'"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    'user-agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    #'x-request-id':'64de5e7b-db6d-f40f-ccde-57c9227f377e_1773180023045'    
    }
    Logger.log_message(f'Requesting EPG from {url}', 'INFO')
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        Logger.log_message(f'Response code: {response.status_code}', 'INFO')
    except requests.exceptions.RequestException as e:
        Logger.log_message(f'Epg request to {url} failed: {e}', 'ERROR')
        return None
    try:
        json_response = response.json()
    except json.JSONDecodeError:
        Logger.log_message(f'Error in decode response from {url}: {response.text}', 'ERROR')
        return None
    Logger.log_message('Response processed', 'INFO')
    return json_response

# --- Convert JTemplate data to XML ---
def generate_xml(epg_template):
    epg_xml = ET.Element('tv')
    epg_xml.attrib['source-info-name'] = 'None'
    channel_nodes = epg_template.get_all_nodes('#.*')
    for channel in channel_nodes:
        ch_id = channel.get_node('id').value
        ch_name = channel.get_node('name').value
        ch_icon =  channel.get_node('icon').value
        channel_xml = ET.SubElement(epg_xml, 'channel', id=ch_id)
        name_xml = ET.SubElement(channel_xml, 'display-name')
        name_xml.text = ch_name
        icon_xml = ET.SubElement(channel_xml, 'icon', src=ch_icon)
    for channel in channel_nodes:
        program_nodes = channel.get_all_nodes('programs.*')
        for program in program_nodes:
            programme_xml = ET.SubElement(
                epg_xml, 'programme',
                start= date_converter(program.get_node('start').value),
                stop = date_converter(program.get_node('end').value),
                channel= channel.get_node('id').value
            )
            title_xml = ET.SubElement(programme_xml, 'title', lang='it')
            title_xml.text = program.get_node('title').value
            subtitle_xml = ET.SubElement(programme_xml, 'sub-title', lang='it')
            subtitle_xml.text = program.get_node('subtitle').value
            desc_xml = ET.SubElement(programme_xml, 'desc')
            desc_xml.text = program.get_node('description').value
            icon_xml = ET.SubElement(programme_xml, 'icon', src=program.get_node('poster').value)
    return epg_xml

####################### main #########################################

start_time = datetime.now(UTC)
Logger.log_message('Program started', 'INFO')
start = datetime(start_time.year, start_time.month, start_time.day, hour = start_time.hour)

delta_chunk = timedelta(hours=timeframe_chunk)

try:
    epg_template = JTemplate(json.load(open(f'{master_channels}')))
except JTemplateError as e:
    Logger.log_message(f'Failed to load master channel template. {e}', 'ERROR')
    epg_template = None
except FileNotFoundError:
    Logger.log_message(f'Failed to load master channel template. file "{master_channels}" does not exist', 'ERROR')
    epg_template = None
try:
    map = JMap(json.load(open(f'{epg_map}')))
except JMapError as e:
    Logger.log_message(f'Failed to load epg map\n{e}', 'ERROR')
    map = None
except FileNotFoundError:
    Logger.log_message(f'Failed to load epg map. file "{epg_map}" does not exist', 'ERROR')
    map = None
if epg_template and map:
    id_list = list(epg_template.loads().keys())
    start_index = 0
    end_index = start_index + channels_chunk
    #i=0
    while start_index <= len(id_list) - 1:
        id_chunk = id_list[start_index:end_index]
        chunk_start = start
        chunk_end = chunk_start + delta_chunk
        while (chunk_end - start).total_seconds()/3600 <= epg_time_frame:
            epg_chunk = get_epg(id_chunk, chunk_start, chunk_end)
            chunk_start += delta_chunk
            chunk_end += delta_chunk
            if not epg_chunk:
                continue
            try:
                chunk_template = JTemplate(epg_chunk)
            except JTemplateError as e:
                Logger.log_message(f'Failed to load epg template. {e}', 'ERROR')
                continue
            map.map(chunk_template, epg_template, log_report=False)
        start_index += channels_chunk
        end_index += channels_chunk
    epg_template.dump('epg_template.json')
    epg_xml = generate_xml(epg_template)
    tree = ET.ElementTree(epg_xml)
    tree.write(epg_output, encoding='utf-8', xml_declaration=True)