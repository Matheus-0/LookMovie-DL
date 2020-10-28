import concurrent.futures
import json
import os
import platform
import re
import shutil
import subprocess
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

API_MOVIES_BASE = 'https://false-promise.lookmovie.ag/api/v1/storage/movies/?id_movie='
API_SHOWS_BASE = 'https://false-promise.lookmovie.ag/api/v1/storage/shows/?slug='
BASE = 'https://lookmovie.ag'
MOVIES_BASE = 'https://lookmovie.ag/movies/search/?q='
MASTER_MOVIES_BASE = 'https://lookmovie.ag/manifests/movies/json/'
MASTER_SHOWS_BASE = 'https://lookmovie.ag/manifests/shows/json/'
SHOWS_BASE = 'https://lookmovie.ag/shows/search/?q='
SUBTITLES_SHOWS_BASE = 'https://lookmovie.ag/api/v1/shows/episode-subtitles/?id_episode='


codes = {
    'English': 'eng',
    'French': 'fre',
    'German': 'ger',
    'Italian': 'ita',
    'Portuguese': 'por',
    'Portuguese (BR)': 'por',
    'Spanish': 'spa'
}

session = requests.Session()

retries = Retry(5, status_forcelist=[500, 502, 503, 504], backoff_factor=0.1)

session.mount('http://', HTTPAdapter(max_retries=retries))


# Returns JSON with expiration and access token
def access(text, movie=True):
    response = session.get(f'{API_MOVIES_BASE if movie else API_SHOWS_BASE}{text}')

    return response.json()


# Converts TS video
def convert(filename, output):
    return subprocess.call(
        f'ffmpeg -v -8 -y -i "{filename}" -map 0 -c copy "{output}"',
        stdout=subprocess.DEVNULL,
        shell=True
    )


# Concatenates all TS segments
def concat(output):
    if platform.system() == 'Windows':
        return subprocess.call(f'copy /b .\\temp\\*.ts "{output}"', stdout=subprocess.DEVNULL, shell=True)
    else:
        return subprocess.call(f'cat ./temp/*.ts > "{output}"', stdout=subprocess.DEVNULL, shell=True)


# Downloads a file
def dlf(link, path, stream):
    response = session.get(link, stream=stream)

    with open(path, 'wb') as file:
        if stream:
            for chunk in response.iter_content(10485760):
                if chunk:
                    file.write(chunk)
        else:
            file.write(response.content)


# Downloads all segments
def download(segments, subtitles, description, workers):
    progress = tqdm(
        desc=description,
        total=len(segments),
        bar_format='{desc}: {percentage:3.0f}% |{bar}| [{elapsed} < {remaining}]',
        colour='green'
    )  # Progress bar

    with concurrent.futures.ThreadPoolExecutor(workers) as executor:
        for sub in subtitles.values():
            filename = sub.split('/')[-1]
            path = os.path.join(os.getcwd(), 'temp', filename)

            executor.submit(dlf, sub, path, False)

        for segment in segments:
            filename = segment.split('/')[-1].split('.')[0]  # Get TS file name

            digits = re.match('.*?([0-9]+)$', filename).group(1)  # Get number at the end of file name
            digits = digits.zfill(5)  # Make it 5 characters long so that files get properly ordered

            path = os.path.join(os.getcwd(), 'temp', f'{digits}.ts')

            executor.submit(dlf, segment, path, True).add_done_callback(lambda _: progress.update())

    progress.close()


# Deletes temporary folder
def ext():
    shutil.rmtree('temp', True)


# Returns all links for each segment
def extract(link):
    parsed = urlparse(link)  # Parse URL
    response = session.get(link)  # Request to index link

    content = [link.strip() for link in response.text.splitlines()]  # Get content from response

    base = f"{parsed.scheme}://{parsed.netloc}{'/'.join(parsed.path.split('/')[:-1])}/"  # Get base URL

    return [link if parsed.scheme in link else urljoin(base, link) for link in content if not link.startswith('#')]


# Returns substring between two substrings
def find(string, start, end):
    return string.split(start)[1].split(end)[0]


