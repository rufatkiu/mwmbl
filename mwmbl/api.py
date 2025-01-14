from multiprocessing import Queue
from pathlib import Path

from django.conf import settings
from ninja import NinjaAPI

import mwmbl.crawler.app as crawler
from mwmbl.indexer.batch_cache import BatchCache
from mwmbl.indexer.paths import INDEX_NAME, BATCH_DIR_NAME
from mwmbl.tinysearchengine import search
from mwmbl.tinysearchengine.completer import Completer
from mwmbl.tinysearchengine.indexer import TinyIndex, Document
from mwmbl.tinysearchengine.rank import HeuristicRanker


queued_batches = Queue()
completer = Completer()

index_path = Path(settings.DATA_PATH) / INDEX_NAME
tiny_index = TinyIndex(item_factory=Document, index_path=index_path)
tiny_index.__enter__()
ranker = HeuristicRanker(tiny_index, completer)
batch_cache = BatchCache(Path(settings.DATA_PATH) / BATCH_DIR_NAME)


def create_api(version):
    api = NinjaAPI(version=version)

    search_router = search.create_router(ranker)
    api.add_router("/search/", search_router)

    crawler_router = crawler.create_router(batch_cache=batch_cache, queued_batches=queued_batches)
    api.add_router("/crawler/", crawler_router)
    return api


# Work around because Django-Ninja doesn't allow using multiple URLs for the same thing
api_original = create_api("0.1")
api_v1 = create_api("1.0.0")
