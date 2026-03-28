#!/usr/bin/env python3
"""
Generate India-native scenario data for SimWork's checkout conversion drop case.

Scenario:
- Company: ZaikaNow, a fictional India food-delivery marketplace (inspired by Swiggy/Zomato)
- Three embedded problems at different difficulty levels:
  - Easy:   "Promo Cliff" — New Year campaign ending looks like a drop
  - Medium: "RupeeFlow v3 Migration" — UPI payment regression on Jan 10
  - Hard:   "Trust Erosion Cascade" — behavioral trust damage persists after technical fix

Schema principles:
- MECE: each fact lives in ONE table, referenced via FK elsewhere
- city/platform/user_type live in `users` — other tables JOIN to get them
- ~50K orders over 6 months (Oct 2024 – Mar 2025)
"""

from __future__ import annotations

import hashlib
import os
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

random.seed(42)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLES_DIR = os.path.join(SCRIPT_DIR, "tables")
DB_PATH = os.path.join(TABLES_DIR, "scenario.db")
os.makedirs(TABLES_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Timeline constants
# ---------------------------------------------------------------------------
START_DATE = datetime(2024, 10, 1)
END_DATE = datetime(2025, 3, 31, 23, 59, 59)
PROMO_START = datetime(2024, 12, 20)
PROMO_END = datetime(2024, 12, 26)
MIGRATION_DATE = datetime(2025, 1, 10)
HOTFIX_DATE = datetime(2025, 2, 1)
TRUST_DAMAGE_DATE = datetime(2025, 2, 16)

# ---------------------------------------------------------------------------
# Market profile — India food delivery
# ---------------------------------------------------------------------------
PROFILE = {
    "brand_name": "ZaikaNow",
    "currency": "INR",
    "email_domain": "zaikanow.in",
    "cities": [
        ("bengaluru", 24, ["Koramangala", "Indiranagar", "HSR Layout", "Whitefield", "Jayanagar"]),
        ("mumbai", 21, ["Andheri West", "Powai", "Bandra", "Ghatkopar", "Lower Parel"]),
        ("delhi_ncr", 19, ["Gurugram Sector 56", "Noida Sector 62", "Saket", "Dwarka", "Indirapuram"]),
        ("hyderabad", 14, ["Madhapur", "Gachibowli", "Kondapur", "Banjara Hills", "Kukatpally"]),
        ("pune", 12, ["Hinjewadi", "Kothrud", "Viman Nagar", "Baner", "Wakad"]),
        ("chennai", 10, ["Velachery", "Anna Nagar", "Adyar", "OMR", "T Nagar"]),
    ],
    "platforms": ["ios", "android", "web"],
    "platform_mix": [18, 62, 20],
    "user_types": ["new", "casual", "returning", "power"],
    "user_type_mix": [28, 27, 30, 15],
    "first_names": [
        "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Ishaan", "Reyansh", "Krishna", "Rohan",
        "Ananya", "Diya", "Aadhya", "Mira", "Saanvi", "Ira", "Kiara", "Myra", "Kavya", "Nitya",
        "Rahul", "Karthik", "Varun", "Pranav", "Akash", "Nikhil", "Siddharth", "Harsh", "Yash", "Neha",
        "Pooja", "Riya", "Sneha", "Anika", "Ishita", "Shruti", "Aarti", "Nandini", "Meera", "Tanvi",
        "Aman", "Ritika", "Sakshi", "Abhishek", "Divya", "Manav", "Preeti", "Lakshmi", "Arvind", "Priya",
        "Deepak", "Ayesha", "Vikram", "Shreya", "Madhav", "Anjali", "Surya", "Bhavna", "Ritesh", "Manya",
    ],
    "last_names": [
        "Sharma", "Verma", "Patel", "Reddy", "Nair", "Rao", "Iyer", "Gupta", "Agarwal", "Mehta",
        "Kulkarni", "Joshi", "Yadav", "Singh", "Khan", "Chopra", "Bansal", "Kapoor", "Mishra", "Pillai",
        "Menon", "Saxena", "Ghosh", "Bose", "Banerjee", "Desai", "Bhatt", "Trivedi", "Pandey", "Choudhary",
        "Malhotra", "Sethi", "Jain", "Dubey", "Tiwari", "Kamble", "Shetty", "Das", "Mukherjee", "Thakur",
    ],
    "restaurant_taxonomy": {
        "north_indian": {
            "names": ["Punjabi Tadka", "Dilli Zaika", "Tandoor Junction", "Royal Curry House", "Ghar Ka Khana Co."],
            "menu": [
                ("Butter Chicken", "Creamy tomato gravy with tandoori chicken", 329),
                ("Paneer Lababdar", "Rich tomato gravy with paneer cubes", 289),
                ("Dal Makhani", "Slow-cooked black lentils with butter", 249),
                ("Butter Naan", "Tandoor-baked naan brushed with butter", 49),
                ("Veg Thali", "North Indian combo meal with roti and rice", 269),
            ],
        },
        "south_indian": {
            "names": ["Anna Idli House", "Udupi Breakfast Club", "Filter Coffee Stories", "Dosa Darbar", "Ghee Roast Kitchen"],
            "menu": [
                ("Masala Dosa", "Crisp dosa with potato filling", 149),
                ("Idli Vada Combo", "Steamed idlis with vada and chutneys", 129),
                ("Podi Dosa", "Dosa dusted with podi masala", 159),
                ("Mini Tiffin", "Assorted breakfast platter", 189),
                ("Filter Coffee", "South Indian filter kaapi", 59),
            ],
        },
        "biryani": {
            "names": ["Biryani Adda", "Nawab Dum House", "Hyderabadi Handi", "Biryani Junction", "Dum Safar"],
            "menu": [
                ("Chicken Dum Biryani", "Hyderabadi-style chicken biryani", 299),
                ("Paneer Biryani", "Fragrant rice layered with paneer masala", 259),
                ("Mutton Biryani", "Slow-cooked biryani with tender mutton", 379),
                ("Double Ka Meetha", "Traditional Hyderabadi dessert", 99),
                ("Mirchi Ka Salan", "Spicy peanut-coconut curry", 79),
            ],
        },
        "street_food": {
            "names": ["Rolls & Rice", "The Frankie Stop", "Nukkad Eats", "Bombay Bites", "Street Treats Co."],
            "menu": [
                ("Paneer Kathi Roll", "Roomali roll stuffed with paneer tikka", 169),
                ("Chicken Shawarma Roll", "Loaded shawarma with garlic mayo", 189),
                ("Pav Bhaji", "Buttery bhaji served with pav", 149),
                ("Veg Momos", "Steamed momos with red chutney", 129),
                ("Chicken Momos", "Juicy steamed chicken momos", 149),
            ],
        },
        "chaat": {
            "names": ["Chaat Junction", "Tangy Tales", "Raj Kachori Point", "Chatpata Express", "Golgappa Factory"],
            "menu": [
                ("Raj Kachori", "Crisp kachori loaded with chaat toppings", 139),
                ("Dahi Puri", "Crispy puris with curd and chutneys", 119),
                ("Papdi Chaat", "Papdi with potatoes, curd, and chutneys", 109),
                ("Sev Puri", "Mumbai-style street snack", 99),
                ("Pani Puri Kit", "Take-home golgappa set", 129),
            ],
        },
        "desserts": {
            "names": ["Kulfi Collective", "Mithai Studio", "Sweet Cravings", "Dessert Wale", "Shahi Sweets"],
            "menu": [
                ("Matka Kulfi", "Traditional kulfi served in clay pot", 99),
                ("Gulab Jamun", "Warm gulab jamun with syrup", 89),
                ("Rasmalai", "Soft rasmalai in saffron milk", 109),
                ("Chocolate Brownie", "Brownie with hot chocolate sauce", 139),
                ("Falooda", "Rose falooda with ice cream", 149),
            ],
        },
        "pizza": {
            "names": ["Pizza Planet India", "Cheese Burst Co.", "Slice Junction", "Oven Stories Local", "Crust Republic"],
            "menu": [
                ("Paneer Tikka Pizza", "Pizza topped with paneer tikka and onions", 279),
                ("Farmhouse Pizza", "Capsicum, mushroom, onion, tomato", 259),
                ("Chicken Keema Pizza", "Spiced keema pizza with cheese", 299),
                ("Garlic Breadsticks", "Garlicky breadsticks with dip", 119),
                ("Choco Lava Cake", "Warm chocolate-filled cake", 99),
            ],
        },
        "burgers": {
            "names": ["Patty Pe Charcha", "Burger Adda", "Stacked Bun Co.", "Smash & Spice", "Desi Burger Lab"],
            "menu": [
                ("Aloo Tikki Burger", "Classic Indian veg burger", 129),
                ("Peri Peri Paneer Burger", "Paneer patty with peri peri sauce", 179),
                ("Chicken Maharaja Burger", "Double chicken burger with signature sauce", 229),
                ("Masala Fries", "Fries tossed in Indian spice mix", 99),
                ("Cold Coffee", "Iced coffee with vanilla ice cream", 119),
            ],
        },
        "chinese": {
            "names": ["Wok on Fire", "Dragon Wok Express", "Desi Chinese Hub", "Hakka Stories", "Wok & Bowl"],
            "menu": [
                ("Veg Hakka Noodles", "Indo-Chinese wok tossed noodles", 169),
                ("Chicken Fried Rice", "Classic fried rice with chicken", 199),
                ("Chilli Paneer", "Paneer tossed in spicy chilli sauce", 189),
                ("Chicken Manchurian", "Juicy chicken balls in gravy", 219),
                ("Schezwan Momos", "Momos tossed in schezwan sauce", 159),
            ],
        },
        "healthy": {
            "names": ["Balanced Bowls", "Salad & Soul", "Protein Pantry", "Fresh Pressed", "Green Plate Kitchen"],
            "menu": [
                ("Paneer Quinoa Bowl", "High-protein bowl with paneer and quinoa", 249),
                ("Chicken Millet Bowl", "Millet bowl with grilled chicken", 279),
                ("Greek Yogurt Parfait", "Yogurt, fruit, and granola", 159),
                ("Cold Pressed Juice", "Seasonal fruit and veggie juice", 129),
                ("Sprouts Chaat", "Protein-rich sprout salad", 149),
            ],
        },
    },
    "ios_devices": ["iPhone 13", "iPhone 14", "iPhone 15", "iPhone 15 Pro", "iPhone SE"],
    "android_devices": ["OnePlus 12", "Samsung S24", "Pixel 8", "Redmi Note 13", "Vivo V30", "Realme GT"],
    "web_devices": ["Chrome", "Safari", "Firefox", "Edge"],
    "bank_names": ["HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak", "IDFC First"],
    "incident_profile": {
        "primary_cities": {"bengaluru", "mumbai", "delhi_ncr"},
        "primary_platform": "android",
        "primary_method": "upi",
        "provider_v2": "rupeeflow_v2",
        "provider_v3": "rupeeflow_v3",
    },
}

PLATFORMS = PROFILE["platforms"]
CITIES = [city for city, _, _ in PROFILE["cities"]]
CITY_WEIGHTS = [weight for _, weight, _ in PROFILE["cities"]]
CITY_AREAS = {city: areas for city, _, areas in PROFILE["cities"]}
USER_TYPES = PROFILE["user_types"]
CONN: sqlite3.Connection | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def jitter(value: float, pct: float = 0.05) -> float:
    return value * (1 + random.uniform(-pct, pct))


def weighted_choice(items, weights):
    return random.choices(items, weights=weights, k=1)[0]


def random_datetime(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def gen_commit_hash() -> str:
    return hashlib.md5(str(random.random()).encode()).hexdigest()[:7]


def gen_phone() -> str:
    return f"+91{random.randint(6000000000, 9999999999)}"


def sanitize_token(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def phase_for_date(current: datetime) -> str:
    if current < MIGRATION_DATE:
        return "baseline"
    if current < HOTFIX_DATE:
        return "incident"
    if current < TRUST_DAMAGE_DATE:
        return "partial_recovery"
    return "trust_damage"


def is_promo_period(current: datetime) -> bool:
    return PROMO_START.date() <= current.date() <= PROMO_END.date()


def city_is_primary(city: str) -> bool:
    return city in PROFILE["incident_profile"]["primary_cities"]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def reset_database() -> sqlite3.Connection:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS documents (name TEXT PRIMARY KEY, content TEXT NOT NULL)")
    conn.commit()
    return conn


def _infer_sqlite_type(values: list[object]) -> str:
    non_null = [v for v in values if v not in {"", None}]
    if not non_null:
        return "TEXT"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
        return "INTEGER"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "REAL"
    return "TEXT"


def write_table(table_name: str, headers: list[str], rows: list[list[object]]) -> None:
    if CONN is None:
        raise RuntimeError("Database connection not initialized.")
    column_types = [_infer_sqlite_type([row[i] for row in rows]) for i in range(len(headers))]
    col_defs = ", ".join(f"[{h}] {t}" for h, t in zip(headers, column_types))
    placeholders = ", ".join("?" for _ in headers)
    CONN.execute(f"DROP TABLE IF EXISTS [{table_name}]")
    CONN.execute(f"CREATE TABLE [{table_name}] ({col_defs})")
    CONN.executemany(
        f"INSERT INTO [{table_name}] ({', '.join(f'[{h}]' for h in headers)}) VALUES ({placeholders})",
        rows,
    )
    CONN.commit()
    print(f"  -> {table_name}: {len(rows)} rows")


def write_md(filename: str, content: str) -> None:
    if CONN is None:
        raise RuntimeError("Database connection not initialized.")
    CONN.execute("INSERT OR REPLACE INTO documents (name, content) VALUES (?, ?)", (filename, content))
    CONN.commit()
    print(f"  -> {filename}: written to documents table")


# ===========================================================================
# TABLE GENERATORS
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. users — PK: user_id — SINGLE source of truth for city, platform, user_type
# ---------------------------------------------------------------------------
def generate_users(n: int = 3000):
    print("Generating users...")
    rows = []
    for i in range(1, n + 1):
        user_id = f"U{i:05d}"
        first = random.choice(PROFILE["first_names"])
        last = random.choice(PROFILE["last_names"])
        city = weighted_choice(CITIES, CITY_WEIGHTS)
        area = random.choice(CITY_AREAS[city])
        platform = weighted_choice(PLATFORMS, PROFILE["platform_mix"])
        user_type = weighted_choice(USER_TYPES, PROFILE["user_type_mix"])
        signup = random_datetime(datetime(2023, 1, 1), datetime(2025, 3, 20)).strftime("%Y-%m-%d")
        email = f"{sanitize_token(first)}.{sanitize_token(last)}{i}@{PROFILE['email_domain']}"
        rows.append([user_id, f"{first} {last}", email, gen_phone(), city, area, signup, platform, user_type])
    write_table("users", ["user_id", "name", "email", "phone", "city", "area", "signup_date", "platform", "user_type"], rows)
    return rows


# ---------------------------------------------------------------------------
# 2. restaurants — PK: restaurant_id — own city/area (restaurant location ≠ user location)
# ---------------------------------------------------------------------------
def generate_restaurants():
    print("Generating restaurants...")
    rows = []
    rid = 1
    for city in CITIES:
        for cuisine, details in PROFILE["restaurant_taxonomy"].items():
            names = details["names"]
            for name in random.sample(names, min(2, len(names))):
                area = random.choice(CITY_AREAS[city])
                rating = round(random.uniform(3.7, 4.8), 1)
                rows.append([f"R{rid:04d}", name, cuisine, city, area, rating])
                rid += 1
    write_table("restaurants", ["restaurant_id", "name", "cuisine_type", "city", "area", "rating"], rows)
    return rows


# ---------------------------------------------------------------------------
# 3. menu_items — PK: item_id — FK: restaurant_id
# ---------------------------------------------------------------------------
def generate_menu_items(restaurants):
    print("Generating menu_items...")
    rows = []
    item_id = 1
    restaurant_menu_map = {}
    for restaurant in restaurants:
        restaurant_id = restaurant[0]
        cuisine = restaurant[2]
        menu = PROFILE["restaurant_taxonomy"][cuisine]["menu"]
        sampled = random.sample(menu, min(len(menu), random.randint(4, 5)))
        ids = []
        for name, description, price in sampled:
            ids.append(f"MI{item_id:05d}")
            rows.append([f"MI{item_id:05d}", restaurant_id, name, description, price])
            item_id += 1
        restaurant_menu_map[restaurant_id] = ids
    write_table("menu_items", ["item_id", "restaurant_id", "name", "description", "price"], rows)
    return rows, restaurant_menu_map


# ---------------------------------------------------------------------------
# 4. orders — PK: order_id — FK: user_id, restaurant_id
#    NO platform/city columns — JOIN to users for those
# ---------------------------------------------------------------------------
def daily_order_target(current: datetime) -> int:
    """Flat ~270/day baseline. Orders are derived from funnel sessions, but this
    function is kept for any non-session order logic. The actual order volume is
    driven by session_target_for() + session_completion_prob()."""
    base = 270
    if current.weekday() in (5, 6):
        base = int(base * 1.10)
    if is_promo_period(current):
        base = int(base * 1.12)
    if phase_for_date(current) == "trust_damage":
        base = int(base * 0.92)
    return max(150, int(jitter(base, 0.04)))


def order_status_probs(current: datetime, platform: str, city: str, user_type: str, method: str = "upi") -> tuple[float, float]:
    """Return (fail_rate, cancel_rate) based on phase/segment/payment method."""
    phase = phase_for_date(current)
    fail_rate = 0.04
    cancel_rate = 0.10

    is_primary = city_is_primary(city)
    is_upi = method == "upi"

    if phase == "incident":
        # UPI orders fail at higher rates due to RupeeFlow v3 migration.
        # Non-UPI payment methods are unaffected by the migration.
        if is_upi and platform == "android" and is_primary:
            fail_rate = 0.22
            cancel_rate = 0.18
        elif is_upi and is_primary:
            fail_rate = 0.14
            cancel_rate = 0.14
        elif is_upi:
            fail_rate = 0.10
            cancel_rate = 0.12
        else:
            # Non-UPI: near baseline — migration doesn't affect these methods
            fail_rate = 0.05
            cancel_rate = 0.11
    elif phase == "partial_recovery":
        if is_upi and platform == "android" and is_primary:
            fail_rate = 0.08
            cancel_rate = 0.13
        elif is_upi:
            fail_rate = 0.06
            cancel_rate = 0.11
        else:
            fail_rate = 0.04
            cancel_rate = 0.11
    elif phase == "trust_damage":
        # Technical metrics mostly recovered
        fail_rate = 0.05
        cancel_rate = 0.10
        # Hard problem: power/returning users on Android in primary metros
        # show elevated cancellation — behavioral, not technical
        if user_type in {"returning", "power"} and platform == "android" and is_primary:
            cancel_rate = 0.15  # vs 0.10 baseline — clear gap

    return fail_rate, cancel_rate


def generate_orders(users, restaurants, restaurant_menu_map, menu_items, drivers, completed_sessions, failed_sessions):
    """Generate orders from both completed and failed funnel sessions.

    Completed sessions produce orders with status determined by order_status_probs.
    Failed sessions (reached payment_attempt but not order_complete) always produce
    failed orders — these represent payment attempts that never succeeded.
    """
    print("Generating orders...")
    user_lookup = {u[0]: {"platform": u[7], "city": u[4], "user_type": u[8]} for u in users}
    # Price lookup: item_id → price
    item_price = {row[0]: float(row[4]) for row in menu_items}
    # Build city → restaurant_ids lookup (user orders from same city)
    restaurants_by_city = defaultdict(list)
    for r in restaurants:
        restaurants_by_city[r[3]].append(r[0])
    # Build city → driver_ids lookup for driver assignment
    drivers_by_city = defaultdict(list)
    for d in drivers:
        drivers_by_city[d[3]].append(d[0])

    order_rows = []
    oi_rows = []
    order_id = 1
    oi_id = 1
    for s in completed_sessions:
        user_id = s["user_id"]
        city = s["city"]
        user_type = s["user_type"]
        platform = s["platform"]
        current = s["date"]
        phase = phase_for_date(current)

        # Use payment method assigned at session creation (in generate_funnel_events)
        method = s.get("payment_method") or payment_method_for(platform)

        fail_rate, cancel_rate = order_status_probs(current, platform, city, user_type, method)

        # Hard problem: trust-damaged cohort cancels 20% of orders
        if phase == "trust_damage" and user_type in {"returning", "power"} and platform == "android" and city_is_primary(city):
            if random.random() < 0.20:
                cancel_rate = 1.0  # force this order to be cancelled
                fail_rate = 0.0
        r = random.random()
        if r < fail_rate:
            status = "failed"
        elif r < fail_rate + cancel_rate:
            status = "cancelled"
        else:
            status = "completed"

        # Restaurant must be in the same city as the user
        restaurant_id = random.choice(restaurants_by_city[city])
        # Assign driver from same city for completed orders
        if status == "completed":
            driver_id = random.choice(drivers_by_city[city])
        else:
            driver_id = ""

        # Generate order_items and compute total_amount from actual prices
        order_id_str = f"ORD{order_id:06d}"
        menu_ids = restaurant_menu_map.get(restaurant_id, [])
        if menu_ids:
            k = weighted_choice([1, 2, 3, 4], [15, 42, 31, 12])
            selected_items = random.sample(menu_ids, k=min(k, len(menu_ids)))
        else:
            selected_items = []
        total_amount = 0.0
        for item_id in selected_items:
            quantity = weighted_choice([1, 2, 3], [72, 23, 5])
            total_amount += item_price[item_id] * quantity
            oi_rows.append([f"OI{oi_id:06d}", order_id_str, item_id, quantity])
            oi_id += 1

        order_rows.append([
            order_id_str, user_id, restaurant_id, driver_id, s["session_id"],
            status, f"{total_amount:.2f}", s["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
        ])
        order_id += 1

    # Failed sessions: payment was attempted but never succeeded → always "failed" orders
    for s in failed_sessions:
        user_id = s["user_id"]
        city = s["city"]
        current = s["date"]

        restaurant_id = random.choice(restaurants_by_city[city])
        order_id_str = f"ORD{order_id:06d}"
        menu_ids = restaurant_menu_map.get(restaurant_id, [])
        if menu_ids:
            k = weighted_choice([1, 2, 3, 4], [15, 42, 31, 12])
            selected_items = random.sample(menu_ids, k=min(k, len(menu_ids)))
        else:
            selected_items = []
        total_amount = 0.0
        for item_id in selected_items:
            quantity = weighted_choice([1, 2, 3], [72, 23, 5])
            total_amount += item_price[item_id] * quantity
            oi_rows.append([f"OI{oi_id:06d}", order_id_str, item_id, quantity])
            oi_id += 1

        order_rows.append([
            order_id_str, user_id, restaurant_id, "", s["session_id"],
            "failed", f"{total_amount:.2f}", s["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
        ])
        order_id += 1

    write_table("orders", ["order_id", "user_id", "restaurant_id", "driver_id", "session_id", "order_status", "total_amount", "created_at"], order_rows)
    print("Generating order_items...")
    write_table("order_items", ["order_item_id", "order_id", "item_id", "quantity"], oi_rows)
    # Build session → payment method mapping for payment generation (both completed and failed)
    session_method_map = {s["session_id"]: s.get("payment_method", "") for s in completed_sessions}
    session_method_map.update({s["session_id"]: s.get("payment_method", "") for s in failed_sessions})
    return order_rows, oi_rows, user_lookup, session_method_map



# ---------------------------------------------------------------------------
# 6. payments — PK: payment_id — FK: order_id
#    NO user_id/platform/city — get via orders → users
# ---------------------------------------------------------------------------
def payment_method_for(platform: str) -> str:
    if platform == "android":
        return weighted_choice(["upi", "credit_card", "debit_card", "wallet", "cod"], [62, 10, 13, 10, 5])
    if platform == "ios":
        return weighted_choice(["upi", "credit_card", "debit_card", "wallet", "cod"], [53, 18, 12, 12, 5])
    return weighted_choice(["upi", "credit_card", "debit_card", "wallet", "cod"], [42, 25, 18, 5, 10])


def payment_outcome(current: datetime, platform: str, city: str, user_type: str, method: str) -> tuple[str, int, str]:
    phase = phase_for_date(current)
    is_primary = city_is_primary(city)
    is_upi = method == "upi"
    base_success = 0.95 if is_upi else 0.93
    timeout = 0.02

    if method == "cod":
        return "success", 0, ""

    if phase == "incident":
        if platform == "android" and is_primary and is_upi:
            base_success, timeout = 0.68, 0.18
        elif is_upi and is_primary:
            base_success, timeout = 0.79, 0.11
        elif is_upi:
            base_success, timeout = 0.86, 0.08
        # Non-UPI methods stay at baseline during incident — the migration only affects UPI
        # (previously 0.91 which was too close to baseline, making all methods look equally affected)
    elif phase == "partial_recovery":
        if platform == "android" and is_primary and is_upi:
            base_success, timeout = 0.84, 0.07
        elif is_upi:
            base_success, timeout = 0.89, 0.05
        else:
            base_success, timeout = 0.93, 0.03
    elif phase == "trust_damage":
        if platform == "android" and is_primary and is_upi:
            base_success, timeout = 0.90, 0.04

    roll = random.random()
    if roll < base_success:
        status, error = "success", ""
    elif roll < base_success + timeout:
        status = "timeout"
        error = random.choice(["UPI_CALLBACK_TIMEOUT", "BANK_TIMEOUT"])
    else:
        status = "failed"
        error = weighted_choice(
            ["PAYMENT_PROVIDER_ERROR", "UPI_COLLECT_PENDING", "TRANSACTION_REVERSED", "BANK_TIMEOUT"],
            [42, 28, 16, 14],
        )

    if phase == "incident":
        processing_time_ms = int(jitter(3500 if is_upi else 1200, 0.55))
    elif phase == "partial_recovery":
        processing_time_ms = int(jitter(1700 if is_upi else 900, 0.45))
    else:
        processing_time_ms = int(jitter(700 if is_upi else 850, 0.35))

    if user_type == "power" and phase == "trust_damage" and status == "success":
        processing_time_ms = int(processing_time_ms * 1.05)

    return status, max(0, processing_time_ms), error


def generate_payments(orders, user_lookup, session_method_map):
    """Generate payments. Uses pre-assigned payment methods from session_method_map
    so that payment method aligns with order status (UPI orders fail more during incident).
    """
    print("Generating payments...")
    rows = []
    for idx, order in enumerate(orders, start=1):
        order_id, user_id, _, _, session_id, order_status, amount, created_at_str = order
        current = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
        info = user_lookup[user_id]
        platform, city, user_type = info["platform"], info["city"], info["user_type"]
        # Use pre-assigned method if available (completed sessions), else generate new
        method = session_method_map.get(session_id) or payment_method_for(platform)
        if method == "cod":
            provider = "cash_on_delivery"
        else:
            provider = PROFILE["incident_profile"]["provider_v3"] if current >= MIGRATION_DATE else PROFILE["incident_profile"]["provider_v2"]

        status, processing_time_ms, error_code = payment_outcome(current, platform, city, user_type, method)

        # Align payment status with order status
        if order_status == "completed":
            status, error_code = "success", ""
        elif order_status == "failed":
            if method == "cod":
                status, error_code = "failed", ""
            elif status == "success":
                status = weighted_choice(["failed", "timeout"], [72, 28])
                error_code = "UPI_CALLBACK_TIMEOUT" if status == "timeout" else "PAYMENT_PROVIDER_ERROR"
        elif order_status == "cancelled":
            if method == "cod":
                status, error_code = "cancelled", ""
            elif status == "success":
                status = weighted_choice(["failed", "timeout"], [55, 45])
                error_code = "TRANSACTION_REVERSED" if status == "failed" else "UPI_COLLECT_PENDING"

        # NO user_id/platform/city — get via orders → users
        rows.append([
            f"PAY{idx:06d}", order_id, session_id, method, provider, status,
            amount, processing_time_ms, error_code, created_at_str,
        ])

    write_table(
        "payments",
        ["payment_id", "order_id", "session_id", "method", "provider", "status", "amount", "processing_time_ms", "error_code", "created_at"],
        rows,
    )
    return rows


# ---------------------------------------------------------------------------
# 7. drivers — PK: driver_id
# ---------------------------------------------------------------------------
def generate_drivers(n: int = 150):
    print("Generating drivers...")
    rows = []
    statuses = ["available", "on_delivery", "offline"]
    for i in range(1, n + 1):
        first = random.choice(PROFILE["first_names"])
        last = random.choice(PROFILE["last_names"])
        city = weighted_choice(CITIES, CITY_WEIGHTS)
        rows.append([f"D{i:04d}", f"{first} {last}", gen_phone(), city, weighted_choice(statuses, [44, 34, 22])])
    write_table("drivers", ["driver_id", "name", "phone", "city", "availability_status"], rows)
    return rows


# ---------------------------------------------------------------------------
# 8. funnel_events — PK: event_id — FK: user_id
#    Keeps platform (session-level device context). No city — JOIN to users.
# ---------------------------------------------------------------------------
def session_target_for(current: datetime) -> int:
    base = 900  # flat baseline across all months
    if current.weekday() in (5, 6):
        base = int(base * 1.10)
    if is_promo_period(current):
        base = int(base * 1.12)
    if phase_for_date(current) == "trust_damage":
        base = int(base * 0.91)
    return max(600, int(jitter(base, 0.04)))


def session_completion_prob(current: datetime, platform: str, city: str, user_type: str, method: str = "upi") -> float:
    """Probability that a session reaching payment_attempt completes to order_complete.

    This is the KEY function controlling the Jan 10 cliff. During the incident
    phase, UPI payments fail at much higher rates than other methods.
    """
    phase = phase_for_date(current)
    is_primary = city_is_primary(city)
    is_upi = method == "upi"

    if phase == "baseline":
        return 0.94

    if phase == "incident":
        if is_upi and platform == "android" and is_primary:
            return 0.53  # catastrophic — UPI callback broken
        if is_upi and is_primary:
            return 0.72  # bad — UPI degraded on iOS/web in primary metros
        if is_upi:
            return 0.82  # moderate — UPI in non-primary metros
        return 0.93  # non-UPI methods unaffected

    if phase == "partial_recovery":
        if is_upi and platform == "android" and is_primary:
            return 0.80
        if is_upi:
            return 0.89
        return 0.93

    # trust_damage phase
    if user_type in {"returning", "power"} and platform == "android" and is_primary:
        return 0.85  # behavioral avoidance persists
    return 0.91


def generate_funnel_events(users):
    """Generate funnel events and return completed sessions for order linkage.

    Every app open = new session. All sessions start at app_open and follow the
    same 6-step funnel. ~30% of sessions complete all steps (order_complete).
    Orders are a subset of sessions — one order per completed session.
    """
    print("Generating funnel_events...")
    rows = []
    completed_sessions = []  # Sessions that reached order_complete
    failed_sessions = []     # Sessions that reached payment_attempt but NOT order_complete
    users_by_platform = {p: [u for u in users if u[7] == p] for p in PLATFORMS}
    user_lookup = {u[0]: {"city": u[4], "user_type": u[8]} for u in users}
    event_id = 1
    session_id = 1
    current = START_DATE

    base_probs = [1.0, 0.77, 0.72, 0.69, 0.85, 0.94]
    steps = ["app_open", "restaurant_view", "add_to_cart", "checkout_start", "payment_attempt", "order_complete"]

    while current.date() <= END_DATE.date():
        phase = phase_for_date(current)
        platform_weights = PROFILE["platform_mix"][:]
        if phase == "trust_damage":
            platform_weights = [18, 56, 26]

        count = session_target_for(current)
        for _ in range(count):
            platform = weighted_choice(PLATFORMS, platform_weights)
            user = random.choice(users_by_platform[platform])
            user_id = user[0]
            city = user_lookup[user_id]["city"]
            user_type = user_lookup[user_id]["user_type"]

            if platform == "ios":
                device = random.choice(PROFILE["ios_devices"])
                app_version = "8.4.1" if current < MIGRATION_DATE else "8.4.2"
            elif platform == "android":
                device = random.choice(PROFILE["android_devices"])
                app_version = "8.4.1" if current < MIGRATION_DATE else "8.4.2"
            else:
                device = random.choice(PROFILE["web_devices"])
                app_version = "web_2025.01" if current < MIGRATION_DATE else "web_2025.02"

            # Assign payment method at session creation so completion prob is method-aware
            method = payment_method_for(platform)
            completion_prob = session_completion_prob(current, platform, city, user_type, method)
            probs = base_probs[:]
            probs[-1] = completion_prob
            # Hard problem: trust-damaged cohort browses less
            if phase == "trust_damage" and platform == "android" and city_is_primary(city) and user_type in {"returning", "power"}:
                probs[1] = 0.70  # restaurant_view: 70% vs 77% baseline
                probs[2] = 0.63  # add_to_cart: 63% vs 72% baseline

            timestamp = datetime.combine(current.date(), datetime.min.time()) + timedelta(
                hours=weighted_choice(list(range(24)), [1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 9, 8, 7, 5, 4, 5, 8, 10, 9, 7, 4, 2]),
                minutes=random.randint(0, 59), seconds=random.randint(0, 59),
            )

            session_id_str = f"S{session_id:07d}"
            reached_complete = False
            reached_payment = False
            for idx, step in enumerate(steps):
                if idx > 0 and random.random() > probs[idx]:
                    break
                timestamp += timedelta(seconds=random.randint(4, 55))
                rows.append([
                    f"E{event_id:07d}", user_id, session_id_str, step,
                    platform, device, app_version, timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                ])
                event_id += 1
                if step == "payment_attempt":
                    reached_payment = True
                if step == "order_complete":
                    reached_complete = True

            session_info = {
                "session_id": session_id_str,
                "user_id": user_id,
                "platform": platform,
                "city": city,
                "user_type": user_type,
                "payment_method": method,
                "timestamp": timestamp,
                "date": current,
            }
            if reached_complete:
                completed_sessions.append(session_info)
            elif reached_payment:
                failed_sessions.append(session_info)

            session_id += 1

        current += timedelta(days=1)

    write_table(
        "funnel_events",
        ["event_id", "user_id", "session_id", "event_type", "platform", "device", "app_version", "timestamp"],
        rows,
    )
    return rows, completed_sessions, failed_sessions


# ---------------------------------------------------------------------------
# 9. reviews — PK: review_id — FK: user_id, order_id — NO platform/city
# ---------------------------------------------------------------------------
def generate_reviews(orders):
    print("Generating reviews...")
    rows = []
    orders_by_window = defaultdict(list)
    for order in orders:
        dt = datetime.strptime(order[7], "%Y-%m-%d %H:%M:%S")
        if dt < MIGRATION_DATE:
            orders_by_window["pre"].append(order)
        elif dt < HOTFIX_DATE:
            orders_by_window["incident"].append(order)
        elif dt < TRUST_DAMAGE_DATE:
            orders_by_window["partial"].append(order)
        else:
            orders_by_window["trust"].append(order)

    review_texts = {
        "pre": [
            (5, "Delivery was quick and the biryani arrived piping hot. ZaikaNow has been super reliable lately."),
            (4, "Loved the breakfast combo from Anna Idli House. Easy checkout and fast delivery."),
            (5, "Great restaurant selection in Bengaluru. Ordering with UPI usually takes seconds."),
            (4, "Nice app. The cart flow is smooth and the offers are useful."),
            (4, "Consistent delivery experience. Will keep ordering from here."),
            (3, "Search feels a bit cluttered, but the order experience is solid overall."),
        ],
        "incident": [
            (1, "UPI got stuck on processing and the order never confirmed. Had to switch apps for dinner."),
            (2, "Money was debited from my bank app but ZaikaNow still showed payment failed."),
            (1, "Payment confirmation is broken on Android. Tried twice from Bengaluru and both attempts timed out."),
            (4, "Food was good but checkout felt slower than usual."),
            (2, "The app asked me to retry UPI three times. Very frustrating."),
        ],
        "partial": [
            (2, "UPI works sometimes now, but I still don't trust whether the order will confirm."),
            (1, "Still seeing callback timeout after paying through UPI. Support says wait 24 hours."),
            (3, "Managed to order after a retry. Better than last week, but not fixed."),
            (4, "Card payment worked fine today, but UPI is still flaky for me."),
        ],
        "trust": [
            (2, "Technical issue seems better, but I've started ordering less because I don't trust the payment flow."),
            (1, "Shifted most of my weekend orders to Swiggy after repeated UPI failures here."),
            (3, "App is faster now, but the earlier failed payments really damaged confidence."),
            (4, "Food quality is good, but ZaikaNow needs to win back trust after the January issues."),
            (2, "I only use ZaikaNow for specific restaurants now. For daily orders I switched to competitors."),
            (1, "Three failed payments in January and nobody proactively reached out. Lost a loyal customer."),
            (3, "My family used to order dinner every night. Now it's maybe twice a week. Trust is broken."),
        ],
    }

    # Variation suffixes to make repeated review templates unique
    _review_suffixes = [
        "",
        " Really disappointed.",
        " Not acceptable.",
        " Will think twice before ordering again.",
        " Hope they fix this soon.",
    ]

    review_id = 1
    for window, entries in review_texts.items():
        # Only completed orders can be reviewed (food was actually delivered)
        candidates = [o for o in orders_by_window.get(window, []) if o[5] == "completed"]
        if not candidates:
            continue
        repeats = 5 if window == "trust" else 4  # More trust-phase reviews
        for rep in range(repeats):
            for rating, text in entries:
                varied_text = text if rep == 0 else text.rstrip(".") + _review_suffixes[rep % len(_review_suffixes)]
                order = random.choice(candidates)
                order_dt = datetime.strptime(order[7], "%Y-%m-%d %H:%M:%S")
                created_at = order_dt + timedelta(hours=random.randint(1, 48))
                # NO platform/city — JOIN to users via order → user
                rows.append([f"REV{review_id:04d}", order[1], order[0], rating, varied_text, created_at.strftime("%Y-%m-%d %H:%M:%S")])
                review_id += 1

    rows.sort(key=lambda r: r[5])
    write_table("reviews", ["review_id", "user_id", "order_id", "rating", "text", "created_at"], rows)
    return rows


# ---------------------------------------------------------------------------
# 10. support_tickets — PK: ticket_id — FK: user_id, order_id — NO platform/city
# ---------------------------------------------------------------------------
def generate_support_tickets(users, orders):
    print("Generating support_tickets...")
    rows = []
    users_by_city = defaultdict(list)
    for u in users:
        users_by_city[u[4]].append(u)

    issue_templates = [
        ("payment", "upi_timeout", "UPI payment stayed on processing and then failed. I had already approved it in my bank app.", "critical"),
        ("payment", "money_debited", "Amount got debited but the order was not confirmed. Please reverse it urgently.", "critical"),
        ("checkout", "retry_missing", "After payment failed there was no proper retry flow. I had to rebuild the cart.", "high"),
        ("payment", "callback_delay", "UPI callback took too long and the order status never updated.", "high"),
        ("delivery", "late_delivery", "Delivery was very late today even though the app showed it was nearby.", "medium"),
        ("promo", "coupon_issue", "Republic Day coupon did not apply on checkout.", "low"),
        # Hard problem: trust concern tickets
        ("account", "trust_concern", "I want to export my order history. Considering moving to another platform after repeated payment failures.", "medium"),
        ("account", "trust_concern", "Can you confirm your refund policy? I had multiple failed payments in January and need assurance before ordering again.", "medium"),
    ]

    ticket_id = 1
    current = datetime(2024, 12, 20)
    while current <= END_DATE:
        phase = phase_for_date(current)
        if phase == "baseline":
            volume = 1 if random.random() < 0.4 else 0
        elif phase == "incident":
            volume = weighted_choice([2, 3, 4], [25, 50, 25])
        elif phase == "partial_recovery":
            volume = weighted_choice([1, 2, 3], [25, 50, 25])
        else:
            volume = weighted_choice([1, 2], [55, 45])

        for _ in range(volume):
            if phase in {"incident", "partial_recovery"} and random.random() < 0.7:
                city = weighted_choice(["bengaluru", "mumbai", "delhi_ncr"], [40, 35, 25])
                platform = weighted_choice(["android", "ios", "web"], [60, 25, 15])
                category, subcategory, description, priority = weighted_choice(issue_templates[:4], [34, 24, 20, 22])
            elif phase == "trust_damage" and random.random() < 0.35:
                # Hard problem: trust concern tickets appear in trust phase
                city = weighted_choice(["bengaluru", "mumbai", "delhi_ncr"], [40, 35, 25])
                platform = "android"
                category, subcategory, description, priority = random.choice(issue_templates[6:8])
            else:
                city = weighted_choice(CITIES, CITY_WEIGHTS)
                platform = weighted_choice(PLATFORMS, PROFILE["platform_mix"])
                # During baseline, only non-payment tickets (delivery, promo)
                if phase == "baseline":
                    baseline_templates = [t for t in issue_templates if t[0] in ("delivery", "promo")]
                    category, subcategory, description, priority = random.choice(baseline_templates)
                else:
                    category, subcategory, description, priority = random.choice(issue_templates[:6])

            possible_users = [u for u in users_by_city[city] if u[7] == platform] or users_by_city[city]
            user = random.choice(possible_users)
            created_at = current + timedelta(hours=random.randint(8, 22), minutes=random.randint(0, 59))
            status = weighted_choice(["open", "in_progress", "resolved"], [45, 35, 20]) if phase != "baseline" else weighted_choice(["resolved", "in_progress"], [80, 20])
            resolved_at = ""
            if status == "resolved":
                resolved_at = (created_at + timedelta(hours=random.randint(4, 36))).strftime("%Y-%m-%d %H:%M:%S")

            # Find a matching order for this user that was placed BEFORE this ticket
            created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            user_orders = [o for o in orders if o[1] == user[0] and o[7] <= created_at_str]
            order_id = random.choice(user_orders)[0] if user_orders else ""

            # NO platform/city — JOIN to users
            rows.append([
                f"TK{ticket_id:04d}", user[0], order_id, category, subcategory, description,
                priority, status, created_at.strftime("%Y-%m-%d %H:%M:%S"), resolved_at,
            ])
            ticket_id += 1
        current += timedelta(days=3)

    rows.sort(key=lambda r: r[8])
    write_table(
        "support_tickets",
        ["ticket_id", "user_id", "order_id", "category", "subcategory", "description", "priority", "status", "created_at", "resolved_at"],
        rows,
    )
    return rows


# ---------------------------------------------------------------------------
# 11. ux_changelog — platform stays (per-change, not per-user)
# ---------------------------------------------------------------------------
def generate_ux_changelog():
    print("Generating ux_changelog...")
    rows = [
        ["2024-12-18", "feature", "Added cuisine shortcuts for breakfast and biryani", "homepage", "all"],
        ["2024-12-20", "feature", "Christmas offer rail on the home feed", "homepage", "all"],
        ["2025-01-05", "ab_test", "Testing a denser cart summary layout", "cart", "all"],
        ["2025-01-08", "feature", "Updated restaurant ranking for repeat orders", "search", "all"],
        ["2025-01-10", "feature", "New payment success animation after confirmation", "checkout", "all"],
        ["2025-01-12", "bugfix", "Fixed checkout button alignment on smaller Android screens", "checkout", "android"],
        ["2025-01-20", "ab_test", "Testing simplified checkout review sheet", "checkout", "all"],
        ["2025-01-25", "feature", "Republic Day homepage banner", "homepage", "all"],
        ["2025-02-08", "bugfix", "Improved failed-payment copy on the review screen", "checkout", "all"],
    ]
    write_table("ux_changelog", ["date", "change_type", "description", "affected_area", "platform"], rows)


# ---------------------------------------------------------------------------
# 12. usability_study.md — Document
# ---------------------------------------------------------------------------
def generate_usability_study():
    print("Generating usability_study.md...")
    content = """# ZaikaNow Checkout & UPI Reliability Study

## Study Overview

**Type:** Moderated usability study
**Participants:** n=24
**Date:** January 22-28, 2025
**Objective:** Evaluate ordering and payment completion across Android, iOS, and web in major Indian metros

Participants were active ZaikaNow customers from Bengaluru, Mumbai, Delhi NCR, Hyderabad, and Pune. Most participants were frequent UPI users, reflecting the app's normal payment mix.

---

## Baseline Snapshot (November 2024)

| Metric | Baseline |
|--------|----------|
| Task completion rate | 93% |
| Avg payment confirmation time | 4.1s |
| Users reporting payment confusion | 2/18 |
| Users abandoning checkout | 2/18 |

---

## January Study Findings

| Metric | Baseline | January Study | Change |
|--------|----------|---------------|--------|
| Task completion rate | 93% | 61% | -32pp |
| Avg payment confirmation time | 4.1s | 13.9s | +239% |
| Users abandoning checkout | 2/18 | 10/24 | Significant increase |
| Users reporting trust loss after failed payment | 1/18 | 11/24 | Significant increase |

### Platform View

| Platform | Task Completion | Avg Confirmation Time | Common Failure Mode |
|----------|-----------------|-----------------------|---------------------|
| Android | 49% | 17.8s | UPI callback timeout |
| iOS | 72% | 9.3s | Delayed confirmation |
| Web | 81% | 6.1s | Retry confusion |

### Key Themes

1. **UPI approval happened, but the order stayed stuck**
   - Several Android participants approved the payment in their bank app but never received a clear confirmation in ZaikaNow.
2. **Money debited, order unclear**
   - Users were not sure whether they had been charged, reversed, or needed to retry.
3. **Retry guidance was weak**
   - The app did not clearly tell users whether to wait, retry, or choose another method.
4. **Trust damage persisted**
   - Even when later attempts worked, participants reported they were less willing to place future orders.

### Participant Quotes

> "I approved the UPI collect request, came back to the app, and it just kept spinning." — Participant 4, Bengaluru

> "If money has left my account, I should not have to guess whether lunch is actually coming." — Participant 11, Mumbai

> "After two failed payments I opened Zomato instead. I didn't want to risk it again." — Participant 17, Delhi NCR

### Recommendations

1. Improve UPI status messaging after approval.
2. Add explicit retry and fallback-method guidance.
3. Prioritize Android + UPI reliability in top metros.
4. Add post-failure reassurance for reversed or pending payments.
5. Track repeat-order drop among affected customers for recovery monitoring.
"""
    write_md("usability_study.md", content)


# ---------------------------------------------------------------------------
# 13. deployments — PK: deploy_id
# ---------------------------------------------------------------------------
def generate_deployments():
    print("Generating deployments...")
    rows = [
        ["DEP001", "catalog_service", "Expanded breakfast collections for metro cities", "ananya.iyer", "2024-12-18 09:45:00", "yes", gen_commit_hash()],
        ["DEP002", "notification_service", "New Year reminder campaign scheduler", "rahul.sharma", "2024-12-28 13:10:00", "yes", gen_commit_hash()],
        ["DEP003", "search_service", "Restaurant ranking refresh for repeat-order intent", "varun.reddy", "2025-01-08 07:30:00", "yes", gen_commit_hash()],
        ["DEP004", "payment_service", "Migrated to RupeeFlow v3 payment orchestration", "priya.nair", "2025-01-10 06:00:00", "yes", gen_commit_hash()],
        ["DEP005", "checkout_service", "Retry copy tweak on payment review screen", "meera.joshi", "2025-01-12 11:20:00", "yes", gen_commit_hash()],
        ["DEP006", "payment_service", "Hotfix: extended UPI callback timeout thresholds", "priya.nair", "2025-01-14 08:50:00", "yes", gen_commit_hash()],
        ["DEP007", "payment_service", "Partial retry handling for pending UPI confirmations", "priya.nair", "2025-02-01 10:15:00", "yes", gen_commit_hash()],
        ["DEP008", "catalog_service", "Republic Day specials banner and restaurant labels", "sakshi.bose", "2025-01-24 14:30:00", "yes", gen_commit_hash()],
        ["DEP009", "user_service", "Customer support reconciliation workflow", "aditya.menon", "2025-02-10 16:20:00", "yes", gen_commit_hash()],
    ]
    write_table("deployments", ["deploy_id", "service", "description", "author", "timestamp", "rollback_available", "commit_hash"], rows)


# ---------------------------------------------------------------------------
# 14. service_metrics — PK: (date, service)
# ---------------------------------------------------------------------------
def generate_service_metrics():
    print("Generating service_metrics...")
    services = {
        "payment_service": {"p50": 135, "p95": 310, "p99": 470, "error_rate": 0.4, "requests": 21000},
        "checkout_service": {"p50": 95, "p95": 210, "p99": 340, "error_rate": 0.12, "requests": 26000},
        "catalog_service": {"p50": 48, "p95": 122, "p99": 205, "error_rate": 0.06, "requests": 54000},
        "user_service": {"p50": 38, "p95": 86, "p99": 156, "error_rate": 0.09, "requests": 32000},
        "notification_service": {"p50": 52, "p95": 152, "p99": 248, "error_rate": 0.10, "requests": 12000},
        "search_service": {"p50": 62, "p95": 168, "p99": 290, "error_rate": 0.05, "requests": 43000},
    }

    rows = []
    current = START_DATE
    while current.date() <= END_DATE.date():
        for service, bl in services.items():
            p50, p95, p99 = bl["p50"], bl["p95"], bl["p99"]
            error_rate, requests = bl["error_rate"], bl["requests"]
            phase = phase_for_date(current)

            if service == "payment_service" and phase == "incident":
                days_after = (current - MIGRATION_DATE).days
                p50 = 240 + days_after * 12
                p95 = 900 + days_after * 70
                p99 = 2600 + days_after * 180
                error_rate = 3.4 + min(days_after, 12) * 0.18
                requests = 18500
            elif service == "payment_service" and phase == "partial_recovery":
                p50, p95, p99, error_rate, requests = 210, 680, 1800, 1.9, 19000
            elif service == "payment_service" and phase == "trust_damage":
                p50, p95, p99, error_rate, requests = 165, 470, 920, 0.9, 18200

            # Red herrings
            if service == "search_service" and current.date() == datetime(2025, 1, 8).date():
                p99 = 860
            if service == "notification_service" and datetime(2025, 1, 20).date() <= current.date() <= datetime(2025, 1, 22).date():
                error_rate = 0.8

            p50 = max(1, int(jitter(p50, 0.08)))
            p95 = max(p50 + 1, int(jitter(p95, 0.08)))
            p99 = max(p95 + 1, int(jitter(p99, 0.08)))
            error_rate = max(0.0, round(jitter(error_rate, 0.1), 2))
            requests = max(1000, int(jitter(requests, 0.06)))
            error_count = int(requests * error_rate / 100)

            rows.append([current.strftime("%Y-%m-%d"), service, p50, p95, p99, error_rate, error_count, requests])
        current += timedelta(days=1)

    write_table("service_metrics", ["date", "service", "p50_ms", "p95_ms", "p99_ms", "error_rate_pct", "error_count", "request_count"], rows)


# ---------------------------------------------------------------------------
# 15. error_log — PK: error_id — row-per-error detail log
# ---------------------------------------------------------------------------
def generate_error_log(payments, orders, user_lookup):
    """Generate a row-per-error log from payment failures + synthetic service errors."""
    print("Generating error_log...")
    rows = []
    error_id = 1

    # Build order lookup for user_id → platform
    order_map = {}
    for o in orders:
        order_map[o[0]] = {"user_id": o[1], "session_id": o[4]}

    # Payment errors: one row per failed/timeout payment
    # Payment row layout: [payment_id, order_id, session_id, method, provider, status, amount, processing_time_ms, error_code, created_at]
    for payment in payments:
        status = payment[5]
        error_code = payment[8]
        if status == "success" or not error_code:
            continue
        order_id = payment[1]
        session_id = payment[2]
        method = payment[3]
        created_at = payment[9]
        order_info = order_map.get(order_id, {})
        user_id = order_info.get("user_id", "")
        platform = user_lookup.get(user_id, {}).get("platform", "")
        severity = "critical" if status == "timeout" else "high"
        rows.append([
            f"ERR{error_id:06d}", created_at, session_id, order_id,
            "payment_service", error_code, method, platform, severity,
        ])
        error_id += 1

    # Non-payment service errors (red herrings from service_metrics)
    # search_service spike on Jan 8
    for _ in range(random.randint(35, 55)):
        ts = datetime(2025, 1, 8, random.randint(9, 17), random.randint(0, 59), random.randint(0, 59))
        platform = weighted_choice(PLATFORMS, PROFILE["platform_mix"])
        rows.append([
            f"ERR{error_id:06d}", ts.strftime("%Y-%m-%d %H:%M:%S"), "", "",
            "search_service", "SEARCH_INDEX_TIMEOUT", "", platform, "medium",
        ])
        error_id += 1

    # notification_service errors Jan 20-22
    for day in range(20, 23):
        for _ in range(random.randint(15, 30)):
            ts = datetime(2025, 1, day, random.randint(8, 22), random.randint(0, 59), random.randint(0, 59))
            platform = weighted_choice(PLATFORMS, PROFILE["platform_mix"])
            err = random.choice(["PUSH_DELIVERY_FAILED", "SMS_GATEWAY_TIMEOUT"])
            rows.append([
                f"ERR{error_id:06d}", ts.strftime("%Y-%m-%d %H:%M:%S"), "", "",
                "notification_service", err, "", platform, "low",
            ])
            error_id += 1

    rows.sort(key=lambda r: r[1])
    write_table(
        "error_log",
        ["error_id", "timestamp", "session_id", "order_id", "service", "error_code", "payment_method", "platform", "severity"],
        rows,
    )


# ---------------------------------------------------------------------------
# 16. system_architecture.md — Document
# ---------------------------------------------------------------------------
def generate_system_architecture():
    print("Generating system_architecture.md...")
    content = """# ZaikaNow System Architecture

## Overview

ZaikaNow is an India-native food delivery marketplace serving major metros such as Bengaluru, Mumbai, Delhi NCR, Hyderabad, Pune, and Chennai.

The platform runs on a microservice architecture in AWS ap-south-1 (Mumbai), with PostgreSQL, Redis, and external payment integrations.

## Core Services

### Catalog Service
- Manages restaurants, menus, cuisine rails, and city-specific discovery collections.

### Search Service
- Powers search, ranking, and repeat-order recommendations.

### User Service
- Handles authentication, profiles, addresses, and customer support linkage.

### Checkout Service
- Owns cart state, order creation, and payment orchestration.

### Payment Service
- Manages online payments across UPI, cards, wallets, and COD reconciliation.
- Recently migrated from RupeeFlow v2 to RupeeFlow v3 on January 10, 2025.

### Notification Service
- Sends order updates, payment alerts, and support-related notifications.

## Payment Path

1. Customer taps `Place Order`
2. Checkout Service creates the order intent
3. Payment Service creates a RupeeFlow transaction
4. Customer approves UPI in their banking app or wallet flow
5. RupeeFlow sends async confirmation callback
6. ZaikaNow confirms the order and notifies the customer

## Failure Pattern Under Investigation

- After the RupeeFlow v3 migration, callback confirmation became unreliable for a subset of UPI flows
- Android users in high-volume metros were hit hardest
- Some users saw money debited or approval completed, but order confirmation never resolved cleanly

## Infra Notes

- Primary AWS location: ap-south-1 (Mumbai)
- Databases: PostgreSQL (Multi-AZ), Redis for cache and queue coordination
- Monitoring: Datadog dashboards and alerting
- Logs: CloudWatch and centralized error aggregation
"""
    write_md("system_architecture.md", content)


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    global CONN
    print("=" * 60)
    print("ZaikaNow Scenario Data Generator")
    print("Checkout Conversion Drop — 3 Embedded Problems")
    print("=" * 60)
    print(f"Output database: {DB_PATH}")
    print(f"Date range: {START_DATE.date()} to {END_DATE.date()}")
    print()

    CONN = reset_database()

    users = generate_users()
    restaurants = generate_restaurants()
    menu_items, restaurant_menu_map = generate_menu_items(restaurants)
    drivers = generate_drivers()
    _, completed_sessions, failed_sessions = generate_funnel_events(users)
    orders, order_items, user_lookup, session_method_map = generate_orders(users, restaurants, restaurant_menu_map, menu_items, drivers, completed_sessions, failed_sessions)
    payments = generate_payments(orders, user_lookup, session_method_map)
    generate_reviews(orders)
    generate_support_tickets(users, orders)
    generate_usability_study()
    generate_ux_changelog()
    generate_deployments()
    generate_service_metrics()
    generate_system_architecture()
    generate_error_log(payments, orders, user_lookup)

    if CONN is not None:
        CONN.close()
        CONN = None

    print()
    print("=" * 60)
    print("Data generation complete!")
    print(f"All data written to: {DB_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
