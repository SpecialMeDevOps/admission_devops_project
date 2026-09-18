import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")
    app.config.from_mapping(
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///admission.db"),
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", "uploads"),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    init_database(app)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        try:
            with get_connection(app) as connection:
                connection.cursor().execute("SELECT 1")
            return jsonify(status="ok", service="admission-api")
        except Exception:
            return jsonify(status="unhealthy", service="admission-api"), 503

    @app.post("/api/admissions")
    def submit_admission():
        student_name = request.form.get("student_name", "").strip()
        email = request.form.get("email", "").strip()
        document = request.files.get("document")

        if not student_name or not email or not document or not document.filename:
            return jsonify(error="Student name, email, and a document are required."), 400
        if "." not in document.filename or document.filename.rsplit(".", 1)[1].lower() not in ALLOWED_EXTENSIONS:
            return jsonify(error="Unsupported document type."), 400

        extension = document.filename.rsplit(".", 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{extension}"
        document.save(Path(app.config["UPLOAD_FOLDER"]) / secure_filename(stored_name))

        with get_connection(app) as connection:
            cursor = connection.cursor()
            if is_sqlite(app):
                cursor.execute(
                    "INSERT INTO admissions (student_name, email, document_name) VALUES (?, ?, ?)",
                    (student_name, email, stored_name),
                )
            else:
                cursor.execute(
                    "INSERT INTO admissions (student_name, email, document_name) VALUES (%s, %s, %s)",
                    (student_name, email, stored_name),
                )
            connection.commit()

        return jsonify(message="Admission submitted successfully."), 201

    return app


def is_sqlite(app):
    return app.config["DATABASE_URL"].startswith("sqlite:///")


@contextmanager
def get_connection(app):
    database_url = app.config["DATABASE_URL"]
    if is_sqlite(app):
        connection = sqlite3.connect(database_url.removeprefix("sqlite:///"))
    else:
        import psycopg

        connection = psycopg.connect(database_url)
    try:
        yield connection
    finally:
        connection.close()


def init_database(app):
    with get_connection(app) as connection:
        cursor = connection.cursor()
        statement = (
            "CREATE TABLE IF NOT EXISTS admissions ("
            "id SERIAL PRIMARY KEY, student_name VARCHAR(200) NOT NULL, "
            "email VARCHAR(320) NOT NULL, document_name VARCHAR(255) NOT NULL, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        if is_sqlite(app):
            statement = statement.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        cursor.execute(statement)
        connection.commit()


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
