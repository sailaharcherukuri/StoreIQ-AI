
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from db import get_db_connection
import traceback

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        connection = get_db_connection()

        if not connection:
            flash("Database connection failed.", "error")
            return render_template("login.html")

        try:
            cursor = connection.cursor(dictionary=True)

            cursor.execute("""
                SELECT
                    u.user_id,
                    u.full_name,
                    u.email,
                    u.password_hash,
                    u.is_active,
                    r.role_name
                FROM users u
                JOIN roles r ON u.role_id = r.role_id
                WHERE u.email = %s
            """, (email,))

            user = cursor.fetchone()
            cursor.close()

            if (
                user
                and user["is_active"]
                and check_password_hash(user["password_hash"], password)
            ):
                session.clear()
                session["user_id"] = user["user_id"]
                session["full_name"] = user["full_name"]
                session["email"] = user["email"]
                session["role"] = user["role_name"]

                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "error")

        except Exception:
            traceback.print_exc()
            flash("Something went wrong. Check the terminal.", "error")

        finally:
            connection.close()

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("auth.login"))
