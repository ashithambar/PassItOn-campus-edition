from sqlalchemy import inspect, text

from app.models import db


def upgrade_schema():
    inspector = inspect(db.engine)
    if 'listings' not in inspector.get_table_names():
        return

    listing_columns = {column['name'] for column in inspector.get_columns('listings')}
    if 'listing_type' not in listing_columns:
        db.session.execute(text(
            "ALTER TABLE listings ADD COLUMN listing_type "
            "VARCHAR(20) NOT NULL DEFAULT 'sell_only'"
        ))
        db.session.commit()

    db.create_all()
