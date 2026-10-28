from ninja import NinjaAPI

from core.api import router as core_router

api = NinjaAPI()
api.add_router("", core_router)
