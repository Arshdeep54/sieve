"""Write a synthetic users CSV for load tests: python scripts/gen_users.py data/users-1m.csv 1000000"""

import csv
import random
import sys
import uuid
from pathlib import Path

FIRST_NAMES = [
    "Aarav",
    "Diya",
    "Dhruv",
    "Ishaan",
    "Kavya",
    "Meera",
    "Nikhil",
    "Riya",
    "Tara",
    "Vihaan",
    "Zoya",
    "Arjun",
]
LAST_NAMES = [
    "Iyengar",
    "Khan",
    "Sharma",
    "Patel",
    "Reddy",
    "Nair",
    "Gupta",
    "Singh",
    "Das",
    "Mehta",
    "Rao",
    "Bose",
]
EMPLOYMENT = ["Salaried", "Salaried", "Salaried", "Self-Employed", "Business"]


def write_users(path: Path, count: int) -> None:
    """Write count users with a fixed seed so load tests are repeatable."""
    rng = random.Random(7)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "user_id",
                "name",
                "email",
                "monthly_income",
                "credit_score",
                "employment_status",
                "age",
            ]
        )
        for index in range(count):
            first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            writer.writerow(
                [
                    uuid.UUID(int=rng.getrandbits(128), version=4),
                    f"{first} {last}",
                    f"{first}.{last}.{index}@example.com".lower(),
                    rng.randrange(15_000, 400_000, 1_000),
                    min(900, max(300, round(rng.gauss(720, 60)))),
                    rng.choice(EMPLOYMENT),
                    rng.randint(21, 62),
                ]
            )


if __name__ == "__main__":
    write_users(Path(sys.argv[1]), int(sys.argv[2]))
