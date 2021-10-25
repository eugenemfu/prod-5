# prod-5

## Функция вознаграждения

Возьмем функцию из бейзлайна (доля новых клеток из исследованных) и модифицируем ее.

Во-первых умножим награду на (1 + total_explored * 0.02), чтобы мотивировать агента лучше ииследовать среду на поздних стадиях.

Во-вторых, агент часто крутится на одном месте, поэтому будем брать штраф за прохождение по старым клеткам (-1) и за остановки (-5).

## Модификация среды

В классе ``ModifiedDungeon`` в файле ``ppo_example.py`` удалена траектория и модифицирована награда.

## Логирование

Использовался wandb: https://wandb.ai/eugene_mfu/prod-5

## Запуск

`git clone https://github.com/g-e0s/mapgen.git`

`pip install -r requirements.txt`

`python ppo_example.py`

## Дальнейшие действия

Подвигать гиперпараметры лосса и вознаграждения, сравнить графики, понять куда двигаться дальше.

