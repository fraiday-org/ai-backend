"""
Migration to populate default workflow configurations for existing clients.
"""
import os
from datetime import datetime
from datetime import timezone
from mongodb_migrations.base import BaseMigration


class Migration(BaseMigration):
    def upgrade(self):
        """
        Populate default workflow configurations for existing clients.
        """
        # Get the default workflow ID from environment
        default_workflow_id = os.environ.get("SLACK_AI_SERVICE_WORKFLOW_ID", "")
        
        if not default_workflow_id:
            print("Warning: SLACK_AI_SERVICE_WORKFLOW_ID not set in environment, using empty string")
        
        # Get all clients
        clients = self.db.clients.find({})
        
        # Create default workflow configs for each client
        workflow_configs = []
        now = datetime.now(timezone.utc)
        
        for client in clients:
            client_id = client.get("_id")
            client_name = client.get("name", "Unknown")
            
            # Get the latest client channel for this client
            latest_channel = self.db.client_channels.find_one(
                {"client": client_id},
                sort=[("created_at", -1)]
            )
            
            if latest_channel:
                channel_id = latest_channel.get("_id")
                channel_name = latest_channel.get("type", "Unknown")
                
                # Create chat workflow config with client channel
                workflow_config = {
                    "name": f"{client_name} - {channel_name} Default Chat Workflow",
                    "description": f"Default chat workflow configuration for {client_name} channel {channel_name}",
                    "client": client_id,
                    "client_channel": channel_id,
                    "workflow_id": default_workflow_id,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now
                }
                workflow_configs.append(workflow_config)
            else:
                print(f"Warning: No channel found for client {client_name}, skipping workflow config creation")
        
        # Insert the workflow configs if there are any
        if workflow_configs:
            self.db.workflow_configs.insert_many(workflow_configs)
            print(f"Created {len(workflow_configs)} default workflow configurations")
        else:
            print("No valid client-channel pairs found, no default workflow configurations created")

    def downgrade(self):
        """
        Remove all default workflow configurations.
        """
        # Remove all workflow configs created by this migration
        result = self.db.workflow_configs.delete_many({"workflow_id": os.environ.get("SLACK_AI_SERVICE_WORKFLOW_ID", "")})
        print(f"Removed {result.deleted_count} default workflow configurations")
