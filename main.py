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

    movie = answer == 'Movies'

    results = None

    while not results:
        query = input('Search: \033[1m')

        print('\033[0m')

        results = search(query, movie)  # Search and get results

        if not results:
            print('No results, try again.\n')

    title = inquirer.prompt([
        inquirer.List('title', 'Select movie or TV show', results.keys(), carousel=True)
    ], theme=theme, raise_keyboard_interrupt=True)['title']

    print('Loading data...\n')

    data = load(results[title], movie)  # Get TV show or movie data
    acc = access(data['ID'], movie)  # Get access data

    expiration, token = acc['data']['expires'], acc['data']['accessToken']

    if movie:
        print('Looking for video qualities...\n')

        mst = master(data['ID'], expiration, token, True)
        links = qualities(mst)

        directory = os.path.join(os.getcwd(), title)
        temporary = os.path.join(os.getcwd(), 'temp')

        quality = inquirer.prompt([
            inquirer.List('quality', 'Select quality', [i + 'p' for i in links.keys()], carousel=True)
        ], theme=theme, raise_keyboard_interrupt=True)['quality'][:-1]

        print('Looking for subtitles...\n')

        sbs = subs(results[title], True)  # Get subtitles links

        if sbs:
            print(f'Available subtitles: {", ".join(sbs.keys())}.\n')
        else:
            print(f'No subtitles available.\n')

        proceed = inquirer.prompt([
            inquirer.List('proceed', 'Do you want to proceed with the download?', ['No', 'Yes'], carousel=True)
        ], theme=theme, raise_keyboard_interrupt=True)['proceed'] == 'Yes'

        if os.path.isfile(os.path.join(os.getcwd(), directory, f'{title}.mp4')):
            proceed = inquirer.prompt([
                inquirer.List(
                    'proceed', f'{title} has already been downloaded, download again?', ['No', 'Yes'], carousel=True
                )
            ], theme=theme, raise_keyboard_interrupt=True)['proceed'] == 'Yes'

        if proceed:
            os.makedirs(directory, exist_ok=True)

            # Try to create temporary folder, if it exists, delete it and create another
            try:
                os.makedirs(temporary)
            except FileExistsError:
                shutil.rmtree(temporary)
                os.makedirs(temporary)

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

        episodes = None

        while not episodes:
            episodes = [x.split()[-1] for x in inquirer.prompt([
                inquirer.Checkbox(
                    'episodes', 'Select episodes (use Space to select)', [f'Episode {e}' for e in data[season].keys()]
                )
            ], theme=theme, raise_keyboard_interrupt=True)['episodes']]

            if not episodes:
                print('No episodes selected, select at least one.\n')

        episodes = list(map(str, sorted(map(int, episodes))))  # Episodes might come in wrong order, so we sort

        print('Looking for video qualities...\n')

        masters = {e: master(data[season][e], expiration, token, False) for e in episodes}  # Get master links
        links = {e: qualities(link) for e, link in masters.items()}  # Get links for each quality

        directory = os.path.join(os.getcwd(), title, f"Season {season}")
        temporary = os.path.join(os.getcwd(), 'temp')

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
            print('The episodes don\'t have any qualities in common, the best quality will be chosen for each.\n')

            quality = str()

        print('Looking for subtitles...\n')

        sbs = {e: subs(data[season][e], False) for e in episodes}  # Get links for subtitles

        for episode in sbs.keys():
            if sbs[episode]:
                print(f'Episode {episode}: {", ".join(sbs[episode].keys())}.')
            else:
                print(f'Episode {episode}: no subtitles available.')

        print()

        proceed = inquirer.prompt([
            inquirer.List('proceed', 'Do you want to proceed with the download?', ['No', 'Yes'], carousel=True)
        ], theme=theme, raise_keyboard_interrupt=True)['proceed'] == 'Yes'

        if proceed:
            os.makedirs(directory, exist_ok=True)

            # Try to create temporary folder, if it exists, delete it and create another
            try:
                os.makedirs(temporary)
            except FileExistsError:
                shutil.rmtree(temporary)
                os.makedirs(temporary)

            for episode, values in links.items():
                if os.path.isfile(os.path.join(os.getcwd(), directory, f'Episode {episode}.mp4')):
                    proceed = inquirer.prompt([
                        inquirer.List(
                            'proceed', f'Episode {episode} has already been downloaded, download again?',
                            ['No', 'Yes']
                        )
                    ], theme=theme, raise_keyboard_interrupt=True)['proceed'] == 'Yes'

                    if not proceed:
                        continue

                os.makedirs(temporary, exist_ok=True)

                if quality:
                    link = values[quality]
                else:
                    link = values[str(max([int(i) for i in values.keys()]))]  # Choose best quality if not available

                segments = extract(link)  # Get segments links

                download(segments, sbs[episode], f'Episode {episode}', MAX_WORKERS)  # Download segments and subs
                process(directory, f'Episode {episode}', sbs[episode])  # Join segments, convert and add subtitles

                shutil.rmtree(temporary, True)
except KeyboardInterrupt:
    print('\033[0mCancelled.\n')
except requests.exceptions.ConnectionError:
    print('Connection error.\n')
finally:
    input('Press Enter to exit.\n')
