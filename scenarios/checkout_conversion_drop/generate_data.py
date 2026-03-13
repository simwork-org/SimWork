#!/usr/bin/env python3
"""
Generate India-native scenario data for SimWork's checkout conversion drop case.

Scenario:
- Company: ZaikaNow, a fictional India food-delivery marketplace
- Challenge: order softness after a gateway migration
- Root cause: RupeeFlow v3 migration on Jan 10, 2025 degraded UPI confirmation flows,
  strongest on Android users in high-volume metros
"""

from __future__ import annotations

import csv
import hashlib
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta

random.seed(42)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLES_DIR = os.path.join(SCRIPT_DIR, "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

START_DATE = datetime(2024, 7, 1)
END_DATE = datetime(2025, 3, 31, 23, 59, 59)
MIGRATION_DATE = datetime(2025, 1, 10)
HOTFIX_DATE = datetime(2025, 2, 1)
TRUST_DAMAGE_DATE = datetime(2025, 2, 16)

MARKET_PROFILES = {
    "india_food_delivery": {
        "brand_name": "ZaikaNow",
        "country": "India",
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
        "platform_mix": [18, 62, 20],  # ios, android, web
        "platforms": ["ios", "android", "web"],
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
}

PROFILE = MARKET_PROFILES["india_food_delivery"]
PLATFORMS = PROFILE["platforms"]
CITIES = [city for city, _, _ in PROFILE["cities"]]
CITY_WEIGHTS = [weight for _, weight, _ in PROFILE["cities"]]
CITY_AREAS = {city: areas for city, _, areas in PROFILE["cities"]}
USER_TYPES = PROFILE["user_types"]


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


def write_csv(filename: str, headers: list[str], rows: list[list[object]]) -> None:
    path = os.path.join(TABLES_DIR, filename)
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"  -> {filename}: {len(rows)} rows")


def write_md(filename: str, content: str) -> None:
    path = os.path.join(TABLES_DIR, filename)
    with open(path, "w") as handle:
        handle.write(content)
    print(f"  -> {filename}: written")


def phase_for_date(current: datetime) -> str:
    if current < MIGRATION_DATE:
        return "baseline"
    if current < HOTFIX_DATE:
        return "incident"
    if current < TRUST_DAMAGE_DATE:
        return "partial_recovery"
    return "trust_damage"


def city_is_primary(city: str) -> bool:
    return city in PROFILE["incident_profile"]["primary_cities"]


def generate_users(n: int = 6500):
    print("Generating users.csv...")
    rows = []
    for i in range(1, n + 1):
        user_id = f"U{i:05d}"
        first = random.choice(PROFILE["first_names"])
        last = random.choice(PROFILE["last_names"])
        city = weighted_choice(CITIES, CITY_WEIGHTS)
        platform = weighted_choice(PLATFORMS, PROFILE["platform_mix"])
        user_type = weighted_choice(USER_TYPES, PROFILE["user_type_mix"])
        signup = random_datetime(datetime(2023, 1, 1), datetime(2025, 3, 20)).strftime("%Y-%m-%d")
        email = f"{sanitize_token(first)}.{sanitize_token(last)}{i}@{PROFILE['email_domain']}"
        rows.append([user_id, f"{first} {last}", email, gen_phone(), signup, platform, city, user_type])
    write_csv("users.csv", ["user_id", "name", "email", "phone", "signup_date", "platform", "city", "user_type"], rows)
    return rows


def generate_restaurants(users):
    print("Generating restaurants.csv...")
    rows = []
    restaurant_id = 1
    for city in CITIES:
        for cuisine, details in PROFILE["restaurant_taxonomy"].items():
            names = details["names"]
            for name in random.sample(names, min(2, len(names))):
                area = random.choice(CITY_AREAS[city])
                address = f"Shop {random.randint(3, 220)}, {area}, {city.replace('_', ' ').title()}"
                owner_id = random.choice(users)[0]
                rating = round(random.uniform(3.7, 4.8), 1)
                rows.append([f"R{restaurant_id:04d}", name, cuisine, address, rating, owner_id])
                restaurant_id += 1
    write_csv("restaurants.csv", ["restaurant_id", "name", "cuisine_type", "address", "rating", "owner_id"], rows)
    return rows


def generate_menu_items(restaurants):
    print("Generating menu_items.csv...")
    rows = []
    item_id = 1
    restaurant_menu_map = {}
    cuisine_map = PROFILE["restaurant_taxonomy"]
    for restaurant in restaurants:
        restaurant_id = restaurant[0]
        cuisine = restaurant[2]
        menu_items = cuisine_map[cuisine]["menu"]
        sampled = random.sample(menu_items, min(len(menu_items), random.randint(4, 5)))
        ids = []
        for name, description, price in sampled:
            ids.append(f"MI{item_id:05d}")
            rows.append([f"MI{item_id:05d}", restaurant_id, name, description, price])
            item_id += 1
        restaurant_menu_map[restaurant_id] = ids
    write_csv("menu_items.csv", ["item_id", "restaurant_id", "name", "description", "price"], rows)
    return rows, restaurant_menu_map


def daily_order_target(current: datetime) -> int:
    base_by_month = {
        7: 300, 8: 315, 9: 325, 10: 340, 11: 355, 12: 390,
        1: 365, 2: 330, 3: 345,
    }
    base = base_by_month[current.month]
    if current.weekday() in (5, 6):
        base = int(base * 1.12)
    if datetime(2024, 12, 26).date() <= current.date() <= datetime(2025, 1, 5).date():
        base = int(base * 1.18)
    if datetime(2025, 1, 24).date() <= current.date() <= datetime(2025, 1, 26).date():
        base = int(base * 1.08)
    if phase_for_date(current) == "trust_damage":
        base = int(base * 0.95)
    return max(180, int(jitter(base, 0.08)))


def order_status_probs(current: datetime, platform: str, city: str, user_type: str) -> tuple[float, float]:
    phase = phase_for_date(current)
    fail_rate = 0.04
    cancel_rate = 0.11

    is_primary = city_is_primary(city)
    if phase == "incident":
        if platform == "android" and is_primary:
            fail_rate = 0.17
            cancel_rate = 0.16
        elif platform == "ios" and is_primary:
            fail_rate = 0.09
            cancel_rate = 0.13
        elif platform == "web" and is_primary:
            fail_rate = 0.07
            cancel_rate = 0.12
        else:
            fail_rate = 0.06
            cancel_rate = 0.12
    elif phase == "partial_recovery":
        if platform == "android" and is_primary:
            fail_rate = 0.09
            cancel_rate = 0.13
        else:
            fail_rate = 0.05
            cancel_rate = 0.11
    elif phase == "trust_damage":
        fail_rate = 0.05
        cancel_rate = 0.10
        if user_type in {"returning", "power"} and platform == "android" and is_primary:
            cancel_rate = 0.12

    return fail_rate, cancel_rate


def generate_orders(users, restaurants, restaurant_menu_map):
    print("Generating orders.csv...")
    user_lookup = {user[0]: {"platform": user[5], "city": user[6], "user_type": user[7]} for user in users}
    users_by_platform = {platform: [user for user in users if user[5] == platform] for platform in PLATFORMS}
    restaurant_ids = [restaurant[0] for restaurant in restaurants]

    rows = []
    order_id = 1
    current = START_DATE
    while current.date() <= END_DATE.date():
        order_count = daily_order_target(current)
        for _ in range(order_count):
            phase = phase_for_date(current)
            platform_weights = PROFILE["platform_mix"][:]
            if phase == "trust_damage":
                platform_weights = [18, 58, 24]
            platform = weighted_choice(PLATFORMS, platform_weights)
            user = random.choice(users_by_platform[platform])
            user_id = user[0]
            city = user[6]
            user_type = user[7]
            fail_rate, cancel_rate = order_status_probs(current, platform, city, user_type)

            r = random.random()
            if r < fail_rate:
                status = "failed"
            elif r < fail_rate + cancel_rate:
                status = "cancelled"
            else:
                status = "completed"

            restaurant_id = random.choice(restaurant_ids)
            total_amount = round(random.uniform(149, 849), 2)
            hour = weighted_choice(
                list(range(24)),
                [1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 9, 8, 7, 5, 4, 5, 8, 10, 9, 7, 4, 2],
            )
            created_at = datetime.combine(current.date(), datetime.min.time()) + timedelta(
                hours=hour,
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59),
            )
            rows.append([
                f"ORD{order_id:06d}",
                user_id,
                restaurant_id,
                status,
                f"{total_amount:.2f}",
                platform,
                city,
                created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])
            order_id += 1
        current += timedelta(days=1)

    write_csv(
        "orders.csv",
        ["order_id", "user_id", "restaurant_id", "order_status", "total_amount", "platform", "city", "created_at"],
        rows,
    )
    return rows, user_lookup


