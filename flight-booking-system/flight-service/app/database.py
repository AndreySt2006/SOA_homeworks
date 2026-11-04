from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flight:flightpass@localhost:5434/flightdb")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from .models import Base
    Base.metadata.create_all(bind=engine)
    print("Migrations applied (create_all)")
    # Seed some data if empty
    from .models import Flight, FlightStatus
    from datetime import datetime, timedelta
    db = SessionLocal()
    if db.query(Flight).count() == 0:
        flights = [
            Flight(
                flight_number="SU1234",
                airline="Aeroflot",
                origin="SVO",
                destination="LED",
                departure_time=datetime(2026, 4, 1, 10, 0),
                arrival_time=datetime(2026, 4, 1, 11, 30),
                total_seats=180,
                available_seats=150,
                price=5000.0,
                status=FlightStatus.SCHEDULED
            ),
            Flight(
                flight_number="SU5678",
                airline="Aeroflot",
                origin="SVO",
                destination="LED",
                departure_time=datetime(2026, 4, 2, 14, 0),
                arrival_time=datetime(2026, 4, 2, 15, 30),
                total_seats=160,
                available_seats=100,
                price=4500.0,
                status=FlightStatus.SCHEDULED
            )
        ]
        db.add_all(flights)
        db.commit()
        print("Seeded sample flights")
    db.close()
