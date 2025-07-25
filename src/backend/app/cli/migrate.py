#!/usr/bin/env python
"""
Command-line utility for running MongoDB migrations using mongodb-migrations.
"""
import sys
import argparse
import subprocess
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.utils.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# Define mongodb-migrations commands
COMMANDS = {
    "up": "Apply all pending migrations",
    "down": "Downgrade migrations",
    "list": "List all migrations and their status (may auto-migrate)",
    "status": "Show migration status without migrating",
    "create": "Create a new migration file"
}


def run_mongodb_migrations(args):
    """
    Run mongodb-migrations with the specified arguments.
    
    Args:
        args: Command line arguments
    
    Returns:
        Exit code from the command
    """
    # Parse MongoDB connection info from settings
    mongo_uri = settings.MONGODB_URI
    
    # Base command
    cmd = ["mongodb-migrate"]
    
    # Based on the _get_mongo_database method in mongodb_migrations/cli.py,
    # we should only provide the URL parameter and let the library handle the connection
    cmd.extend(["--url", mongo_uri])
    
    # Add migrations directory - using the new location
    migrations_path = str(Path(__file__).parent.parent / "migrations")
    cmd.extend(["--migrations", migrations_path])
    
    # Add metastore collection name
    cmd.extend(["--metastore", "database_migrations"])
    
    # Handle different commands
    if args.command == "up":
        # Apply all pending migrations
        pass  # No additional args needed
    
    elif args.command == "down":
        # Downgrade migrations
        cmd.append("--downgrade")
        
        # Add specific migration target if provided
        if args.migration_id:
            cmd.extend(["--to_datetime", args.migration_id])
    
    elif args.command == "status":
        # Use the separate script for showing migration status
        script_path = str(Path(__file__).parent / "migration_status.py")
        cmd = ["python", script_path, "--url", mongo_uri, "--migrations", migrations_path]
    
    elif args.command == "create":
        # Create a new migration
        cmd = ["mongodb-migrate-create"]
        cmd.extend(["--migrations", str(Path(__file__).parent.parent / "migrations")])
        
        if args.description:
            cmd.extend(["--description", args.description])
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    try:
        # Run the command and capture output
        result = subprocess.run(
            cmd, 
            check=True, 
            capture_output=True, 
            text=True
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        # Print any warnings/errors
        if result.stderr:
            print(f"Warnings/Errors: {result.stderr}", file=sys.stderr)
        
        return 0
    
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}", file=sys.stderr)
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}", file=sys.stderr)
        return e.returncode


def main():
    """
    Main entry point for the migration CLI.
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="MongoDB migration utility using mongodb-migrations"
    )
    
    subparsers = parser.add_subparsers(
        dest="command",
        help="Migration command",
        required=True
    )
    
    # Create subparsers for each command
    for cmd, description in COMMANDS.items():
        cmd_parser = subparsers.add_parser(cmd, help=description)
        
        # Add command-specific arguments
        if cmd == "down":
            cmd_parser.add_argument(
                "migration_id",
                nargs="?",
                help="Migration ID to downgrade to (optional)"
            )
        elif cmd == "create":
            cmd_parser.add_argument(
                "description",
                help="Description for the new migration file"
            )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Run the command
    return run_mongodb_migrations(args)


if __name__ == "__main__":
    sys.exit(main())
