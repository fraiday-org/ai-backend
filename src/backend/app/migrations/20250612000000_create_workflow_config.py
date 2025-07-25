"""
Migration to create the WorkflowConfig collection and indexes.
"""
from mongodb_migrations.base import BaseMigration
from pymongo import ASCENDING, IndexModel


class Migration(BaseMigration):
    def upgrade(self):
        """
        Create the workflow_configs collection and set up indexes.
        """
        # Create the collection if it doesn't exist
        if "workflow_configs" not in self.db.list_collection_names():
            self.db.create_collection("workflow_configs")
        
        # Create indexes
        workflow_configs = self.db.workflow_configs
        indexes = [
            IndexModel([('client', ASCENDING)]),
            IndexModel([('client_channel', ASCENDING)]),
            IndexModel([('is_active', ASCENDING)]),
            # Removed compound index as it's already defined in the model
            # with uniqueness constraints
        ]
        
        workflow_configs.create_indexes(indexes)
        
        print("Created workflow_configs collection and indexes")

    def downgrade(self):
        """
        Drop the workflow_configs collection.
        """
        if "workflow_configs" in self.db.list_collection_names():
            self.db.workflow_configs.drop()
            print("Dropped workflow_configs collection")
