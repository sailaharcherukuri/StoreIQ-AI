
from db import get_connection
from sklearn.linear_model import LinearRegression
from datetime import date, timedelta
import numpy as np


def generate_forecasts(store_id=None, forecast_days=7):
    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:
        query = """
            SELECT
                s.store_id,
                si.product_id,
                DATE(s.created_at) AS sale_date,
                SUM(si.quantity) AS daily_quantity
            FROM sales s
            JOIN sale_items si ON s.sale_id = si.sale_id
        """

        params = ()

        if store_id is not None:
            query += " WHERE s.store_id = %s"
            params = (store_id,)

        query += """
            GROUP BY s.store_id, si.product_id, DATE(s.created_at)
            ORDER BY sale_date
        """

        cursor.execute(query, params)
        sales_data = cursor.fetchall()

        if not sales_data:
            return []

        # Group sales by store and product
        grouped_data = {}

        for row in sales_data:
            key = (row["store_id"], row["product_id"])

            if key not in grouped_data:
                grouped_data[key] = []

            grouped_data[key].append(row)

        forecasts = []

        for (current_store, product_id), records in grouped_data.items():

            first_date = records[0]["sale_date"]
            last_date = records[-1]["sale_date"]

            total_days = (last_date - first_date).days + 1

            # Fill dates without sales with zero quantity
            daily_sales = {row["sale_date"]: float(row["daily_quantity"])
                           for row in records}

            X = []
            y = []

            for day_number in range(total_days):
                current_date = first_date + timedelta(days=day_number)
                X.append([day_number])
                y.append(daily_sales.get(current_date, 0))

            # Train Linear Regression model
            model = LinearRegression()
            model.fit(np.array(X), np.array(y))

            # Generate future predictions
            for day in range(1, forecast_days + 1):
                future_day = total_days - 1 + day
                predicted_quantity = max(
                    0,
                    float(model.predict([[future_day]])[0])
                )

                forecast_date = date.today() + timedelta(days=day)

                cursor.execute("""
                    INSERT INTO demand_forecasts (
                        store_id,
                        product_id,
                        forecast_date,
                        predicted_qty,
                        model_name
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    current_store,
                    product_id,
                    forecast_date,
                    round(predicted_quantity, 2),
                    "Linear Regression"
                ))

                forecasts.append({
                    "store_id": current_store,
                    "product_id": product_id,
                    "forecast_date": str(forecast_date),
                    "predicted_qty": round(predicted_quantity, 2),
                    "model_name": "Linear Regression"
                })

        connection.commit()
        return forecasts

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def get_all_forecasts(store_id=None):
    connection = get_connection()

    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)

    try:
        query = """
            SELECT
                f.forecast_id,
                f.store_id,
                s.store_name,
                f.product_id,
                p.product_name,
                f.forecast_date,
                f.predicted_qty,
                f.model_name
            FROM demand_forecasts f
            JOIN stores s ON f.store_id = s.store_id
            JOIN products p ON f.product_id = p.product_id
        """

        if store_id is not None:
            query += " WHERE f.store_id = %s"
            cursor.execute(query, (store_id,))
        else:
            cursor.execute(query)

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()
