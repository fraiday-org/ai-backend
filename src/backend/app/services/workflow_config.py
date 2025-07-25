"""
Service for managing workflow configurations.
"""
from typing import List, Optional

from app.models.mongodb.workflow_config import WorkflowConfig
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowConfigService:
    """
    Service for managing workflow configurations.
    """

    @staticmethod
    def get_workflow_id(client_id: str, client_channel_id: Optional[str]) -> str:
        return WorkflowConfigService.get_workflow_config_for_client(client_id, client_channel_id).workflow_id
        
    @staticmethod
    def get_workflow_config_for_client(client_id: str, client_channel_id: Optional[str]) -> WorkflowConfig:
        """
        Get workflow ID based on client and channel with fallback mechanism:
        1. Try client-channel specific config if client_channel_id is provided
        2. Fall back to client-level config
        3. Fall back to default from environment

        Args:
            client_id: The client ID
            client_channel_id: Optional client channel ID

        Returns:
            The workflow ID to use
        """
        # Use default workflow if feature flag is disabled
        if not settings.ENABLE_CONFIGURABLE_WORKFLOWS:
            return settings.SLACK_AI_SERVICE_WORKFLOW_ID

        # Try to find channel-specific config if client_channel_id is provided
        if client_channel_id:
            config = WorkflowConfig.objects(client=client_id, client_channel=client_channel_id, is_active=True).first()

            if config:
                logger.info(
                    f"Using channel-specific workflow ID {config.workflow_id} for client {client_id}, "
                    f"channel {client_channel_id}"
                )
                return config

        # Fall back to client-level config
        config = WorkflowConfig.objects(client=client_id, client_channel=None, is_active=True).first()

        if config:
            logger.info(f"Using client-level workflow ID {config.workflow_id} for client {client_id}")
            return config

        # Fall back to default if no config exists
        logger.info(
            f"No workflow config found for client {client_id}. " f"Using default workflow ID from environment."
        )
        return settings.SLACK_AI_SERVICE_WORKFLOW_ID

    @staticmethod
    def create_workflow_config(client_id: str, name: str, workflow_id: str, is_active: bool = True, client_channel_id: Optional[str] = None, body: Optional[dict] = None) -> WorkflowConfig:
        """
        Create a new workflow configuration.

        Args:
            client_id: The client ID
            workflow_id: The workflow ID
            is_active: Whether the workflow is active
            client_channel_id: Optional client channel ID

        Returns:
            The created workflow configuration
        """
        from app.models.mongodb.client import Client
        from app.models.mongodb.client_channel import ClientChannel

        try:
            client = Client.objects.get(client_id=client_id)
        except Exception as e:
            logger.error(f"Failed to find client with client_id {client_id}: {str(e)}")
            raise ValueError(f"Invalid client_id: {client_id}")
        
        client_channel = None
        if client_channel_id:
            try:
                client_channel = ClientChannel.objects.get(id=client_channel_id)
            except Exception as e:
                logger.error(f"Failed to find client channel with id {client_channel_id}: {str(e)}")
                raise ValueError(f"Invalid client_channel_id: {client_channel_id}")
        
        workflow_config = WorkflowConfig(
            client=client,
            client_channel=client_channel,
            name=name,
            workflow_id=workflow_id,
            is_active=is_active,
            body=body or {}
        )
        workflow_config.save()
        logger.info(f"Created workflow config {workflow_config.id} for client {client.id}")
        return workflow_config

    @staticmethod
    def update_workflow_config(config_id: str, name: Optional[str] = None, workflow_id: Optional[str] = None, is_active: Optional[bool] = None, client_id: Optional[str] = None, client_channel_id: Optional[str] = None, body: Optional[dict] = None) -> WorkflowConfig:
        """
        Update an existing workflow configuration.

        Args:
            config_id: The ID of the configuration to update
            workflow_id: Optional updated workflow ID
            is_active: Optional updated active status
            client_id: Optional updated client ID
            client_channel_id: Optional updated client channel ID

        Returns:
            The updated workflow configuration
        """
        from app.models.mongodb.client import Client
        from app.models.mongodb.client_channel import ClientChannel
        
        workflow_config = WorkflowConfig.objects.get(id=config_id)

        if name is not None:
            workflow_config.name = name
            
        if workflow_id is not None:
            workflow_config.workflow_id = workflow_id
            
        if is_active is not None:
            workflow_config.is_active = is_active
            
        if client_id is not None:
            try:
                client = Client.objects.get(client_id=client_id)
                workflow_config.client = client
            except Exception as e:
                logger.error(f"Failed to find client with client_id {client_id}: {str(e)}")
                raise ValueError(f"Invalid client_id: {client_id}")
                
        if client_channel_id is not None:
            if client_channel_id == "":
                workflow_config.client_channel = None
            else:
                try:
                    client_channel = ClientChannel.objects.get(id=client_channel_id)
                    workflow_config.client_channel = client_channel
                except Exception as e:
                    logger.error(f"Failed to find client channel with id {client_channel_id}: {str(e)}")
                    raise ValueError(f"Invalid client_channel_id: {client_channel_id}")
        
        if body is not None:
            workflow_config.body = body

        workflow_config.save()
        logger.info(f"Updated workflow config {workflow_config.id}")
        return workflow_config

    @staticmethod
    def get_workflow_config(config_id: str) -> WorkflowConfig:
        """
        Get a workflow configuration by ID.

        Args:
            config_id: The ID of the configuration to get

        Returns:
            The workflow configuration
        """
        return WorkflowConfig.objects.get(id=config_id)

    @staticmethod
    def delete_workflow_config(config_id: str) -> bool:
        """
        Delete a workflow configuration.

        Args:
            config_id: The ID of the configuration to delete

        Returns:
            True if the configuration was deleted, False otherwise
        """
        workflow_config = WorkflowConfig.objects.get(id=config_id)
        workflow_config.delete()
        logger.info(f"Deleted workflow config {config_id}")
        return True

    @staticmethod
    def list_workflow_configs(
        client_id: Optional[str] = None, client_channel_id: Optional[str] = None
    ) -> List[WorkflowConfig]:
        """
        List workflow configurations with optional filtering.

        Args:
            client_id: Optional client ID to filter by
            client_channel_id: Optional client channel ID to filter by

        Returns:
            List of workflow configurations matching the filters
        """
        query = {}

        if client_id:
            query["client"] = client_id

        if client_channel_id:
            query["client_channel"] = client_channel_id

        return WorkflowConfig.objects(**query)
