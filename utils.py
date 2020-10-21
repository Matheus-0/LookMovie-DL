import json
import subprocess
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

API_MOVIES_BASE = 'https://false-promise.lookmovie.ag/api/v1/storage/movies/?id_movie='
API_SHOWS_BASE = 'https://false-promise.lookmovie.ag/api/v1/storage/shows/?slug='
BASE = 'https://lookmovie.ag'
MOVIES_BASE = 'https://lookmovie.ag/movies/search/?q='
MASTER_BASE = 'https://lookmovie.ag/manifests/shows/json/'
SHOWS_BASE = 'https://lookmovie.ag/shows/search/?q='


# Returns JSON with expiration and access token
def access(text, movie=True):
    response = requests.get(f'{API_MOVIES_BASE if movie else API_SHOWS_BASE}{text}')

    return response.json()


# Converts TS video to MP4
def convert(filename, output):
    subprocess.Popen(
        ['ffmpeg', '-loglevel', 'quiet', '-stats', '-i', filename, '-c:a', 'copy', '-c:v', 'copy', output]
    ).wait()


# Concatenates all TS segments
def concat(txt, output):
    subprocess.Popen(
        ['ffmpeg', '-loglevel', 'quiet', '-stats', '-f', 'concat', '-safe', '0', '-i', txt, '-c', 'copy', output]
    ).wait()


# Downloads all segments
def download(segment, path):
    response = requests.get(segment, stream=True)

    with open(path, 'wb') as file:
        for chunk in response.iter_content(10485760):
            if chunk:
                file.write(chunk)


# Returns all links for each segment
def extract(link):
    parsed = urlparse(link)  # Parse URL
    response = requests.get(link)  # Request to index link

    content = [link.strip() for link in response.text.splitlines()]  # Get content from response

    base = f"{parsed.scheme}://{parsed.netloc}{'/'.join(parsed.path.split('/')[:-1])}/"  # Get base URL

    return [link if parsed.scheme in link else urljoin(base, link) for link in content if not link.startswith('#')]


# Returns substring between two substrings
def find(string, start, end):
    return string.split(start)[1].split(end)[0]


# Returns all available video qualities
def qualities(link):
    response = requests.get(link)

    return {key: value for key, value in response.json().items() if not key.startswith('a')}


# Returns episode IDs data
def load(link):
    response = requests.get(link)
    document = response.text  # Get page HTML

    soup = BeautifulSoup(document, 'html.parser')

    script = soup.find('div', id='app').find('script').string  # Get content of first script tag

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

    return f'{MASTER_BASE}{data}/master.m3u8'


# Returns a dict with the links for results
def search(query, movie=True):
    response = requests.get(f'{MOVIES_BASE if movie else SHOWS_BASE}{query}')

    document = response.text  # Get page HTML

    soup = BeautifulSoup(document, 'html.parser')

    result = dict()

    # Search tags with the results
    for element in soup.find_all('div', 'movie-item-style-2 movie-item-style-1'):
        info = element.find('h6')
        year = element.find('p', 'year').string

        link = f"{BASE}{info.a.get('href')}"
        title = info.a.string.strip()

        result[f'{title} ({year})'] = link

    return result
