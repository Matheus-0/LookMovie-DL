import atexit
import os
import shutil

import inquirer
import requests
from inquirer.themes import load_theme_from_dict

from utils import access, download, ext, extract, qualities, load, master, process, search, subs

MAX_WORKERS = 30  # Maximum number of workers for thread pool executor

atexit.register(ext)  # Function to be executed when program exits

# Theme for inquirer
theme = load_theme_from_dict({
    'Checkbox': {
        'selected_color': 'cyan',
        'selected_icon': 'x',
        'selection_color': 'green'
    },
    'Question': {
        'mark_color': 'green'
    },
    'List': {
        'selection_color': 'green'
    }
})

try:
    answer = inquirer.prompt([
        inquirer.List('type', 'Look for movies or TV shows?', ['Movies', 'TV shows'], carousel=True)
    ], theme=theme, raise_keyboard_interrupt=True)['type']

    query = input('Search: \033[1m')

    print('\033[0m')

    movie = answer == 'Movies'

    results = search(query, movie)  # Search and get results

    if results:
        title = inquirer.prompt([
            inquirer.List('title', 'Select movie or TV show', results.keys(), carousel=True)
        ], theme=theme, raise_keyboard_interrupt=True)['title']

        data = load(results[title], movie)  # Get TV show or movie data
        acc = access(data['ID'], movie)  # Get access data

        expiration, token = acc['data']['expires'], acc['data']['accessToken']

        if movie:
            mst = master(data['ID'], expiration, token, True)
            links = qualities(mst)

            directory = os.path.join(os.getcwd(), title)
            temporary = os.path.join(os.getcwd(), 'temp')

            os.makedirs(directory, exist_ok=True)

            proceed = True

            if os.path.isfile(os.path.join(os.getcwd(), directory, f'{title}.mp4')):
                again = inquirer.prompt([
                    inquirer.List('again', f'{title} has already been downloaded, download again?', ['No', 'Yes'])
                ], theme=theme, raise_keyboard_interrupt=True)['again']

                if again == 'No':
                    proceed = False

            if proceed:
                # Try to create temporary folder, if it exists, delete it and create another
                try:
                    os.makedirs(temporary)
                except FileExistsError:
                    shutil.rmtree(temporary)
                    os.makedirs(temporary)

                quality = inquirer.prompt([
                    inquirer.List('quality', 'Select quality', [i + 'p' for i in links.keys()], carousel=True)
                ], theme=theme, raise_keyboard_interrupt=True)['quality'][:-1]

                sbs = subs(results[title], True)  # Get subtitles links
                segments = extract(links[quality])  # Get segments links

                download(segments, sbs, title, MAX_WORKERS)  # Download all segments and subtitles
                process(directory, title, sbs)  # Join segments, convert to MP4 and add subtitles

                shutil.rmtree(temporary, True)
        else:
            season = inquirer.prompt([
                inquirer.List(
                    'season', 'Select season', [f'Season {s}' for s in data.keys() if s != 'ID'], carousel=True
                )
            ], theme=theme, raise_keyboard_interrupt=True)['season'].split()[-1]

            episodes = [x.split()[-1] for x in inquirer.prompt([
                inquirer.Checkbox('episodes', 'Select episodes', [f'Episode {e}' for e in data[season].keys()])
            ], theme=theme, raise_keyboard_interrupt=True)['episodes']]

            if episodes:
                episodes = list(map(str, sorted(map(int, episodes))))  # Episodes might come in wrong order, so we sort

                masters = {e: master(data[season][e], expiration, token, False) for e in episodes}  # Get master links
                links = {e: qualities(link) for e, link in masters.items()}  # Get links for each quality

                directory = os.path.join(os.getcwd(), title, f"Season {season}")
                temporary = os.path.join(os.getcwd(), 'temp')

                os.makedirs(directory, exist_ok=True)

                # Get qualities all episodes have in common
                labels = ['360', '480', '720', '1080']

                for i in labels[:]:
                    for j in links.values():
                        if i not in j.keys():
                            labels.remove(i)

                            break

                if labels:
                    quality = inquirer.prompt([
                        inquirer.List('quality', 'Select quality', [i + 'p' for i in labels], carousel=True)
                    ], theme=theme, raise_keyboard_interrupt=True)['quality'][:-1]
                else:
                    quality = str()

                for episode, values in links.items():
                    if os.path.isfile(os.path.join(os.getcwd(), directory, f'Episode {episode}.mp4')):
                        again = inquirer.prompt([
                            inquirer.List(
                                'again', f'Episode {episode} has already been downloaded, download again?',
                                ['No', 'Yes']
                            )
                        ], theme=theme, raise_keyboard_interrupt=True)['again']

                        if again == 'No':
                            continue

                    os.makedirs(temporary, exist_ok=True)

                    if quality:
                        link = values[quality]
                    else:
                        link = values[str(max([int(i) for i in values.keys()]))]  # Choose best quality if not available

                    sbs = subs(data[season][episode], False)  # Get subtitles links
                    segments = extract(link)  # Get segments links

                    download(segments, sbs, f'Episode {episode}', MAX_WORKERS)  # Download all segments and subtitles
                    process(directory, f'Episode {episode}', sbs)  # Join segments, convert to MP4 and add subtitles

                    shutil.rmtree(temporary, True)
            else:
                print('No episodes selected.')
    else:
        print('No results.')
except KeyboardInterrupt:
    print('Cancelled.')
except requests.exceptions.ConnectionError:
    print('Could not connect, try again.')
finally:
    input('\nPress Enter to exit.\n')
