import os
from app import create_app
from app.migrations import upgrade_schema
from app.models import db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        upgrade_schema()
    print("=" * 60)
    print("PassItOn – Campus Edition")
    print("Tagline: One student's unused item becomes another student's useful item.")
    print("Running locally at: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=True)
