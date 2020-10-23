import atexit
import os
import shutil

import inquirer

from utils import access, concat, convert, download, ext, extract, qualities, load, master, search

MAX_WORKERS = 30  # Maximum number of workers for thread pool executor

atexit.register(ext)  # Function to be executed when program exits

try:
    answer = inquirer.prompt([
        inquirer.List('type', 'Look for movies or TV shows?', ['Movies', 'TV shows'], carousel=True)
    ], raise_keyboard_interrupt=True)['type']

    query = input('Search: ')

    movie = answer == 'Movies'

    results = search(query, movie)  # Search and get results

    if results:
        title = inquirer.prompt([
            inquirer.List('title', 'Select movie or TV show', results.keys(), carousel=True)
        ], raise_keyboard_interrupt=True)['title']

        data = load(results[title], movie)  # Get TV show or movie data
        acc = access(data['ID'], movie)  # Get access data

        expiration, token = acc['data']['expires'], acc['data']['accessToken']

        if movie:
            mst = master(data['ID'], expiration, token, True)
            links = qualities(mst)

            directory = os.path.join(os.getcwd(), title)
            temporary = os.path.join(os.getcwd(), 'temp')

            os.makedirs(directory, exist_ok=True)

            # Try to create temporary folder, if it exists, delete it and create another
            try:
                os.makedirs(temporary)
            except FileExistsError:
                shutil.rmtree(temporary)
                os.makedirs(temporary)

            quality = inquirer.prompt([
                inquirer.List('quality', 'Select quality', [i + 'p' for i in links.keys()], carousel=True)
            ], raise_keyboard_interrupt=True)['quality'][:-1]

            MP4 = os.path.join(directory, f'{title}.mp4')
            TS = os.path.join(directory, f"{title}.ts")

            segments = extract(links[quality])  # Get segments links

            download(segments, temporary, title, MAX_WORKERS)

            concat(TS)  # Join segments
            convert(TS, MP4)  # Convert TS to MP4

            os.unlink(TS)  # Remove TS video

            shutil.rmtree(temporary)
        else:
            season = inquirer.prompt([
                inquirer.List(
                    'season', 'Select season', [f'Season {s}' for s in data.keys() if s != 'ID'], carousel=True
                )
            ], raise_keyboard_interrupt=True)['season'].split()[-1]

            episodes = [x.split()[-1] for x in inquirer.prompt([
                inquirer.Checkbox('episodes', 'Select episodes', [f'Episode {e}' for e in data[season].keys()])
            ], raise_keyboard_interrupt=True)['episodes']]

            if episodes:
                masters = {e: master(data[season][e], expiration, token, False) for e in episodes}  # Get master links
                links = {e: qualities(link) for e, link in masters.items()}  # Get index links for each quality

                directory = os.path.join(os.getcwd(), title, f"Season {season}")
                temporary = os.path.join(os.getcwd(), 'temp')

                os.makedirs(directory, exist_ok=True)

                labels = ['360', '480', '720', '1080']

                for i in labels[:]:
                    for j in links.values():
                        if i not in j.keys():
                            labels.remove(i)

                            break

                if labels:
                    quality = inquirer.prompt([
                        inquirer.List('quality', 'Select quality', [i + 'p' for i in labels], carousel=True)
                    ], raise_keyboard_interrupt=True)['quality'][:-1]
                else:
                    quality = str()

                for episode, values in links.items():
                    # Paths for MP4 and TS videos
                    MP4 = os.path.join(directory, f'Episode {episode}.mp4')
                    TS = os.path.join(directory, f"Episode {episode}.ts")

                    os.makedirs(temporary, exist_ok=True)

                    if quality:
                        link = values[quality]
                    else:
                        link = values[str(max([int(i) for i in values.keys()]))]  # Choose best quality if not available

                    segments = extract(link)  # Get segments links

                    download(segments, temporary, f'Episode {episode}', MAX_WORKERS)

                    concat(TS)  # Join segments
                    convert(TS, MP4)  # Convert TS to MP4

                    os.unlink(TS)  # Remove TS video

                    shutil.rmtree(temporary)  # Remove temporary folder and all its files
            else:
                print('No episodes selected.')
    else:
        print('No results.')
except KeyboardInterrupt:
    print('Cancelled.')
