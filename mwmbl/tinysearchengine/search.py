from logging import getLogger

from ninja import Router

from mwmbl.tinysearchengine.rank import HeuristicRanker

logger = getLogger(__name__)


SCORE_THRESHOLD = 0.25


def create_router(ranker: HeuristicRanker) -> Router:
    router = Router(tags=["search"])

    @router.get("")
    def search(request, s: str):
        return ranker.search(s)

    @router.get("/complete")
    def complete(request, q: str):
        return ranker.complete(q)

    return router