def generate_order_items(orders, restaurant_menu_map):
    print("Generating order_items.csv...")
    rows = []
    order_item_id = 1
    for order in orders:
        restaurant_id = order[2]
        menu_ids = restaurant_menu_map.get(restaurant_id, [])
        for item_id in random.choices(menu_ids, k=weighted_choice([1, 2, 3, 4], [15, 42, 31, 12])):
            quantity = weighted_choice([1, 2, 3], [72, 23, 5])
            rows.append([f"OI{order_item_id:06d}", order[0], item_id, quantity])
            order_item_id += 1
    write_csv("order_items.csv", ["order_item_id", "order_id", "item_id", "quantity"], rows)
    return rows


def generate_drivers(n: int = 260):
    print("Generating drivers.csv...")
    rows = []
    statuses = ["available", "on_delivery", "offline"]
    for i in range(1, n + 1):
        first = random.choice(PROFILE["first_names"])
        last = random.choice(PROFILE["last_names"])
        city = weighted_choice(CITIES, CITY_WEIGHTS)
        rows.append([f"D{i:04d}", f"{first} {last}", gen_phone(), city, weighted_choice(statuses, [44, 34, 22])])
    write_csv("drivers.csv", ["driver_id", "name", "phone", "city", "availability_status"], rows)
    return rows


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
    reversed_rate = 0.01

    if method == "cod":
        return "success", 0, ""

    if phase == "incident":
        if platform == "android" and is_primary and is_upi:
            base_success = 0.68
            timeout = 0.18
            reversed_rate = 0.05
        elif is_upi and is_primary:
            base_success = 0.79
            timeout = 0.11
            reversed_rate = 0.03
        elif is_upi:
            base_success = 0.86
            timeout = 0.08
            reversed_rate = 0.02
        else:
            base_success = 0.91
            timeout = 0.04
    elif phase == "partial_recovery":
        if platform == "android" and is_primary and is_upi:
            base_success = 0.84
            timeout = 0.07
            reversed_rate = 0.02
        elif is_upi:
            base_success = 0.89
            timeout = 0.05
        else:
            base_success = 0.93
            timeout = 0.03
    elif phase == "trust_damage":
        if platform == "android" and is_primary and is_upi:
            base_success = 0.90
            timeout = 0.04
            reversed_rate = 0.015

    roll = random.random()
    if roll < base_success:
        status = "success"
        error = ""
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


