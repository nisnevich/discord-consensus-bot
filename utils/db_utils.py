import const
import sqlite3
import atexit

conn = None


def connect_db():
    """
    Connect to the database. If the connection hasn't been established yet, create a new connection and register a function to close the connection when the program exits.
    Returns:
        conn (sqlite3.Connection): The connection to the database.
    """
    global conn
    if conn is None:
        conn = sqlite3.connect(const.DB_NAME)
        atexit.register(close_db)
    return conn


def close_db():
    """
    Close the connection to the database if it has been established.
    """
    global conn
    if conn is not None:
        conn.close()


def run_query(query, params=()):
    """
    Run a query on the database.
    Parameters:
        query (str): The query to run.
        params (tuple, optional): The parameters to bind to the query.
    Returns:
        cursor (sqlite3.Cursor): The cursor for the query.
    """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor
