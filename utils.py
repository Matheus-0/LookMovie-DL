import requests
from bs4 import BeautifulSoup

BASE = 'https://lookmovie.ag'
MOVIES_BASE = 'https://lookmovie.ag/movies/search/?q='
SHOWS_BASE = 'https://lookmovie.ag/shows/search/?q='


# Returns a dict with the links for results found
def search(query, movie=True):
    response = requests.get((MOVIES_BASE if movie else SHOWS_BASE) + query)

    document = response.text  # Get page HTML

    soup = BeautifulSoup(document, 'html.parser')

    result = dict()

    # Search tags with the results
    for element in soup.find_all('div', 'movie-item-style-2 movie-item-style-1'):
        info = element.find('h6')

        link = BASE + info.a.get('href')
        title = info.a.string.strip()

        result[title] = link

    return result