def generate_payments(orders, user_lookup):
    print("Generating payments.csv...")
    rows = []
    for index, order in enumerate(orders, start=1):
        order_id, user_id, _, order_status, amount, platform, city, created_at = order
        current = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        user_type = user_lookup[user_id]["user_type"]
        phase = phase_for_date(current)
        method = payment_method_for(platform)
        if method == "cod":
            provider = "cash_on_delivery"
        else:
            provider = PROFILE["incident_profile"]["provider_v3"] if current >= MIGRATION_DATE else PROFILE["incident_profile"]["provider_v2"]

        status, processing_time_ms, error_code = payment_outcome(current, platform, city, user_type, method)

        if order_status == "completed":
            status = "success"
            error_code = ""
        elif order_status == "failed" and status == "success" and method != "cod":
            status = weighted_choice(["failed", "timeout"], [72, 28])
            error_code = "UPI_CALLBACK_TIMEOUT" if status == "timeout" else "PAYMENT_PROVIDER_ERROR"
        elif order_status == "cancelled" and method != "cod" and status == "success" and phase != "baseline":
            status = weighted_choice(["failed", "timeout"], [55, 45])
            error_code = "TRANSACTION_REVERSED" if status == "failed" else "UPI_COLLECT_PENDING"

        rows.append([
            f"PAY{index:06d}",
            order_id,
            user_id,
            method,
            provider,
            status,
            amount,
            processing_time_ms,
            error_code,
            platform,
            city,
            created_at,
        ])

    write_csv(
        "payments.csv",
        ["payment_id", "order_id", "user_id", "method", "provider", "status", "amount", "processing_time_ms", "error_code", "platform", "city", "created_at"],
        rows,
    )
    return rows


