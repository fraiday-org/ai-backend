"""
Migration to update the EventProcessorConfig model to add client_channel field and indexes.
"""
from mongodb_migrations.base import BaseMigration
from pymongo import ASCENDING, IndexModel


class Migration(BaseMigration):
    def upgrade(self):
        """
        Update the event_processor_configs collection to add client_channel field and indexes.
        """
        # Check if collection exists
        if "event_processor_configs" not in self.db.list_collection_names():
            print("event_processor_configs collection does not exist, skipping")
            return
        
        # Create new indexes
        event_processor_configs = self.db.event_processor_configs
        indexes = [
            IndexModel([("client_channel", ASCENDING)]),
            # Removed compound index as it's already defined in the model
            # with uniqueness constraints
        ]
        
        event_processor_configs.create_indexes(indexes)
        print("Added client_channel indexes to event_processor_configs collection")
        
        # Update event processor configs with client_channel
        processors = list(event_processor_configs.find({}))
        updated_count = 0
        
        for processor in processors:
            client_id = processor.get('client')
            if client_id:
                # Find the latest client channel for this client
                latest_channel = self.db.client_channels.find_one(
                    {"client": client_id},
                    sort=[("created_at", -1)]
                )
                
                if latest_channel:
                    channel_id = latest_channel.get("_id")
                    # Update the processor with the client_channel
                    event_processor_configs.update_one(
                        {"_id": processor["_id"]},
                        {"$set": {"client_channel": channel_id}}
                    )
                    updated_count += 1
        
        print(f"Updated {updated_count} event processor configs with client_channel references")

    def downgrade(self):
        """
        Remove the client_channel indexes from event_processor_configs collection.
        """
        if "event_processor_configs" not in self.db.list_collection_names():
            print("event_processor_configs collection does not exist, skipping")
            return
        
        # Remove client_channel field from all documents
        event_processor_configs = self.db.event_processor_configs
        result = event_processor_configs.update_many(
            {},
            {"$unset": {"client_channel": ""}}
        )
        print(f"Removed client_channel field from {result.modified_count} documents")
        
        # Drop the indexes
        try:
            event_processor_configs.drop_index("client_channel_1")
            event_processor_configs.drop_index("client_1_client_channel_1_is_active_1")
        except Exception as e:
            print(f"Error dropping indexes: {e}")
        
        print("Removed client_channel indexes from event_processor_configs collection")
