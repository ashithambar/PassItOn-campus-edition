from app import create_app
from app.migrations import upgrade_schema
from app.models import Category, User, db

app = create_app()

CATEGORIES = [
    ("Books", "books", "bi-book", "Textbooks, reference guides, semester notes, entrance prep, fiction & non-fiction."),
    ("Electronics", "electronics", "bi-laptop", "Laptops, monitors, headphones, keyboards, mice, adapters, chargers."),
    ("Calculators", "calculators", "bi-calculator", "Scientific calculators, programmable & graphing calculators for engineering & math."),
    ("Stationery", "stationery", "bi-pencil-square", "Notebooks, sketchbooks, geometry boxes, technical pens, markers."),
    ("Lab Equipment", "lab-equipment", "bi-eyedropper", "Lab coats, safety goggles, breadboards, multimeters, dissecting kits."),
    ("Furniture", "furniture", "bi-lamp", "Hostel study tables, ergonomic chairs, bed tables, desk organizers."),
    ("Clothing", "clothing", "bi-person-badge", "College blazers, lab coats, hoodies, sports jerseys, formal placement wear."),
    ("Accessories", "accessories", "bi-bag-check", "Backpacks, laptop sleeves, water bottles, umbrellas, cycle locks."),
    ("Sports Items", "sports-items", "bi-trophy", "Badminton rackets, cricket bats, footballs, basketballs, gym gear."),
    ("College Supplies", "college-supplies", "bi-mortarboard", "Mini drafters, T-squares, architecture sheets, engineering drawing tools."),
    ("Other", "other", "bi-grid", "Hostel appliances, music instruments, bicycles, room essentials."),
]


def seed_database():
    with app.app_context():
        db.create_all()
        upgrade_schema()

        existing_slugs = {category.slug for category in Category.query.all()}
        for name, slug, icon, description in CATEGORIES:
            if slug not in existing_slugs:
                db.session.add(Category(
                    name=name,
                    slug=slug,
                    icon=icon,
                    description=description,
                ))

        if not User.query.filter_by(role="admin").first():
            admin = User.query.filter_by(email="admin@campus.edu").first()
            if admin is None:
                admin = User(
                    name="Campus Administrator",
                    email="admin@campus.edu",
                    phone="9876543210",
                    department="Dean of Student Welfare",
                    year_semester="Administration",
                    college="Apex Institute of Technology",
                    role="admin",
                )
                admin.set_password("Admin@123")
                db.session.add(admin)

        db.session.commit()
        print("Database initialized without deleting existing data or adding sample listings.")


if __name__ == "__main__":
    seed_database()
