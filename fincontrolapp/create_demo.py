"""
Создаёт тестовый аккаунт с данными за 2024, 2025 и 2026 год (до 16 мая 2026).
Логин: demo@test.ru  Пароль: Demo2024
Запускать из папки fincontrolapp: python create_demo.py
"""
import hashlib
import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from database import create_tables, get_connection


# ── Хэш пароля (pbkdf2, как в auth.py) ───────────────────────────────────────

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + ':' + key.hex()


# ── Создаём таблицы (если не существуют) ─────────────────────────────────────

create_tables()

EMAIL    = "demo@test.ru"
PASSWORD = "Demo2024"

with get_connection() as conn:

    # ── Удаляем старый демо-аккаунт если есть ────────────────────────────────
    old = conn.execute("SELECT id FROM users WHERE email=?", (EMAIL,)).fetchone()
    if old:
        uid = old["id"]
        conn.execute("DELETE FROM transactions   WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM goals          WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM subscriptions  WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM budgets        WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM purchase_timers WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM users          WHERE id=?",      (uid,))
        print("Старый demo-аккаунт удалён.")

    # ── Пользователь ─────────────────────────────────────────────────────────
    pwd_hash = hash_password(PASSWORD)
    conn.execute(
        "INSERT INTO users (email, username, password_hash, notification_hour) VALUES (?, ?, ?, ?)",
        (EMAIL, "Дмитрий", pwd_hash, 9),
    )
    user_id = conn.execute("SELECT id FROM users WHERE email=?", (EMAIL,)).fetchone()["id"]
    print(f"Пользователь создан: id={user_id}")

    # ── Категории ─────────────────────────────────────────────────────────────
    def cat(name, type_):
        row = conn.execute(
            "SELECT id FROM categories WHERE name=? AND type=?", (name, type_)
        ).fetchone()
        if row:
            return row["id"]
        conn.execute("INSERT INTO categories (name, type) VALUES (?, ?)", (name, type_))
        return conn.execute(
            "SELECT id FROM categories WHERE name=? AND type=?", (name, type_)
        ).fetchone()["id"]

    c_salary      = cat("Зарплата",        "income")
    c_freelance   = cat("Фриланс",         "income")
    c_other_in    = cat("Другое",          "income")
    c_food        = cat("Еда",             "expense")
    c_transport   = cat("Транспорт",       "expense")
    c_health      = cat("Здоровье",        "expense")
    c_shopping    = cat("Покупки",         "expense")
    c_fun         = cat("Развлечения",     "expense")
    c_home        = cat("Жильё",           "expense")
    c_edu         = cat("Образование",     "expense")
    c_savings     = cat("Накопления",      "expense")
    c_subs        = cat("Подписки",        "expense")

    # ── Хелпер добавления транзакций ──────────────────────────────────────────
    def tx(type_, amount, category_id, description, day: date, is_recurring=0):
        conn.execute(
            """INSERT INTO transactions
               (user_id, type, amount, category_id, description, date, is_recurring)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, type_, amount, category_id, description, day.isoformat(), is_recurring),
        )

    # ── Генерация дат ─────────────────────────────────────────────────────────
    START = date(2024, 1, 1)
    END   = date(2026, 5, 16)

    def months_range(start: date, end: date):
        cur = date(start.year, start.month, 1)
        while cur <= end:
            yield cur
            if cur.month == 12:
                cur = date(cur.year + 1, 1, 1)
            else:
                cur = date(cur.year, cur.month + 1, 1)

    def clamp(d: date) -> date:
        return min(d, END)

    rng = random.Random(42)   # фиксированный seed — воспроизводимо

    # ── ДОХОДЫ ───────────────────────────────────────────────────────────────
    # Зарплата растёт по годам
    salary_by_year = {2024: 95_000, 2025: 110_000, 2026: 125_000}

    for m in months_range(START, END):
        salary = salary_by_year[m.year]
        payday = clamp(date(m.year, m.month, 10))
        tx("income", salary, c_salary, "Зарплата", payday, is_recurring=1)

        # Фриланс — каждые 2-3 месяца
        if rng.random() < 0.35:
            amount = rng.randint(15, 60) * 1000
            fday = clamp(date(m.year, m.month, rng.randint(12, 28)))
            tx("income", amount, c_freelance, "Проект " + rng.choice(
                ["сайт", "дизайн", "консультация", "анализ данных", "вёрстка"]), fday)

        # Прочие доходы — редко
        if rng.random() < 0.12:
            tx("income", rng.randint(2, 10) * 1000, c_other_in, "Продажа вещей",
               clamp(date(m.year, m.month, rng.randint(5, 25))))

    # ── РАСХОДЫ — ежемесячные статьи ─────────────────────────────────────────
    for m in months_range(START, END):
        yr, mo = m.year, m.month

        # Аренда (1-го числа)
        rent = {2024: 35_000, 2025: 38_000, 2026: 40_000}[yr]
        tx("expense", rent, c_home, "Аренда квартиры", clamp(date(yr, mo, 1)))

        # Коммуналка
        util = rng.randint(4_500, 7_500)
        tx("expense", util, c_home, "Коммунальные услуги",
           clamp(date(yr, mo, rng.randint(5, 12))))

        # Еда — несколько транзакций в месяц
        food_total = rng.randint(22_000, 34_000)
        weeks = rng.randint(3, 5)
        for w in range(weeks):
            d = clamp(date(yr, mo, min(28, 1 + w * 7 + rng.randint(0, 4))))
            places = ["Вкусвилл", "Пятёрочка", "Перекрёсток", "Ашан", "Кафе", "Доставка еды",
                      "Магазин", "Суши-бар", "Пиццерия", "Рынок"]
            tx("expense", food_total // weeks + rng.randint(-500, 500),
               c_food, rng.choice(places), d)

        # Транспорт
        for _ in range(rng.randint(2, 4)):
            d = clamp(date(yr, mo, rng.randint(2, 28)))
            place = rng.choice(["Метро/автобус", "Яндекс.Такси", "Каршеринг", "Бензин",
                                 "Парковка", "Самокат"])
            tx("expense", rng.randint(300, 4_500), c_transport, place, d)

        # Развлечения
        for _ in range(rng.randint(1, 4)):
            d = clamp(date(yr, mo, rng.randint(3, 28)))
            place = rng.choice(["Кино", "Концерт", "Бар", "Ресторан", "Боулинг",
                                 "Выставка", "Квест", "Steam игры", "Театр"])
            tx("expense", rng.randint(700, 8_000), c_fun, place, d)

        # Покупки
        for _ in range(rng.randint(1, 3)):
            d = clamp(date(yr, mo, rng.randint(3, 28)))
            item = rng.choice(["Wildberries", "Ozon", "Одежда", "Обувь", "Электроника",
                                "Аксессуары", "Книги", "Спорттовары", "Косметика"])
            tx("expense", rng.randint(500, 12_000), c_shopping, item, d)

        # Накопления — ежемесячный перевод
        save_amt = {2024: 10_000, 2025: 15_000, 2026: 18_000}[yr]
        tx("expense", save_amt, c_savings, "Пополнение накоп. счёта",
           clamp(date(yr, mo, 20)))

        # Здоровье — 2-3 раза в квартал
        if rng.random() < 0.28:
            place = rng.choice(["Аптека", "Стоматолог", "Врач", "Анализы", "Спортзал абон."])
            tx("expense", rng.randint(500, 9_500), c_health, place,
               clamp(date(yr, mo, rng.randint(5, 25))))

        # Образование — раз в 3-4 месяца
        if rng.random() < 0.22:
            place = rng.choice(["Курс Stepik", "Udemy", "Курс английского", "Книга по Python",
                                 "Нетология", "Coursera", "YouTube Premium"])
            tx("expense", rng.randint(990, 15_000), c_edu, place,
               clamp(date(yr, mo, rng.randint(5, 25))))

    # ── КРУПНЫЕ ПОКУПКИ ───────────────────────────────────────────────────────
    big_purchases = [
        (date(2024, 3, 15), 85_000,  c_shopping, "iPhone 15"),
        (date(2024, 7, 20), 45_000,  c_shopping, "Монитор Samsung 27\""),
        (date(2024, 11, 11), 12_500, c_shopping, "Распродажа 11.11 — Ozon"),
        (date(2025, 2, 14), 18_000,  c_fun,      "Поездка на выходные"),
        (date(2025, 5, 1),  120_000, c_fun,      "Отпуск — Турция"),
        (date(2025, 8, 20), 62_000,  c_shopping, "MacBook аксессуары"),
        (date(2025, 12, 25), 9_800,  c_shopping, "Новогодние подарки"),
        (date(2026, 1, 15), 35_000,  c_health,   "Обследование (чек-ап)"),
        (date(2026, 3, 8),  22_000,  c_shopping, "Подарок на 8 марта"),
        (date(2026, 4, 20), 78_000,  c_shopping, "iPad Air"),
    ]
    for d, amt, cat_id, desc in big_purchases:
        if d <= END:
            tx("expense", amt, cat_id, desc, d)

    # ── ПОДПИСКИ ─────────────────────────────────────────────────────────────
    subs = [
        ("Яндекс Плюс",   299,   5,  "monthly", "2024-01-05"),
        ("Spotify",        199,   8,  "monthly", "2024-01-08"),
        ("iCloud 50GB",    149,   1,  "monthly", "2024-02-01"),
        ("ChatGPT Plus",  1990,  15,  "monthly", "2024-06-15"),
        ("Notion",         399,  20,  "monthly", "2024-09-20"),
        ("1Password",     1499,   1,  "yearly",  "2024-03-01"),
        ("Литрес",         599,  12,  "monthly", "2025-01-12"),
    ]
    for name, amount, charge_day, period, start_date in subs:
        conn.execute(
            """INSERT INTO subscriptions
               (user_id, name, amount, charge_day, period, start_date, is_paused, last_charged_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
            (user_id, name, amount, charge_day, period, start_date,
             "2026-05-01" if period == "monthly" else "2025-03-01"),
        )

    # ── ЦЕЛИ ─────────────────────────────────────────────────────────────────
    goals = [
        ("Автомобиль",       1_500_000, 320_000, "2027-12-31"),
        ("Отпуск на Бали",     250_000, 185_000, "2026-08-01"),
        ("MacBook Pro M4",     250_000, 250_000, "2026-02-01"),  # достигнута
        ("Подушка безопасности", 300_000, 178_000, "2026-12-31"),
        ("Ремонт",             800_000,  95_000, "2028-06-01"),
    ]
    for name, target, current, deadline in goals:
        conn.execute(
            """INSERT INTO goals (user_id, name, target_amount, current_amount, deadline)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, name, target, current, deadline),
        )

    # ── БЮДЖЕТЫ ──────────────────────────────────────────────────────────────
    budgets = [
        (c_food,      32_000, "monthly"),
        (c_fun,       15_000, "monthly"),
        (c_transport,  8_000, "monthly"),
        (c_shopping,  20_000, "monthly"),
        (c_health,    10_000, "monthly"),
        (c_home,      50_000, "monthly"),
    ]
    for cat_id, limit, period in budgets:
        try:
            conn.execute(
                """INSERT INTO budgets (user_id, category_id, limit_amount, period)
                   VALUES (?, ?, ?, ?)""",
                (user_id, cat_id, limit, period),
            )
        except Exception:
            pass  # UNIQUE constraint если уже есть

    # ── Итог ──────────────────────────────────────────────────────────────────
    n_tx   = conn.execute("SELECT COUNT(*) FROM transactions WHERE user_id=?", (user_id,)).fetchone()[0]
    n_sub  = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()[0]
    n_goal = conn.execute("SELECT COUNT(*) FROM goals       WHERE user_id=?", (user_id,)).fetchone()[0]
    n_bud  = conn.execute("SELECT COUNT(*) FROM budgets     WHERE user_id=?", (user_id,)).fetchone()[0]

    print(f"\n✅ Демо-аккаунт готов:")
    print(f"   Логин:      {EMAIL}")
    print(f"   Пароль:     {PASSWORD}")
    print(f"   Транзакций: {n_tx}")
    print(f"   Подписки:   {n_sub}")
    print(f"   Цели:       {n_goal}")
    print(f"   Бюджеты:    {n_bud}")