def session_target_for(current: datetime) -> int:
    base = {7: 250, 8: 260, 9: 270, 10: 285, 11: 295, 12: 330, 1: 320, 2: 295, 3: 305}[current.month]
    if current.weekday() in (5, 6):
        base = int(base * 1.1)
    if datetime(2024, 12, 26).date() <= current.date() <= datetime(2025, 1, 5).date():
        base = int(base * 1.14)
    if phase_for_date(current) == "trust_damage":
        base = int(base * 0.94)
    return max(160, int(jitter(base, 0.07)))


def session_completion_prob(current: datetime, platform: str, city: str, user_type: str) -> float:
    phase = phase_for_date(current)
    is_primary = city_is_primary(city)
    prob = 0.94
    if phase == "incident":
        if platform == "android" and is_primary:
            prob = 0.63
        elif platform == "ios" and is_primary:
            prob = 0.78
        elif platform == "web" and is_primary:
            prob = 0.84
        else:
            prob = 0.87
    elif phase == "partial_recovery":
        if platform == "android" and is_primary:
            prob = 0.80
        else:
            prob = 0.89
    elif phase == "trust_damage":
        prob = 0.91
        if user_type in {"returning", "power"} and platform == "android" and is_primary:
            prob = 0.88
    return prob


def generate_session_events(users, orders):
    print("Generating sessions_events.csv...")
    rows = []
    users_by_platform = {platform: [user for user in users if user[5] == platform] for platform in PLATFORMS}
    event_id = 1
    session_id = 1
    current = START_DATE

    base_probs = [1.0, 0.77, 0.72, 0.69, 0.85, 0.94]
    steps = ["app_open", "restaurant_view", "add_to_cart", "checkout_start", "payment_attempt", "order_complete"]

    while current.date() <= END_DATE.date():
        session_count = session_target_for(current)
        for _ in range(session_count):
            platform_weights = PROFILE["platform_mix"][:]
            if phase_for_date(current) == "trust_damage":
                platform_weights = [18, 58, 24]
            platform = weighted_choice(PLATFORMS, platform_weights)
            user = random.choice(users_by_platform[platform])
            user_id, city, user_type = user[0], user[6], user[7]
            if platform == "ios":
                device = random.choice(PROFILE["ios_devices"])
                app_version = "8.4.1" if current < MIGRATION_DATE else "8.4.2"
            elif platform == "android":
                device = random.choice(PROFILE["android_devices"])
                app_version = "8.4.1" if current < MIGRATION_DATE else "8.4.2"
            else:
                device = random.choice(PROFILE["web_devices"])
                app_version = "web_2025.01" if current < MIGRATION_DATE else "web_2025.02"

            completion_prob = session_completion_prob(current, platform, city, user_type)
            probs = base_probs[:]
            probs[-1] = completion_prob
            if phase_for_date(current) == "trust_damage" and platform == "android" and city_is_primary(city) and user_type in {"returning", "power"}:
                probs[1] = 0.73
                probs[2] = 0.67

            timestamp = datetime.combine(current.date(), datetime.min.time()) + timedelta(
                hours=weighted_choice(list(range(24)), [1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 9, 8, 7, 5, 4, 5, 8, 10, 9, 7, 4, 2]),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59),
            )

            for idx, step in enumerate(steps):
                if idx > 0 and random.random() > probs[idx]:
                    break
                timestamp += timedelta(seconds=random.randint(4, 55))
                rows.append([
                    f"E{event_id:07d}",
                    user_id,
                    f"S{session_id:07d}",
                    step,
                    platform,
                    city,
                    device,
                    app_version,
                    timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                ])
                event_id += 1
            session_id += 1
        current += timedelta(days=1)

    write_csv(
        "sessions_events.csv",
        ["event_id", "user_id", "session_id", "event_type", "platform", "city", "device", "app_version", "timestamp"],
        rows,
    )
    return rows


