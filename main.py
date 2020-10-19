import inquirer

from utils import access, load, master, search

questions = [
    inquirer.List(
        'type',
        'Do you want to look for movies or TV shows?',
        ['Movies', 'TV shows'],
        carousel=True
    ),
    inquirer.Text(
        'query',
        'Search'
    )
]

answer = inquirer.prompt(questions)

movie = answer['type'] == 'Movies'

result = search(answer['query'], movie)

if result:
    titles = [
        inquirer.List(
            'title',
            'Which movie or TV show do you want to download?',
            result.keys(),
            carousel=True
        )
    ]

    title = inquirer.prompt(titles)

    if movie:
        print('To-do.')
    else:
        data = load(result[title['title']])
        auth = access(data['ID'], False)

        expiration, token = auth['data']['expires'], auth['data']['accessToken']

        seasons = [
            inquirer.List(
                'season',
                'Which season do you want?',
                [x for x in data.keys() if x != 'ID'],
                carousel=True
            )
        ]

        season = inquirer.prompt(seasons)

        episodes = [
            inquirer.Checkbox(
                'episodes',
                'Which episodes do you want to download?',
                data[season['season']].keys(),
            )
        ]

        answers = inquirer.prompt(episodes)

        if answers:
            masters = dict()

            for episode in answers['episodes']:
                ID = data[season['season']][episode]

                masters[episode] = master(ID, expiration, token, False)

            print(masters)
        else:
            print('No episodes selected.')
else:
    print('No results.')
