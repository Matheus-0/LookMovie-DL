import inquirer

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
