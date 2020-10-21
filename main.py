import concurrent.futures
import os
import shutil

import inquirer
from tqdm import tqdm

from utils import *

MAX_WORKERS = 15  # Maximum number of workers for thread pool executor

answers = inquirer.prompt([
    inquirer.List('type', 'Look for movies or TV shows?', ['Movies', 'TV shows'], carousel=True),
    inquirer.Text('query', 'Search')
])

movie = answers['type'] == 'Movies'

results = search(answers['query'], movie)  # Search and get results

if results:
    title = inquirer.prompt([
        inquirer.List('title', 'Select movie or TV show', results.keys(), carousel=True)
    ])['title']

    if movie:
        print('To-do.')
    else:
        data = load(results[title])  # Get TV show data
        acc = access(data['ID'], False)  # Get access data

        expiration, token = acc['data']['expires'], acc['data']['accessToken']

        season = inquirer.prompt([
            inquirer.List('season', 'Select season', [s for s in data.keys() if s != 'ID'], carousel=True)
        ])['season']

        episodes = inquirer.prompt([
            inquirer.Checkbox('episodes', 'Select episodes', data[season].keys())
        ])['episodes']

        if episodes:
            masters = {e: master(data[season][e], expiration, token, False) for e in episodes}  # Get master links
            links = {e: qualities(link) for e, link in masters.items()}  # Get index links for each quality

            directory = os.path.join(os.getcwd(), title, f"Season {season}")
            temporary = os.path.join(os.getcwd(), 'temp')

            os.makedirs(directory, exist_ok=True)

            quality = inquirer.prompt([
                inquirer.List('quality', 'Select quality', ['360p', '480p', '720p', '1080p'], carousel=True)
            ])['quality']

            for episode, values in links.items():
                # Paths for MP4 and TS videos
                MP4 = os.path.join(directory, f'Episode {episode}.mp4')
                TS = os.path.join(directory, f"Episode {episode}.ts")

                try:
                    link = values[quality[:-1]]  # Try to access quality
                except KeyError:
                    link = values[str(max([int(i) for i in values.keys()]))]  # Choose best quality if not available

                segments = extract(link)  # Get all links for each segment

                os.makedirs(temporary, exist_ok=True)

                progress = tqdm(total=len(segments))  # Progress bar

                with concurrent.futures.ThreadPoolExecutor(MAX_WORKERS) as executor:
                    with open('segments.txt', 'w') as file:
                        for segment in segments:
                            path = os.path.join(temporary, segment.split('/')[-1])

                            executor.submit(download, segment, path).add_done_callback(lambda _: progress.update())

                            file.write(f"file '{path}'\n")  # Write file paths on text file for later use

                progress.close()

                concat('segments.txt', TS)  # Join all segments

                convert(TS, MP4)  # Convert from TS to MP4

                os.unlink('segments.txt')  # Remove text file
                os.unlink(TS)  # Remove TS video

                shutil.rmtree(temporary)  # Remove temporary folder and all its files
        else:
            print('No episodes selected.')
else:
    print('No results.')
