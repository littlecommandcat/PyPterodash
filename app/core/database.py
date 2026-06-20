import json
import logging
import os
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv
from pymongo import MongoClient


class ConfigCache:
    def __init__(self):
        self.config = {}
        self.price = {}

    def get_config(self, key: str, default: any = None, force: bool = True) -> str | None:
        if key not in self.config or force:
            load_dotenv()
            self.config[key] = os.environ.get(key)

        return self.config.get(key, default)
    
    def get_price(self, key: str, default: int = 5, force: bool = True) -> int:
        if key not in self.config or force:
            
            file = "price.json"
            if not os.path.exists(file):
                logging.error("Couldn't find price.json")
                return default
                
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.price = data

            except json.JSONDecodeError:
                logging.error(f"{file} json type error.")

            except Exception as e:
                logging.error(f"Price loaded error: {e}")
            
            return self.price.get(key, default)

class DataManager:

    def __init__(
        self,
        db_name: str = None,
        collection_name: str = None,
        uri: str = None,
    ):
        self.config = ConfigCache()
        self.uri: str | None = uri or self.config.get_config("mongo_uri")
        self.db_name: str | None = db_name or self.config.get_config("mongo_db")
        self.collection_name: str | None = collection_name or self.config.get_config(
            "mongo_collection"
        )

        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.collection_name]



    def find_one(self, query: dict) -> dict | None:
        if self.collection is None:
            logging.error("[Database Error] Collection is not initialized. Call set_client() first.")
            return None


        logging.info(f"[Cache MISS] Query: {query}")
        result = self.collection.find_one(query)


        return result

    def find_all(self, query: dict) -> list[dict]:
        if self.collection is None:
            logging.error("[Database Error] Collection is not initialized.")
            return []
        
        logging.info(f"[DB Find All] Query: {query}")
        cursor = self.collection.find(query)
        
        results = []
        for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    def insert_one(self, document: dict):
        if self.collection is None:
            raise RuntimeError("Collection not initialized.")
        result = self.collection.insert_one(document)
        logging.info(f"[Insert] Inserted ID: {result.inserted_id}")
        return result

    def update_one(self, query: dict, update_data: dict):
        if self.collection is None:
            raise RuntimeError("Collection not initialized.")
        result = self.collection.update_one(query, update_data)
        logging.info(
            f"[Update] Matched: {result.matched_count}, Modified: {result.modified_count}"
        )


        return result

    def delete_one(self, query: dict):
        if self.collection is None:
            raise RuntimeError("Collection not initialized.")
        result = self.collection.delete_one(query)
        logging.info(f"[Delete] Deleted Count: {result.deleted_count}")


        return result


@dataclass
class ServerResource:
    name: str
    user: int
    nest: int
    egg: int
    docker_image: str
    startup: str
    
    description: str | None = None
    start_on_completion: bool = False
    
    limits: dict[str, int] = field(default_factory=lambda: {
        "memory": 1024,
        "swap": 0,
        "disk": 5120,
        "io": 500,
        "cpu": 100
    })
    
    feature_limits: dict[str, int] = field(default_factory=lambda: {
        "databases": 0,
        "allocations": 1,
        "backups": 0
    })
    
    allocation: dict[str, any] = field(default_factory=lambda: {
        "default": 0,
        "additional": []
    })

    environment: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, any]:
        return asdict(self)


datamanager = DataManager()
config = ConfigCache()