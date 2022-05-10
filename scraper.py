import os
import json
import time
import logging
import ssl
import click
import requests
from operator import itemgetter
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager

BASE_URL = 'https://2022electionresults.comelec.gov.ph/data'
BASE_DIR = 'data'
DOWNLOAD_DELAY = 0.5

urljoin = lambda *args: '/'.join(args)

def load_or_download(sess, file_path, url):
    """Read file_path if it exists, download from url if it doesn't"""
    logging.debug(f'In load_or_download: {file_path}, {url}')
    if os.path.exists(file_path):
        logging.info(f'{file_path} exists, loading...')
        with open(file_path) as f:
            data = json.load(f)
    else:
        try:
            logging.info(f"{file_path} doesn't exists, "
                         f"downloading from {url}...")
            data = sess.get(url).json()
            time.sleep(DOWNLOAD_DELAY)
        except json.JSONDecodeError:
            logging.info(f"{file_path} not available.")
            raise ValueError('Results not available.')
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        print(os.path.dirname(file_path))
        with open(file_path, 'w') as f:
            json.dump(data, f)
    return data

region_dict = {'REGION I': '44022',
 'REGION II': '44023',
 'REGION III': '44024',
 'REGION V': '44025',
 'REGION VI': '44026',
 'REGION VII': '44027',
 'REGION VIII': '44028',
 'REGION IX': '44029',
 'REGION X': '44030',
 'REGION XI': '44031',
 'REGION XII': '44032',
 'REGION XIII': '44033',
 'REGION IV-A': '44034',
 'REGION IV-B': '44035',
 'BARMM': '44036',
 'CORDILLERA ADMINISTRATIVE REGION': '44037',
 'NATIONAL CAPITAL REGION': '44038',
 'OAV': '44039'}

def download_data(sess, node_dir, node_url, region):
    """Recursively download data, skipping already downloaded files
    
    Parameters
    ----------
    sess : requests.Session
        requests session to use
    node_dir : str
        the directory path of this node
    node_url : str
        url of this node as given by the srs field of the parent
    """
    logging.info(f'In download_data: {node_dir}, {node_url}')
    # check if info file of this node exists; download from node_url if not
    info_path = os.path.join(BASE_DIR, 'results', node_dir, 'info.json')
    info_url = urljoin(BASE_URL, 'regions', node_url)
    node_info = load_or_download(sess, info_path, info_url)

    # brute force way to filter scraped data by Region
    if node_info['can'] == 'Country' and region:
        for reg, rc in region_dict.items():
            if reg!=region:
                node_info['srs'].pop(rc)

    # download data of all children
    for child in node_info['srs'].values():
        child_dir = os.path.join(node_dir,
                                 child['rn'].replace('/', '_'))
        download_data(sess, child_dir, child['url']+'.json', '')

    if node_info['can'] == 'Barangay': # download ER if barangay
        for precinct in node_info['pps']:
            # download results of this precint if it doesn't exist
            precinct_path = os.path.join(BASE_DIR, 'results', node_dir,
                                         precinct['ppcc']+'.json')
            assert len(precinct['vbs']) == 1
            precinct_url = urljoin(BASE_URL, 'results', 
                                   precinct['vbs'][0]['url']+'.json')
            try:
                precinct_results = load_or_download(sess, precinct_path, 
                                                    precinct_url)
            except ValueError: # no ER yet
                continue

            # collect all unique contests then download if it doesn't exist
            contests = set(map(itemgetter('cc'), precinct_results['rs']))
            for contest in contests:
                contest_path = os.path.join(BASE_DIR, 'contests', 
                                            f'{contest}.json')
                contest_url = urljoin(BASE_URL, 'contests', 
                                      f'{contest}.json')
                load_or_download(sess, contest_path, contest_url)

    else: # download COC
        # there should be at most 1 result for a node
        assert len(node_info['pps']) < 2

        for coc in node_info['pps']:
            # download COC if it doesn't exist
            coc_path = os.path.join(BASE_DIR, 'results', node_dir, 'coc.json')
            assert len(coc['vbs']) == 1
            coc_url = urljoin(BASE_URL, 'results', coc['vbs'][0]['url']+'.json')
            try:
                load_or_download(sess, coc_path, coc_url)
            except ValueError: # no COC yet
                continue

@click.command()
@click.option('-b', '--base-dir', default='data',
              help='directory from which all downloaded data will be stored')
@click.option('-d', '--download-delay', type=click.FLOAT, default=0.5,
              help='minimum delay between successive downloads')
@click.option('-l', '--log-level',
              help='log output level',
              type=click.Choice(['CRITICAL', 'ERROR', 'WARNING', 
                                 'INFO', 'DEBUG']),
              default='INFO')
@click.option('-r', '--region', default='')
def main(base_dir, download_delay, log_level, region):
    BASE_DIR = 'data'
    logging.basicConfig(level=log_level)
    sess = requests.Session()
    sess.headers = {'User-Agent': 
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/101.0.4951.54 Safari/537.36'}
    download_data(sess, '', 'root.json', region)

if __name__ == "__main__":
    main()
