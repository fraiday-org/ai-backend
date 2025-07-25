from mongoengine import DoesNotExist, ValidationError
from fastapi import HTTPException

from app.models.mongodb.client import Client
from app.models.mongodb.client_channel import ClientChannel
from app.schemas.client import ClientChannelCreateorUpdateRequest, ClientChannelResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ClientChannelService:
    @staticmethod
    def create_channel(client_id: str, request: ClientChannelCreateorUpdateRequest) -> ClientChannelResponse:
        """
        Creates a new client channel.

        Args:
            client_id: The client ID
            request: The channel creation request

        Returns:
            The created client channel response

        Raises:
            HTTPException: If the client is not found or validation fails
        """
        try:
            # Validate client exists
            client = Client.objects.get(client_id=client_id)

            # Determine if channel_id is provided
            has_channel_id = hasattr(request, "channel_id") and request.channel_id
            channel_type = request.channel_type.value

            # Validate uniqueness constraints upfront
            if has_channel_id:
                # Check if channel_id already exists for this client
                existing_by_id = ClientChannel.objects(
                    client=client, channel_id=request.channel_id, channel_type=channel_type
                ).first()
                if existing_by_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Channel ID '{request.channel_id}' already exists for this client with the channel type {channel_type}",
                    )
            else:
                # If no channel_id, validate that no channel with the same type exists
                existing_by_type = ClientChannel.objects(client=client, channel_type=channel_type).first()
                if existing_by_type:
                    raise HTTPException(
                        status_code=400,
                        detail=f"A channel with type '{channel_type}' already exists for this client. "
                        f"To create multiple channels of the same type, provide a unique channel_id.",
                    )

            # Create channel data
            channel_data = {
                "channel_type": channel_type,
                "channel_config": request.channel_config.model_dump(),
                "client": client,
                "is_active": request.is_active,
            }

            # Add channel_id if provided
            if has_channel_id:
                channel_data["channel_id"] = request.channel_id

            # Create and save the channel
            channel = ClientChannel(**channel_data)
            channel.save()

            return ClientChannelResponse.model_validate(channel.to_serializable_dict())
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Client not found")
        except ValidationError as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating channel: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create channel")

    @staticmethod
    def list_channels(client_id: str) -> list[ClientChannelResponse]:
        """
        Retrieves a list of all channels for a specific client.
        """
        try:
            client = Client.objects.get(client_id=client_id)
            channels = ClientChannel.objects(client=client, is_active=True).all()
            return [ClientChannelResponse.model_validate(channel.to_serializable_dict()) for channel in channels]
        except DoesNotExist:
            raise HTTPException(404, "Client not found")

    @staticmethod
    def update_channel(client_id: str, channel_id: str, request: ClientChannelCreateorUpdateRequest) -> dict:
        """
        Updates an existing client channel.

        Args:
            client_id: The client ID
            channel_id: The channel ID to update
            request: The update request

        Returns:
            A success message

        Raises:
            HTTPException: If the client or channel is not found, or if validation fails
        """
        try:
            # Validate client and channel exist
            client = Client.objects.get(client_id=client_id)
            channel = ClientChannel.objects.get(id=channel_id, client=client)

            # Get the update data
            update_data = request.model_dump(exclude_unset=True, mode="json")
            if not update_data:  # Nothing to update
                return {"message": "No changes to update"}

            logger.info(f"Update data: {update_data}")
            # Only validate removing channel_id as it's a common case that needs specific handling
            if "channel_id" in update_data and not update_data["channel_id"] and channel.channel_id:
                # Check if another channel with the same type exists
                channel_type = update_data.get("channel_type", channel.channel_type)
                existing = ClientChannel.objects(
                    client=client,
                    channel_type=channel_type,
                    id__ne=channel_id,  # Exclude the current channel
                ).first()

                if existing:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot remove channel_id as another channel with type '{channel_type}' "
                        f"already exists. Each client can have only one channel per type unless a unique "
                        f"channel_id is provided.",
                    )

            # Apply the update and let database indexes handle other uniqueness constraints
            try:
                channel.update(**update_data)
                return {"message": "Channel updated successfully"}
            except Exception as e:
                error_msg = str(e).lower()
                if "duplicate key error" in error_msg:
                    if "channel_id" in error_msg:
                        raise HTTPException(
                            status_code=400, detail="Channel ID is already in use by another channel for this client"
                        )
                    elif "channel_type" in error_msg or "index" in error_msg:
                        raise HTTPException(
                            status_code=400,
                            detail="Update would create a duplicate channel type. Each client can have only one "
                            "channel per type unless a unique channel_id is provided.",
                        )
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="Update would violate uniqueness constraints. The combination of client, "
                            "channel_type, and channel_id must be unique.",
                        )
                raise e

        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Client or channel not found")
        except ValidationError as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating channel: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to update channel")

    @staticmethod
    def get_channel_by_id(client_id: str, channel_id: str) -> ClientChannel:
        """
        Retrieves a specific channel for a client by its channel_id.

        Args:
            client_id: The client ID
            channel_id: The channel ID

        Returns:
            The client channel

        Raises:
            HTTPException: If the client or channel is not found
        """
        try:
            client = Client.objects.get(client_id=client_id)
            channel = ClientChannel.objects.get(client=client, channel_id=channel_id)
            return channel
        except DoesNotExist:
            raise HTTPException(404, f"Channel with ID {channel_id} not found for client {client_id}")

    @staticmethod
    def get_channel_by_type(client_id: str, channel_type: str, channel_id: str = None) -> ClientChannel:
        """
        Retrieves a specific channel for a client by its type or ID.
        If channel_id is provided, it takes precedence over channel_type.

        Args:
            client_id: The client ID
            channel_type: The channel type
            channel_id: Optional channel ID (takes precedence if provided)

        Returns:
            The client channel

        Raises:
            HTTPException: If the client or channel is not found
        """
        try:
            client = Client.objects.get(client_id=client_id)

            # If channel_id is provided, use it for lookup
            if channel_id:
                try:
                    channel = ClientChannel.objects.get(
                        client=client, channel_id=channel_id, channel_type=channel_type
                    )
                    logger.info(
                        f"Found channel by ID {channel_id} and channel_type {channel_type} for client {client_id}. Found channel {channel.id}"
                    )
                    return channel
                except DoesNotExist:
                    logger.warning(f"Channel with ID {channel_id} not found, falling back to channel_type")
                    # Fall back to channel_type if channel_id not found

            # Lookup by channel_type with channel_id as None
            channel = ClientChannel.objects.get(client=client, channel_type=channel_type, channel_id=None)
            return channel
        except DoesNotExist as e:
            logger.error(f"Error finding channel: {e}")
            raise HTTPException(404, f"Channel not found for client {client_id}")

    @staticmethod
    def get_channel_webhook_url(client_id: str, channel_id: str) -> str:
        """
        Retrieves the webhook URL for a specific channel.
        """
        try:
            channel = ClientChannel.objects.get(id=channel_id)
            channel_response = ClientChannelResponse.model_validate(channel.to_serializable_dict())
            return channel_response.channel_config.webhook_url
        except DoesNotExist:
            raise HTTPException(404, "Channel not found")
