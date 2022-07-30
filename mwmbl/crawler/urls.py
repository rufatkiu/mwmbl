"""
Database storing info on URLs
"""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable

from psycopg2 import connect
from psycopg2.extras import execute_values


# Client has one hour to crawl a URL that has been assigned to them, or it will be reassigned
from mwmbl.database import Database

REASSIGN_MIN_HOURS = 1
BATCH_SIZE = 100


class URLStatus(Enum):
    """
    URL state update is idempotent and can only progress forwards.
    """
    NEW = 0                   # One user has identified this URL
    ASSIGNED = 10             # The crawler has given the URL to a user to crawl
    ERROR_TIMEOUT = 20        # Timeout while retrieving
    ERROR_404 = 30            # 404 response
    ERROR_OTHER = 40          # Some other error
    ERROR_ROBOTS_DENIED = 50  # Robots disallow this page
    CRAWLED = 100             # At least one user has crawled the URL


def batch(items: list, batch_size):
    """
    Adapted from https://stackoverflow.com/a/8290508
    """
    length = len(items)
    for ndx in range(0, length, batch_size):
        yield items[ndx:min(ndx + batch_size, length)]


@dataclass
class FoundURL:
    url: str
    user_id_hash: str
    score: float
    status: URLStatus
    timestamp: datetime


class URLDatabase:
    def __init__(self, connection):
        self.connection = connection

    def create_tables(self):
        sql = """
        CREATE TABLE IF NOT EXISTS urls (
            url VARCHAR PRIMARY KEY,
            status INT NOT NULL DEFAULT 0,
            user_id_hash VARCHAR NOT NULL,
            score FLOAT NOT NULL DEFAULT 1,
            updated TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """

        with self.connection.cursor() as cursor:
            cursor.execute(sql)

    def update_found_urls(self, found_urls: list[FoundURL]):
        if len(found_urls) == 0:
            return

        get_urls_sql = """
          SELECT url FROM urls
          WHERE url in %(urls)s
        """

        lock_urls_sql = """
          SELECT url FROM urls
          WHERE url in %(urls)s
          FOR UPDATE SKIP LOCKED
        """

        insert_sql = f"""
         INSERT INTO urls (url, status, user_id_hash, score, updated) values %s
         ON CONFLICT (url) DO UPDATE SET
           status = GREATEST(urls.status, excluded.status),
           user_id_hash = CASE
             WHEN urls.status > excluded.status THEN urls.user_id_hash ELSE excluded.user_id_hash
           END,
           score = urls.score + excluded.score,
           updated = CASE
             WHEN urls.status > excluded.status THEN urls.updated ELSE excluded.updated
           END
        """

        input_urls = [x.url for x in found_urls]
        assert len(input_urls) == len(set(input_urls))

        with self.connection as connection:
            with connection.cursor() as cursor:
                cursor.execute(get_urls_sql, {'urls': tuple(input_urls)})
                existing_urls = {x[0] for x in cursor.fetchall()}
                new_urls = set(input_urls) - existing_urls

                cursor.execute(lock_urls_sql, {'urls': tuple(input_urls)})
                locked_urls = {x[0] for x in cursor.fetchall()}

                urls_to_insert = new_urls | locked_urls

                if len(urls_to_insert) != len(input_urls):
                    print(f"Only got {len(urls_to_insert)} instead of {len(input_urls)} - {len(new_urls)} new")

                sorted_urls = sorted(found_urls, key=lambda x: x.url)
                data = [
                    (found_url.url, found_url.status.value, found_url.user_id_hash, found_url.score, found_url.timestamp)
                    for found_url in sorted_urls if found_url.url in urls_to_insert]

                execute_values(cursor, insert_sql, data)

    def get_new_batch_for_user(self, user_id_hash: str):
        sql = f"""
        UPDATE urls SET status = {URLStatus.ASSIGNED.value}, user_id_hash = %(user_id_hash)s, updated = %(now)s
        WHERE url IN (
          SELECT url FROM urls
          WHERE status = {URLStatus.NEW.value} OR (
            status = {URLStatus.ASSIGNED.value} AND updated < %(min_updated_date)s
          )
          ORDER BY score DESC
          LIMIT {BATCH_SIZE}
          FOR UPDATE SKIP LOCKED
        )
        RETURNING url
        """

        now = datetime.utcnow()
        min_updated_date = now - timedelta(hours=REASSIGN_MIN_HOURS)
        with self.connection.cursor() as cursor:
            cursor.execute(sql, {'user_id_hash': user_id_hash, 'min_updated_date': min_updated_date, 'now': now})
            results = cursor.fetchall()

        return [result[0] for result in results]

    def get_url_scores(self, urls: list[str]) -> dict[str, float]:
        sql = f"""
        SELECT url, score FROM urls WHERE url IN %(urls)s
        """

        url_scores = {}
        for url_batch in batch(urls, 10000):
            with self.connection.cursor() as cursor:
                cursor.execute(sql, {'urls': tuple(url_batch)})
                results = cursor.fetchall()
                url_scores.update({result[0]: result[1] for result in results})

        return url_scores


if __name__ == "__main__":
    with Database() as db:
        url_db = URLDatabase(db.connection)
        url_db.create_tables()
        # update_url_status(conn, [URLStatus("https://mwmbl.org", URLState.NEW, "test-user", datetime.now())])
        # url_db.user_found_urls("Test user", ["a", "b", "c"], datetime.utcnow())
        # url_db.user_found_urls("Another user", ["b", "c", "d"], datetime.utcnow())
        # url_db.user_crawled_urls("Test user", ["c"], datetime.utcnow())
        batch = url_db.get_new_batch_for_user('test user 4')
        print("Batch", len(batch), batch)