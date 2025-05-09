import base64
import codecs
import sys

from redis.commands.search.query import Query
from ulid import ULID
from models import Item, ItemId, ItemWithScore


class ItemsService:
    def __init__(self, redis_client):
        self.redis = redis_client

    def add(self, title: str, author: str, image_url: str, embedding: str) -> Item:
        ulid = str(ULID())

        return self.save_to_redis(
            ulid=ulid,
            title=title,
            author=author,
            image_url=image_url,
            embedding=embedding,
        )

    def get(self, ulid: str) -> Item:
        item = self.redis.hgetall(f"item:{ulid}")

        if not item:
            return None

        return Item(
            ulid=item[b"ulid"].decode("utf-8"),
            title=item[b"title"].decode("utf-8"),
            author=item[b"author"].decode("utf-8"),
            image_url=item[b"image_url"].decode("utf-8"),
            embedding=base64.b64encode(item[b"embedding"]).decode("utf-8"),
        )

    def update(
        self, ulid: str, title: str, author: str, image_url: str, embedding: str
    ) -> Item:
        if not self.item_exists(ulid):
            return None

        return self.save_to_redis(
            ulid=ulid,
            title=title,
            author=author,
            image_url=image_url,
            embedding=embedding,
        )

    def delete(self, ulid: str) -> ItemId:
        count = self.redis.unlink(self.key(ulid))
        return ItemId(ulid=ulid) if count > 0 else None

    def search(self, embedding: str) -> list[ItemWithScore]:
        query = Query("(*)=>[KNN 5 @embedding $blob as score]")
        query.sort_by("score")
        query.return_fields(
            "ulid", "title", "author", "image_url", "embedding", "score"
        )
        query.paging(0, 5)
        query.dialect(3)

        bytes = base64.b64decode(embedding)
        query_params = {"blob": bytes}

        response = self.redis.ft("item:index").search(query, query_params)
        results = response[b"results"]

        found_items = []

        for result in results:
            attributes = result[b"extra_attributes"]
            ulid = attributes[b"ulid"].decode("utf-8")
            title = attributes[b"title"].decode("utf-8")
            author = attributes[b"author"].decode("utf-8")
            image_url = attributes[b"image_url"].decode("utf-8")
            embedding = attributes[b"embedding"]
            score = attributes[b"score"]

            found_items.append(
                ItemWithScore(
                    ulid=ulid,
                    title=title,
                    author=author,
                    image_url=image_url,
                    embedding=base64.b64encode(embedding).decode("utf-8"),
                    score=score,
                )
            )

        return found_items

    def item_exists(self, ulid: str) -> bool:
        return self.redis.exists(self.key(ulid)) > 0

    def save_to_redis(
        self, ulid: str, title: str, author: str, image_url: str, embedding: str
    ) -> Item:

        self.redis.hset(
            self.key(ulid),
            mapping={
                "ulid": ulid,
                "title": title,
                "author": author,
                "image_url": image_url,
                "embedding": base64.b64decode(embedding),
            },
        )

        return Item(
            ulid=ulid,
            title=title,
            author=author,
            image_url=image_url,
            embedding=embedding,
        )

    def key(self, ulid: str) -> str:
        return f"item:{ulid}"
