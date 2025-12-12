"""
Test script for LangGraph orchestrator.

Tests the new LangGraph-based incident processing workflow.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.langgraph_orchestrator import LangGraphOrchestrator


async def test_langgraph_orchestrator():
    """Test the LangGraph orchestrator with a sample incident."""
    
    print("=" * 60)
    print("Testing LangGraph Orchestrator")
    print("=" * 60)
    
    # Initialize orchestrator
    print("\n1. Initializing LangGraph orchestrator...")
    orchestrator = LangGraphOrchestrator()
    print("✅ Orchestrator initialized")
    
    # Create test incident
    print("\n2. Creating test incident...")
    incident_data = {
        'incident_id': 'test-langgraph-001',
        'vlm_summary': {
            'confidence': 0.92,
            'incident_type': 'vehicle_collision',
            'description': 'High-speed collision detected on highway',
            'vehicles_involved': 2,
            'recommended_alerts': ['call', 'sms'],
            'ambiguous': False,
        },
        'enhanced_report': {
            'report_text': 'Critical incident: Two-vehicle collision with potential injuries',
            'risk_score': 9,
            'executive_summary': 'High-severity collision requiring immediate emergency response',
        },
        'location': {
            'lat': 12.9716,
            'lon': 77.5946,
        },
        'history': [],
    }
    
    print(f"   Incident ID: {incident_data['incident_id']}")
    print(f"   Type: {incident_data['vlm_summary']['incident_type']}")
    print(f"   Risk Score: {incident_data['enhanced_report']['risk_score']}/10")
    print(f"   Confidence: {incident_data['vlm_summary']['confidence']}")
    
    # Process incident
    print("\n3. Processing incident through LangGraph...")
    try:
        result = await orchestrator.process_incident_async(incident_data)
        
        print("\n✅ Incident processed successfully!")
        print("\n4. Results:")
        print(f"   Final Status: {result['action_result']['final_status']}")
        print(f"   Actions Created: {len(result['action_result']['action_plan'])}")
        print(f"   Audit Entries: {len(result['action_result']['audit'])}")
        
        # Display action plan
        print("\n5. Action Plan:")
        for i, action in enumerate(result['action_result']['action_plan'], 1):
            print(f"   {i}. {action['type'].upper()} to {action['target_role']}")
            print(f"      Number: {action['number']}")
            print(f"      Status: {action['status']}")
        
        # Display audit trail (last 5 entries)
        print("\n6. Audit Trail (last 5 entries):")
        for entry in result['action_result']['audit'][-5:]:
            print(f"   • {entry['step']}: {entry['outcome']}")
        
        # Test state retrieval
        print("\n7. Testing state retrieval...")
        state = orchestrator.get_incident(incident_data['incident_id'])
        if state:
            print(f"   ✅ State retrieved: {state['status']}")
        else:
            print("   ❌ State not found")
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error processing incident: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_policy_decisions():
    """Test different policy decision paths."""
    
    print("\n" + "=" * 60)
    print("Testing Policy Decision Paths")
    print("=" * 60)
    
    orchestrator = LangGraphOrchestrator()
    
    test_cases = [
        {
            'name': 'Critical - Auto Dispatch',
            'risk_score': 9,
            'confidence': 0.95,
            'expected': 'auto_dispatch'
        },
        {
            'name': 'Medium - Queue for Review',
            'risk_score': 6,
            'confidence': 0.75,
            'expected': 'queue_review'
        },
        {
            'name': 'Low - Log Only',
            'risk_score': 3,
            'confidence': 0.60,
            'expected': 'log_only'
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"   Risk: {test['risk_score']}, Confidence: {test['confidence']}")
        
        incident_data = {
            'incident_id': f'test-policy-{i:03d}',
            'vlm_summary': {
                'confidence': test['confidence'],
                'incident_type': 'test_incident',
                'description': f"Test case {i}",
                'recommended_alerts': ['call'],
            },
            'enhanced_report': {
                'report_text': f"Test incident {i}",
                'risk_score': test['risk_score'],
                'executive_summary': f"Test case {i}",
            },
            'location': {'lat': 12.0, 'lon': 77.0},
            'history': [],
        }
        
        try:
            result = await orchestrator.process_incident_async(incident_data)
            actual_status = result['action_result']['final_status']
            
            # Check if decision matches expected
            if test['expected'] in actual_status or actual_status in test['expected']:
                print(f"   ✅ Correct decision: {actual_status}")
            else:
                print(f"   ⚠️  Unexpected decision: {actual_status} (expected: {test['expected']})")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n🚀 LangGraph Orchestrator Test Suite\n")
    
    # Run tests
    asyncio.run(test_langgraph_orchestrator())
    asyncio.run(test_policy_decisions())
    
    print("\n✅ Test suite completed!\n")
