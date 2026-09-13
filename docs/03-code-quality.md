# Контроль якості коду та pre-commit хуки

Мета цього налаштування — не дати технічному боргу з'явитися до того, як написана
основна бізнес-логіка. Перевірки виконуються локально й **блокують коміт**, тому
непридатний код фізично не потрапляє в історію репозиторію.

## 1. Інструменти

| Інструмент | Роль | Конфігурація |
| --- | --- | --- |
| `ruff` | статичний аналіз: синтаксис, невикористані імпорти та змінні, порядок імпортів, застарілі конструкції | `[tool.ruff]` у `pyproject.toml` |
| `black` | єдине форматування коду, довжина рядка 100 | `[tool.black]` у `pyproject.toml` |
| `pre-commit` | запуск усіх перевірок на git-хуку `pre-commit` | `.pre-commit-config.yaml` |
| `pytest` | юніт-тести доменних правил і каркаса API | `[tool.pytest.ini_options]` |

Набір правил `ruff`: `E`, `F`, `W` (помилки та стиль), `I` (порядок імпортів),
`B` (типові дефекти), `UP` (сучасний синтаксис Python), `C4` (спрощення колекцій).
Перевірка довжини рядка `E501` відключена, бо за неї відповідає `black` —
інакше два інструменти конфліктували б між собою.

Версії хуків у `.pre-commit-config.yaml` закріплені (`rev`) під ті самі версії, що
встановлені в локальному оточенні. Без цього перевірка в хуку і перевірка з
командного рядка могли б давати різні результати.

## 2. Склад хуків

```
check-ast                 файл є коректним Python (парситься в AST)
check-added-large-files   у репозиторій не потрапляють важкі файли
check-merge-conflict      немає незакритих маркерів конфлікту
check-toml / check-yaml   конфігурації валідні
end-of-file-fixer         файл завершується переводом рядка
trailing-whitespace       немає пробілів у кінці рядків
detect-private-key        у коміт не потрапляє приватний ключ
ruff-check --fix          статичний аналіз із автовиправленням
black                     форматування
```

Встановлення хуків у локальний репозиторій:

```powershell
pre-commit install
# pre-commit installed at .git\hooks\pre-commit
```

## 3. Демонстрація: коміт із порушеннями стилю блокується

Створено файл `app/demo_bad_style.py` з невикористаними імпортами, невикористаною
змінною та порушеним форматуванням:

```python
import json
import os


def  bookSeat( trip_id,seat ) :
    unused_total=1
    return {"trip":trip_id,"seat":seat}
```

Спроба коміту:

```
$ git add app/demo_bad_style.py
$ git commit -m "demo: спроба закомітити код з порушеннями стилю"

check python ast.........................................................Passed
check for added large files..............................................Passed
check for merge conflicts................................................Passed
fix end of files.........................................................Passed
trim trailing whitespace.................................................Passed
detect private key.......................................................Passed
ruff check...............................................................Failed
- hook id: ruff-check
- exit code: 1
- files were modified by this hook

F841 Local variable `unused_total` is assigned to but never used
 --> app\demo_bad_style.py:4:5
  |
3 | def  bookSeat( trip_id,seat ) :
4 |     unused_total=1
  |     ^^^^^^^^^^^^
5 |     return {"trip":trip_id,"seat":seat}
  |
help: Remove assignment to unused variable `unused_total`

Found 3 errors (2 fixed, 1 remaining).

black....................................................................Failed
- hook id: black
- files were modified by this hook

reformatted app\demo_bad_style.py
1 file reformatted.
```

Результат: коміт **не створено** (`git commit` завершився з кодом 1), `HEAD`
залишився на попередньому коміті. Два порушення з трьох `ruff` виправив
автоматично, `black` переформатував файл — але сам коміт усе одно відхилено,
бо хуки змінили вміст файлів і зміни потрібно переглянути та додати заново.

## 4. Демонстрація: коміт із синтаксичною помилкою блокується

Той самий файл із пропущеною двокрапкою:

```python
def hold_seat(trip_id: int, seat_number: str) -> None
    return None
```

Спроба коміту:

```
$ git add app/demo_bad_style.py
$ git commit -m "demo: спроба закомітити код з синтаксичною помилкою"

check python ast.........................................................Failed
- hook id: check-ast
- exit code: 1

app/demo_bad_style.py: failed parsing with CPython 3.12.4:

    Traceback (most recent call last):
      File ".../pre_commit_hooks/check_ast.py", line 21, in main
        ast.parse(f.read(), filename=filename)
      File ".../ast.py", line 52, in parse
        return compile(source, filename, mode, flags,
      File "app/demo_bad_style.py", line 1
        def hold_seat(trip_id: int, seat_number: str) -> None
                                                             ^
    SyntaxError: expected ':'

ruff check...............................................................Failed
- hook id: ruff-check
- exit code: 1

invalid-syntax: Expected `:`, found newline
 --> app\demo_bad_style.py:1:54
  |
1 | def hold_seat(trip_id: int, seat_number: str) -> None
  |                                                      ^
2 |     return None
  |

Found 1 error.

black....................................................................Failed
- hook id: black
- exit code: 123

error: cannot format app\demo_bad_style.py: Cannot parse for target version Python 3.12: 1:53
1 file failed to reformat.
```

Результат: коміт **не створено**, `HEAD` не змінився. Синтаксичну помилку
перехопили одразу три хуки незалежно один від одного.

Демонстраційний файл після перевірки видалений і в історію репозиторію не потрапив.

## 5. Стан перевірок на робочому коді

```
$ ruff check .
All checks passed!

$ black --check .
33 files would be left unchanged.

$ pytest -q
15 passed

$ alembic check
No new upgrade operations detected.
```

Остання команда — окрема перевірка узгодженості: `alembic check` підтверджує, що
моделі SQLAlchemy не розійшлися з фактичною схемою бази, тобто жодна зміна моделі
не залишилася без міграції.

## 6. Інтеграція з Alembic

Автогенеровані міграції теж проходять форматування: в `alembic.ini` налаштований
post-write хук, який запускає `black` для щойно створеного файлу міграції.

```ini
[post_write_hooks]
hooks = black
black.type = console_scripts
black.entrypoint = black
black.options = -l 100 REVISION_SCRIPT_FILENAME
```

Без цього кожна нова міграція блокувала б коміт через форматування, яке
розробник не писав руками.
