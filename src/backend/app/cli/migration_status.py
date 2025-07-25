#!/usr/bin/env python
"""
Script to show migration status without running migrations.
"""
import sys
import argparse
import os
import re

def main():
    parser = argparse.ArgumentParser(description="Show migration status")
    parser.add_argument("--url", required=True, help="MongoDB URL")
    parser.add_argument("--migrations", required=True, help="Path to migrations directory")
    args = parser.parse_args()
    
    try:
        from mongodb_migrations.cli import Configuration, MigrationManager
        
        # Set up configuration
        config = Configuration()
        config.mongo_url = args.url
        config.mongo_migrations_path = args.migrations
        config.metastore = 'database_migrations'
        
        # Initialize manager
        manager = MigrationManager(config)
        
        # Connect to database
        manager.db = manager._get_mongo_database(
            manager.config.mongo_host, 
            manager.config.mongo_port, 
            manager.config.mongo_database,
            manager.config.mongo_username, 
            manager.config.mongo_password, 
            manager.config.mongo_url
        )
        
        # Get migrations from files (similar to how MigrationManager does it)
        migrations = {}
        files = os.listdir(manager.config.mongo_migrations_path)
        for file in files:
            result = re.match('^(\d+)[_a-z]*\.py$', file)
            if result:
                migrations[result.group(1)] = file[:-3]
        
        # Get migrations from database
        database_migrations = manager._get_migration_names()
        db_migration_names = [migration['migration_datetime'] for migration in database_migrations]
        
        # Print status
        print('\nMigration Status:')
        print('-' * 60)
        print(f"{'Migration':40} {'Status':20}")
        print('-' * 60)
        
        for migration_datetime in sorted(migrations.keys()):
            migration_name = migrations[migration_datetime]
            status = 'Applied' if migration_datetime in db_migration_names else 'Pending'
            print(f"{migration_name:40} {status:20}")
            
        print('\n')
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
