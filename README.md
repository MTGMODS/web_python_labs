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

Повний стек (база + застосунок) піднімається однією командою. Контейнер сам
застосовує міграції та наповнює демодані.

```powershell
docker compose -f deploy/docker-compose.yml up --build
```

- Сайт (інтерфейс для користувача): http://127.0.0.1:8000/
- Вхід: http://127.0.0.1:8000/login
- Swagger / OpenAPI (окремо, з сайту не лінкується): http://127.0.0.1:8000/docs
- Зупинити: `docker compose -f deploy/docker-compose.yml down` (том з даними лишається)

Локальний запуск uvicorn без контейнера застосунку (для тестів і відлагодження):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config\env.example .env
docker compose -f deploy/docker-compose.yml up -d db
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

Сайт — інтерфейс для пасажира й перевізника: розклад, схема салону, оплата,
кабінети. Службові шляхи (`/docs`, `/redoc`, `/openapi.json`, `/health`, `/api/v1`)
не показуються в навігації; їх можна відкрити вручну за прямим URL.

Після `seed` можна увійти готовими акаунтами:

| Роль | Email | Пароль | Сторінка |
| --- | --- | --- | --- |
| адміністратор | `admin@busline.ua` | `admin12345` | http://127.0.0.1:8000/admin |
| пасажир | `passenger@busline.ua` | `passenger123` | розклад `/`, квитки `/home` |
| другий пасажир | `passenger2@busline.ua` | `passenger123` | для демонстрації IDOR |

Окремий адміністратор:

```powershell
# у контейнері
docker compose -f deploy/docker-compose.yml exec app python -m scripts.create_admin you@busline.ua secret-pass

# або локально, якщо uvicorn на хості
python -m scripts.create_admin you@busline.ua secret-pass
```

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
