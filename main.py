import inquirer

from utils import search

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

print(result)
