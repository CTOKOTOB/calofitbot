# calofitbot

Бот для учёта калорий. Храню данные, показываю статистику и подсказываю калорийность продуктов.

.bash_aliases:
alias stopbot='sudo systemctl stop calofitbot.service'
alias startbot='sudo systemctl start calofitbot.service'
alias statusbot='sudo systemctl status calofitbot.service'
alias logbot="journalctl -u calofitbot.service -f"

alias psql='sudo -u postgres psql -d calorie_tracker'
alias hba='sudo vi /etc/postgresql/16/main/pg_hba.conf'

alias activate='cd ~/projects/calofitbot && source venv/bin/activate'


commands:
start - Знакомство\Обновить данные
report - Отчет 
del - Удалить последнюю запись
graph - График
add_cache - Запомнить блюдо
edit_cache - Редактировать список
del_all - Удалить все мои данные



