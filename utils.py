import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

API_MOVIES_BASE = 'https://false-promise.lookmovie.ag/api/v1/storage/movies/?id_movie='
API_SHOWS_BASE = 'https://false-promise.lookmovie.ag/api/v1/storage/shows/?slug='
BASE = 'https://lookmovie.ag'
MOVIES_BASE = 'https://lookmovie.ag/movies/search/?q='
MASTER_MOVIES_BASE = 'https://lookmovie.ag/manifests/movies/json/'
MASTER_SHOWS_BASE = 'https://lookmovie.ag/manifests/shows/json/'
SHOWS_BASE = 'https://lookmovie.ag/shows/search/?q='
SUBTITLES_SHOWS_BASE = 'https://lookmovie.ag/api/v1/shows/episode-subtitles/?id_episode='


# Returns JSON with expiration and access token
def access(text, movie=True):
    response = requests.get(f'{API_MOVIES_BASE if movie else API_SHOWS_BASE}{text}')

    return response.json()


# Converts TS video to MP4
def convert(filename, output):
    print('Converting to MP4...')

    subprocess.call(
        f'ffmpeg -i "{filename}" -c:a copy -c:v copy "{output}" -loglevel quiet',
        stdout=subprocess.DEVNULL,
        shell=True
    )


# Concatenates all TS segments
def concat(output):
    print('Joining segments...')

    subprocess.call(f'copy /b .\\temp\\*.ts "{output}"', stdout=subprocess.DEVNULL, shell=True)


# Downloads a segment
def dls(segment, path):
    response = requests.get(segment, stream=True)

    with open(path, 'wb') as file:
        for chunk in response.iter_content(10485760):
            if chunk:
                file.write(chunk)


# Downloads all segments
def download(segments, directory, description, workers):
    progress = tqdm(
        desc=description,
        total=len(segments),
        bar_format='{desc}: {percentage:3.0f}% |{bar}| [{elapsed} < {remaining}]'
    )  # Progress bar

    with concurrent.futures.ThreadPoolExecutor(workers) as executor:
        for segment in segments:
            filename = segment.split('/')[-1].split('.')[0]  # Get TS file name

            digits = re.match('.*?([0-9]+)$', filename).group(1)  # Get number at the end of file name
            digits = digits.zfill(5)  # Make it 5 characters long so that files get properly ordered

            path = os.path.join(directory, f'{digits}.ts')

            executor.submit(dls, segment, path).add_done_callback(lambda _: progress.update())

    progress.close()


# Deletes temporary folder
def ext():
    try:
        shutil.rmtree('temp')
    except FileNotFoundError:
        pass


# Returns all links for each segment
def extract(link):
    parsed = urlparse(link)  # Parse URL

    try:
        response = requests.get(link)  # Request to index link
    except requests.exceptions.ConnectionError:
        print('Could not connect, try again.')

        sys.exit()

    content = [link.strip() for link in response.text.splitlines()]  # Get content from response

    base = f"{parsed.scheme}://{parsed.netloc}{'/'.join(parsed.path.split('/')[:-1])}/"  # Get base URL

    return [link if parsed.scheme in link else urljoin(base, link) for link in content if not link.startswith('#')]


# Returns substring between two substrings
def find(string, start, end):
    return string.split(start)[1].split(end)[0]


# Returns all available video qualities
def qualities(link):
    try:
        response = requests.get(link)
    except requests.exceptions.ConnectionError:
        print('Could not connect, try again.')

        sys.exit()

    return {k[:-1] if k.endswith('p') else k: v for k, v in response.json().items() if not k.startswith('a')}


# Returns episode IDs data
def load(link, movie=True):
    try:
        response = requests.get(link)
    except requests.exceptions.ConnectionError:
        print('Could not connect, try again.')

        sys.exit()

    document = response.text  # Get page HTML

    soup = BeautifulSoup(document, 'html.parser')

    script = soup.find('div', id='app').find('script').string  # Get content of first script tag

    if movie:
        i = find(script, 'id_movie: ', ',')

        return {
            'ID': i
        }
    else:
        slug = find(script, 'slug: \'', '\',')  # Get slug
        episodes = find(script, 'seasons: [', ']')  # Find seasons data substring

        # Replace characters for JSON creation
        episodes = episodes.replace('\'', '"')
        episodes = episodes.replace('title:', '"title":')
        episodes = episodes.replace('id_episode:', '"id_episode":')
        episodes = episodes.replace('episode:', '"episode":')
        episodes = episodes.replace('season:', '"season":')

        episodes = '[' + ''.join(episodes.rsplit(',', 1)) + ']'  # Remove last comma and add brackets

        episodes = json.loads(episodes)  # Get JSON

        result = {
            'ID': slug
        }

        for x in episodes:
            s, e = x['season'], x['episode']

            i = x['id_episode']

            try:
                result[s][e] = i
            except KeyError:
                result[s] = {
                    e: i
                }

        return result


# Returns master link given ID, expiration and access token
def master(i, expiration, token, movie=True):
    data = f'{i}/{expiration}/{token}' if movie else f'{token}/{expiration}/{i}'

    return f'{MASTER_MOVIES_BASE if movie else MASTER_SHOWS_BASE}{data}/master.m3u8'


# Returns a dict with the links for results
def search(query, movie=True):
    try:
        response = requests.get(f'{MOVIES_BASE if movie else SHOWS_BASE}{query}')
    except requests.exceptions.ConnectionError:
        print('Could not connect, try again.')

        sys.exit()

    document = response.text  # Get page HTML

    soup = BeautifulSoup(document, 'html.parser')

    result = dict()

    # Search tags with the results
    for element in soup.find_all('div', 'movie-item-style-2 movie-item-style-1'):
        info = element.find('h6')
        year = element.find('p', 'year').string

        link = f"{BASE}{info.a.get('href')}"

        title = info.a.string.strip()
        title = re.sub(r'[<>:"/|?*\\]', ' ', title)  # Remove invalid characters for Windows
        title = ' '.join(title.split())  # Remove consecutive spaces

        result[f'{title} ({year})'] = link

    return result