def generate_reviews(users, orders):
    print("Generating reviews.csv...")
    rows = []

    orders_by_window = defaultdict(list)
    for order in orders:
        order_dt = datetime.strptime(order[7], "%Y-%m-%d %H:%M:%S")
        if order_dt < MIGRATION_DATE:
            orders_by_window["pre"].append(order)
        elif order_dt < HOTFIX_DATE:
            orders_by_window["incident"].append(order)
        elif order_dt < TRUST_DAMAGE_DATE:
            orders_by_window["partial"].append(order)
        else:
            orders_by_window["trust"].append(order)

    def add_review(review_id: int, order, rating: int, text: str, created_at: datetime):
        rows.append([f"REV{review_id:04d}", order[1], order[0], rating, text, order[5], order[6], created_at.strftime("%Y-%m-%d %H:%M:%S")])

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
            (2, "UPI works sometimes now, but I still don’t trust whether the order will confirm."),
            (1, "Still seeing callback timeout after paying through UPI. Support says wait 24 hours."),
            (3, "Managed to order after a retry. Better than last week, but not fixed."),
            (4, "Card payment worked fine today, but UPI is still flaky for me."),
        ],
        "trust": [
            (2, "Technical issue seems better, but I’ve started ordering less because I don’t trust the payment flow."),
            (1, "Shifted most of my weekend orders to Swiggy after repeated UPI failures here."),
            (3, "App is faster now, but the earlier failed payments really damaged confidence."),
            (4, "Food quality is good, but ZaikaNow needs to win back trust after the January issues."),
        ],
    }

    review_id = 1
    for window, entries in review_texts.items():
        candidates = orders_by_window[window]
        if not candidates:
            continue
        for rating, text in entries * 4:
            order = random.choice(candidates)
            order_dt = datetime.strptime(order[7], "%Y-%m-%d %H:%M:%S")
            add_review(review_id, order, rating, text, order_dt + timedelta(hours=random.randint(1, 48)))
            review_id += 1

    rows.sort(key=lambda row: row[7])
    write_csv("reviews.csv", ["review_id", "user_id", "order_id", "rating", "text", "platform", "city", "created_at"], rows)
    return rows


