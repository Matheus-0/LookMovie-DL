import json

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


# Returns substring between two substrings
def find(string, start, end):
    return string.split(start)[1].split(end)[0]


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
        s = f"Season {x['season']}"
        e = f"Episode {x['episode']}"

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

        link = f"{BASE}{info.a.get('href')}"
        title = info.a.string.strip()

        result[title] = link

    return result
