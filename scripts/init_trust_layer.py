#!/usr/bin/env python3
"""
Initialize Trust Layer System

This script:
1. Verifies database tables are created
2. Registers default plugins  
3. Checks environment configuration
4. Runs health checks
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database import DatabaseManager
from trust_layer import get_registry
from trust_layer.plugins.email_auth import EmailAuthPlugin
from trust_layer.scoring_engine import ScoringEngine

def main():
    print("🛡️  Trust Layer Initialization")
    print("=" * 50)
    
    # 1. Check database
    print("\n📦 Checking database...")
    try:
        db = DatabaseManager()
        print("✅ Database initialized")
        
        # Verify tables exist
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'trust_%'
            """)
            tables = cursor.fetchall()
            
            print(f"✅ Found {len(tables)} trust tables:")
            for table in tables:
                print(f"   - {table[0]}")
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 2. Register plugins
    print("\n🔌 Registering plugins...")
    try:
        registry = get_registry()
        
        # Register all plugins
        from trust_layer.plugins.email_auth import EmailAuthPlugin
        from trust_layer.plugins.dns_records import DNSRecordsPlugin
        from trust_layer.plugins.content_heuristics import ContentHeuristicsPlugin
        
        registry.register(EmailAuthPlugin(config={'enabled': True}))
        registry.register(DNSRecordsPlugin(config={'enabled': True}))
        registry.register(ContentHeuristicsPlugin(config={'enabled': True}))
        
        plugins = registry.list_plugins()
        print(f"✅ Registered {len(plugins)} plugin(s):")
        for plugin in plugins:
            status = "✅" if plugin['enabled'] else "⏸️"
            print(f"   {status} {plugin['name']} v{plugin['version']}")
    except Exception as e:
        print(f"❌ Plugin registration error: {e}")
        return 1
    
    # 3. Check environment
    print("\n⚙️  Checking environment...")
    required_vars = []
    optional_vars = [
        'GOOGLE_SAFE_BROWSING_API_KEY',
        'VIRUSTOTAL_API_KEY',
        'LINKEDIN_CLIENT_ID',
        'LINKEDIN_CLIENT_SECRET'
    ]
    
    missing_required = [var for var in required_vars if not os.getenv(var)]
    if missing_required:
        print(f"❌ Missing required variables: {', '.join(missing_required)}")
        return 1
    
    available_optional = [var for var in optional_vars if os.getenv(var)]
    print(f"✅ {len(available_optional)} optional services configured:")
    for var in available_optional:
        print(f"   - {var}")
    
    if len(available_optional) < len(optional_vars):
        missing = set(optional_vars) - set(available_optional)
        print(f"ℹ️  Optional services not configured: {', '.join(missing)}")
    
    # 4. Initialize scoring engine
    print("\n📊 Initializing scoring engine...")
    try:
        engine = ScoringEngine(ruleset_version="1.0")
        rules = engine.list_rules()
        print(f"✅ Loaded {len(rules)} scoring rules")
        
        # Show a few example rules
        print("   Example rules:")
        for rule in rules[:3]:
            print(f"   - {rule['rule_id']}: {rule['points_delta']} points")
    except Exception as e:
        print(f"❌ Scoring engine error: {e}")
        return 1
    
    # 5. Summary
    print("\n" + "=" * 50)
    print("✅ Trust Layer initialized successfully!")
    print("\nNext steps:")
    print("1. Copy .env.trust_layer.sample to .env and add API keys")
    print("2. Restart the dashboard: ./ops/startup.sh restart")
    print("3. Access trust reports via API: http://localhost:8008/docs")
    print("\nDocumentation: devdocs/TRUST_LAYER_STATUS.md")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