# Returns all occurrences of substrings between two substrings
def findall(string, start, end):
    return re.findall(re.escape(start) + r'(.*?)' + re.escape(end), string)


# Returns all available video qualities
def qualities(link):
    response = session.get(link)

    data = {k[:-1] if k.endswith('p') else k: v for k, v in response.json().items() if not k.startswith('a')}

    # Try to obtain 1080p URL
    try:
        # Check if there's a 1080p URL or if the existing 1080p URL is valid
        if '1080' not in data.keys() or link.split('/')[-3] not in data['1080']:
            delete = False

            for key, value in data.items():
                if key != '1080':
                    # Guess 1080p URL
                    valid = value.replace(key + 'p', '1080p')

                    # Check if such 1080p URL exists
                    if session.get(valid).ok:
                        data['1080'] = valid
                    else:
                        delete = True

                    break

            if delete:
                del data['1080']
    except KeyError:
        pass

    return data


# Returns episode IDs data
def load(link, movie=True):
    response = session.get(link)

    soup = BeautifulSoup(response.text, 'html.parser')

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


# Does the process of joining segments, converting and adding subtitles
def process(directory, title, subtitles):
    final = os.path.join(directory, f'{title}.mp4')
    m = os.path.join(directory, f'temporary.mp4')
    t = os.path.join(directory, f'temporary.ts')

    print('\nJoining segments...')

    concat(t)

    print('Converting to MP4...')

    if subtitles:
        convert(t, m)

        print('Adding subtitles...')

        if subtitle(m, final, subtitles) == 0:
            try:
                os.unlink(m)  # If adding subtitles was successful, delete temporary file
            except OSError:
                print(f'Could not delete temporary video file: {m}')

                pass
        else:
            # Otherwise, delete incomplete final file and keep the temporary one without subtitles
            try:
                os.unlink(final)
            except OSError:
                print(f'Could not delete incomplete output file: {final}')

                pass
            else:
                try:
                    os.rename(m, final)
                except OSError:
                    print(f'Could not rename file: {m}')

                    pass

            print('Error, could not add subtitles.')
    else:
        convert(t, final)

    os.unlink(t)

    print('Finished!\n')


# Returns a dict with the links for results
def search(query, movie=True):
    response = session.get(f'{MOVIES_BASE if movie else SHOWS_BASE}{query}')

    soup = BeautifulSoup(response.text, 'html.parser')

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


# Gets subtitles
def subs(i, movie):
    if movie:
        response = session.get(i)

        soup = BeautifulSoup(response.text, 'html.parser')

        script = soup.find('div', id='app').find('script').string

        labels = findall(script, '"label": "', '"')
        links = [BASE + x for x in findall(script, 'host + "', '"')]

        languages = {labels[i]: links[i] for i in range(len(labels)) if labels[i] in codes.keys()}

        return languages
    else:
        response = session.get(f'{SUBTITLES_SHOWS_BASE}{i}')

        languages = dict()

        for s in response.json():
            if s['languageName'] in codes.keys():
                languages[s['languageName']] = f"{BASE}/{s['shard']}/{s['storagePath']}{s['isoCode']}.vtt"

        return languages


# Puts subtitles on video
def subtitle(i, output, subtitles):
    inputs = f'-i "{i}"'  # Store the inputs
    maps = '-map 0:v -map 0:a'  # Store the maps
    metadata = str()  # Store subtitles metadata

    count = 1

    for lang, url in subtitles.items():
        path = os.path.join(os.getcwd(), 'temp', url.split('/')[-1])  # Get file name

        # Get language ISO-639 code, defaults to three first letters
        language = codes.get(lang, lang.split('.')[0][:3].lower())

        inputs += f' -i "{path}"'
        maps += f' -map {count}'
        metadata += f"-metadata:s:s:{count - 1} language={language} "

        count += 1

    return subprocess.call(
        f'ffmpeg -xerror -v -8 -y {inputs} {maps} -c:v copy -c:a copy -c:s mov_text {metadata[:-1]} "{output}"',
        stdout=subprocess.DEVNULL
    )
