from fastapi import APIRouter

from .endpoints.chat_message import router as chat_message_router
from .endpoints.chat_session import router as chat_session_router
from .endpoints.client import router as client_router
from .endpoints.client_channel import router as client_channel_router
from .endpoints.chat_session_recap import router as chat_session_recap_router
from .endpoints.chat_message_feedback import router as chat_message_feedback_router
from .endpoints.client_data_store import router as client_data_store_router
from .endpoints.semantic_layer.repository import router as repository_router
from .endpoints.semantic_layer.semantic_server import router as semantic_server_router
from .endpoints.semantic_layer.semantic_layer import router as semmantic_layer_router
from .endpoints.semantic_layer.data_store_sync_job import router as data_store_sync_router
from .endpoints.events.event_processor_config import router as event_processor_config_router
from .endpoints.health import router as health_router
from .endpoints.metrics import router as metrics_router
from .endpoints.analytics import router as analytics_router
from .endpoints.chat_session_thread import router as chat_session_thread_router
from .client.user_type import router as client_user_type_router
from .endpoints.workflow_config import router as workflow_config_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(chat_message_router)
api_v1_router.include_router(chat_session_router)
api_v1_router.include_router(client_router)
api_v1_router.include_router(client_channel_router)
api_v1_router.include_router(chat_session_recap_router)
api_v1_router.include_router(chat_message_feedback_router)
api_v1_router.include_router(client_data_store_router)
api_v1_router.include_router(repository_router)
api_v1_router.include_router(semantic_server_router)
api_v1_router.include_router(semmantic_layer_router)
api_v1_router.include_router(data_store_sync_router)
api_v1_router.include_router(event_processor_config_router)
api_v1_router.include_router(health_router)
api_v1_router.include_router(metrics_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(client_user_type_router)
api_v1_router.include_router(chat_session_thread_router)
api_v1_router.include_router(workflow_config_router)
