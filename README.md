# calofitbot

cat ~/.bash_aliases
alias stopbot='sudo systemctl stop calofitbot.service'
alias startbot='sudo systemctl start calofitbot.service'
alias statusbot='sudo systemctl status calofitbot.service'
alias logbot="journalctl -u calofitbot.service -f"

alias psql='psql -U calorie_bot -d calorie_tracker -h localhost'
alias hba='sudo vi /etc/postgresql/17/main/pg_hba.conf'

alias activate='cd ~/calofitbot && source venv/bin/activate'


commands:
report - Отчет
graph - График
from_cache - Добавить продукт из списка 
add_cache - Запомнить блюдо 
edit_cache - Редактировать список 
start - Знакомство\Обновить данные 
del - Удалить последнюю запись 
del_all - Удалить все мои данные


crontab:
17 */4 * * * sh  /usr/bin/bash ~/calofitbot/restart_calofitbot.sh

/etc/sudoers.d/calobot:
calobot ALL=NOPASSWD: /usr/bin/systemctl restart calofitbot.service
calobot ALL=NOPASSWD: /usr/bin/systemctl start calofitbot.service
calobot ALL=NOPASSWD: /usr/bin/systemctl stop calofitbot.service


