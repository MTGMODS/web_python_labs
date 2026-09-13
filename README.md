# Платформа продажу квитків на міжміські автобуси

Навчальний проєкт з дисципліни «Високонавантажені web-системи».
Предметна область: **платформа продажу квитків на міжміські автобуси з динамічним
розкладом та блокуванням місць під час транзакції** (варіант №15, група «Реалістичний
бізнес та e-commerce»).

Проєкт розвивається наскрізно: кожна наступна лабораторна робота нашаровується на
цей самий домен.

## Стек

| Шар | Технологія |
| --- | --- |
| Backend | Python 3.12, FastAPI |
| ORM / міграції | SQLAlchemy 2.0, Alembic |
| База даних | PostgreSQL 17 (драйвер psycopg3) |
| Автентифікація | JWT (HS256), bcrypt, дві ролі: passenger / admin |
| Сторінки | Jinja2 (вхід, реєстрація, кабінети ролей) |
| Якість коду | ruff, black, pre-commit |
| Тести | pytest |

PostgreSQL використовується з першої роботи свідомо: ключовий сценарій навантаження
цієї предметної області — конкурентне бронювання одного місця, і його неможливо
коректно відтворити на SQLite через блокування бази цілком замість блокування рядка.

## Структура репозиторію

```
app/            код застосунку (API, конфігурація, моделі, домен)
config/         приклади конфігураційних файлів
deploy/         інфраструктура (docker compose)
docs/           документація та схеми архітектури
migrations/     міграції Alembic
scripts/        допоміжні скрипти (наповнення БД демоданими)
tests/          автотести
```

## Запуск

```powershell
# 1. Залежності
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 2. Конфігурація
Copy-Item config\env.example .env

# 3. База даних
docker compose -f deploy/docker-compose.yml up -d

# 4. Міграції та демодані
alembic upgrade head
python -m scripts.seed

# 5. Застосунок
uvicorn app.main:app --reload
```

Документація API: http://127.0.0.1:8000/docs

Після `seed` можна увійти готовими акаунтами:

| Роль | Email | Пароль | Сторінка |
| --- | --- | --- | --- |
| адміністратор | `admin@busline.ua` | `admin12345` | http://127.0.0.1:8000/admin |
| пасажир | `passenger@busline.ua` | `passenger123` | http://127.0.0.1:8000/home |
| другий пасажир | `passenger2@busline.ua` | `passenger123` | для демонстрації IDOR |

Окремий адміністратор: `python -m scripts.create_admin --email you@busline.ua --password secret-pass`

## Перевірка якості коду

```powershell
pre-commit install          # активувати хуки в локальному репозиторії
pre-commit run --all-files  # перевірити весь проєкт
ruff check .
black --check .
pytest
```

## Документація

- [Обґрунтування предметної області](docs/01-domain.md)
- [Архітектура системи](docs/02-architecture.md)
- [Контроль якості коду та pre-commit](docs/03-code-quality.md)
- [Користувачі, ролі та розмежування доступу](docs/04-auth-and-access.md)