def generate_support_tickets(users, orders):
    print("Generating support_tickets.csv...")
    rows = []
    users_by_city = defaultdict(list)
    for user in users:
        users_by_city[user[6]].append(user)

    issue_templates = [
        ("payment", "upi_timeout", "UPI payment stayed on processing and then failed. I had already approved it in my bank app.", "critical"),
        ("payment", "money_debited", "Amount got debited but the order was not confirmed. Please reverse it urgently.", "critical"),
        ("checkout", "retry_missing", "After payment failed there was no proper retry flow. I had to rebuild the cart.", "high"),
        ("payment", "callback_delay", "UPI callback took too long and the order status never updated.", "high"),
        ("delivery", "late_delivery", "Delivery was very late today even though the app showed it was nearby.", "medium"),
        ("promo", "coupon_issue", "Republic Day coupon did not apply on checkout.", "low"),
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
            volume = weighted_choice([1, 2], [65, 35])

        for _ in range(volume):
            if phase in {"incident", "partial_recovery", "trust_damage"} and random.random() < 0.7:
                city = weighted_choice(["bengaluru", "mumbai", "delhi_ncr"], [40, 35, 25])
                platform = weighted_choice(["android", "ios", "web"], [60, 25, 15])
                category, subcategory, description, priority = weighted_choice(
                    issue_templates[:4],
                    [34, 24, 20, 22],
                )
            else:
                city = weighted_choice(CITIES, CITY_WEIGHTS)
                platform = weighted_choice(PLATFORMS, PROFILE["platform_mix"])
                category, subcategory, description, priority = random.choice(issue_templates)

            possible_users = [user for user in users_by_city[city] if user[5] == platform] or users_by_city[city]
            user = random.choice(possible_users)
            created_at = current + timedelta(hours=random.randint(8, 22), minutes=random.randint(0, 59))
            status = weighted_choice(["open", "in_progress", "resolved"], [45, 35, 20]) if phase != "baseline" else weighted_choice(["resolved", "in_progress"], [80, 20])
            resolved_at = ""
            if status == "resolved":
                resolved_at = (created_at + timedelta(hours=random.randint(4, 36))).strftime("%Y-%m-%d %H:%M:%S")
            rows.append([
                f"TK{ticket_id:04d}",
                user[0],
                category,
                subcategory,
                description,
                platform,
                city,
                priority,
                status,
                created_at.strftime("%Y-%m-%d %H:%M:%S"),
                resolved_at,
            ])
            ticket_id += 1
        current += timedelta(days=3)

    rows.sort(key=lambda row: row[9])
    write_csv(
        "support_tickets.csv",
        ["ticket_id", "user_id", "category", "subcategory", "description", "platform", "city", "priority", "status", "created_at", "resolved_at"],
        rows,
    )
    return rows


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


def generate_ux_changelog():
    print("Generating ux_changelog.csv...")
    rows = [
        ["2024-12-18", "feature", "Added cuisine shortcuts for breakfast and biryani", "homepage", "all"],
        ["2024-12-27", "feature", "New Year offer rail on the home feed", "homepage", "all"],
        ["2025-01-05", "ab_test", "Testing a denser cart summary layout", "cart", "all"],
        ["2025-01-08", "feature", "Updated restaurant ranking for repeat orders", "search", "all"],
        ["2025-01-10", "feature", "New payment success animation after confirmation", "checkout", "all"],
        ["2025-01-12", "bugfix", "Fixed checkout button alignment on smaller Android screens", "checkout", "android"],
        ["2025-01-20", "ab_test", "Testing simplified checkout review sheet", "checkout", "all"],
        ["2025-01-25", "feature", "Republic Day specials collection", "homepage", "all"],
        ["2025-02-08", "bugfix", "Improved failed-payment copy on the review screen", "checkout", "all"],
    ]
    write_csv("ux_changelog.csv", ["date", "change_type", "description", "affected_area", "platform"], rows)


def generate_deployments():
    print("Generating deployments.csv...")
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
    write_csv("deployments.csv", ["deploy_id", "service", "description", "author", "timestamp", "rollback_available", "commit_hash"], rows)


def generate_service_metrics():
    print("Generating service_metrics.csv...")
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
        for service, baseline in services.items():
            p50 = baseline["p50"]
            p95 = baseline["p95"]
            p99 = baseline["p99"]
            error_rate = baseline["error_rate"]
            requests = baseline["requests"]
            phase = phase_for_date(current)

            if service == "payment_service" and phase == "incident":
                days_after = (current - MIGRATION_DATE).days
                p50 = 240 + days_after * 12
                p95 = 900 + days_after * 70
                p99 = 2600 + days_after * 180
                error_rate = 3.4 + min(days_after, 12) * 0.18
                requests = 18500
            elif service == "payment_service" and phase == "partial_recovery":
                p50 = 210
                p95 = 680
                p99 = 1800
                error_rate = 1.9
                requests = 19000
            elif service == "payment_service" and phase == "trust_damage":
                p50 = 165
                p95 = 470
                p99 = 920
                error_rate = 0.9
                requests = 18200

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

    write_csv(
        "service_metrics.csv",
        ["date", "service", "p50_ms", "p95_ms", "p99_ms", "error_rate_pct", "error_count", "request_count"],
        rows,
    )


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


def generate_payment_errors_summary(payments):
    print("Generating payment_errors_summary.csv...")
    summary = defaultdict(int)
    for payment in payments:
        status = payment[5]
        error_code = payment[8]
        if status == "success" or not error_code:
            continue
        date = payment[11][:10]
        platform = payment[9]
        summary[(date, error_code, platform)] += 1

    rows = [[date, error_code, count, platform] for (date, error_code, platform), count in sorted(summary.items())]
    write_csv("payment_errors_summary.csv", ["date", "error_code", "count", "platform"], rows)


def main():
    print("=" * 60)
    print("ZaikaNow Scenario Data Generator")
    print("Checkout Conversion Drop - RupeeFlow v3 Migration")
    print("=" * 60)
    print(f"Output directory: {TABLES_DIR}")
    print()

    users = generate_users()
    restaurants = generate_restaurants(users)
    _, restaurant_menu_map = generate_menu_items(restaurants)
    orders, user_lookup = generate_orders(users, restaurants, restaurant_menu_map)
    generate_order_items(orders, restaurant_menu_map)
    generate_drivers()
    payments = generate_payments(orders, user_lookup)
    generate_session_events(users, orders)
    generate_reviews(users, orders)
    generate_support_tickets(users, orders)
    generate_usability_study()
    generate_ux_changelog()
    generate_deployments()
    generate_service_metrics()
    generate_system_architecture()
    generate_payment_errors_summary(payments)

    print()
    print("=" * 60)
    print("Data generation complete!")
    print(f"All files written to: {TABLES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
