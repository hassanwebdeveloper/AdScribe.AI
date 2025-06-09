"""
Test script for the Ad Script Generator Agent

This script tests the refactored agent with dynamic classification and separate nodes.
"""

import asyncio
import json
from Ad_Script_Generator_Agent import AdScriptGeneratorAgent

async def test_default_classification():
    """Test the agent with default classification classes"""
    
    print("=== Testing Default Classification Classes ===\n")
    
    # Create agent with default classes
    agent = AdScriptGeneratorAgent()
    
    print("Default classification classes:")
    for class_name, description in agent.classification_classes.items():
        print(f"  {class_name}: {description}")
    print()
    
    # Test ad script generation query
    print("Testing ad script generation classification...")
    response = await agent.process_request(
        user_message="Please write new ad script for my new oud",
        previous_messages=[],
        ad_analyses=[]
    )
    print(f"Classification: {response['classification']}")
    print(f"Response preview: {response['output'][:100]}...")
    print()
    
    # Test general query
    print("Testing general query classification...")
    response = await agent.process_request(
        user_message="What is the weather like today?",
        previous_messages=[],
        ad_analyses=[]
    )
    print(f"Classification: {response['classification']}")
    print(f"Response preview: {response['output'][:100]}...")
    print()

async def test_custom_classification():
    """Test the agent with custom classification classes"""
    
    print("=== Testing Custom Classification Classes ===\n")
    
    # Create custom classification classes
    custom_classes = {
        "ad_script": "If user wants to write new ad speech or video script or text but not code.",
        "product_help": "If user asks for help with product features or usage instructions",
        "default": "it is default category all remaining query should lie under this category"
    }
    
    # Create agent with custom classes
    agent = AdScriptGeneratorAgent(custom_classes)
    
    print("Custom classification classes:")
    for class_name, description in agent.classification_classes.items():
        print(f"  {class_name}: {description}")
    print()
    
    # Test different types of queries
    test_queries = [
        "Please tell me how can i create my new ad for my portable fan",
        "How do I use the scheduling feature?",
        "What's the capital of France?"
    ]
    
    for query in test_queries:
        print(f"Testing query: '{query}'")
        response = await agent.process_request(
            user_message=query,
            previous_messages=[],
            ad_analyses=[]
        )
        print(f"Classification: {response['classification']}")
        print(f"Response preview: {response['output'][:100]}...")
        print()

async def test_ad_script_generation_with_data():
    """Test ad script generation with sample data"""
    
    print("=== Testing Ad Script Generation with Data ===\n")
    
    agent = AdScriptGeneratorAgent()
    
    # Sample ad analysis data
    sample_ad_analyses = [
        {
            "video_title": "Best Oud Perfume 2024",
            "audio_description": "Traditional oud music with narrator explaining the rich fragrance",
            "video_description": "Person applying oud perfume, elegant packaging showcase, satisfied customers",
            "metrics": {
                "roas": 5.2,
                "ctr": 3.1,
                "conversions": 200,
                "revenue": 8000
            }
        }
    ]
    
    response = await agent.process_request(
        user_message="Please write new ad script for my new oud",
        previous_messages=[],
        ad_analyses=sample_ad_analyses
    )
    
    print(f"Classification: {response['classification']}")
    print(f"Success: {response['success']}")
    print("Generated Ad Script:")
    print("=" * 50)
    print(response['output'])
    print("=" * 50)
    print()

async def test_dynamic_class_update():
    """Test dynamic updating of classification classes"""
    
    print("=== Testing Dynamic Classification Update ===\n")
    
    agent = AdScriptGeneratorAgent()
    
    print("Initial classes:")
    for class_name, description in agent.classification_classes.items():
        print(f"  {class_name}: {description}")
    print()
    
    # Update classification classes
    new_classes = {
        "ad_script": "If user wants to write new ad speech or video script or text but not code.",
        "analytics": "If user asks about metrics, performance data, or analytics",
        "support": "If user needs technical support or troubleshooting help",
        "default": "it is default category all remaining query should lie under this category"
    }
    
    agent.update_classification_classes(new_classes)
    
    print("Updated classes:")
    for class_name, description in agent.classification_classes.items():
        print(f"  {class_name}: {description}")
    print()
    
    # Test with new classification
    test_queries = [
        "Show me the ROAS data for last month",
        "I need help with login issues",
        "Create an ad script for perfume"
    ]
    
    for query in test_queries:
        print(f"Testing: '{query}'")
        response = await agent.process_request(
            user_message=query,
            previous_messages=[],
            ad_analyses=[]
        )
        print(f"Classification: {response['classification']}")
        print()

async def main():
    """Run all tests"""
    print("Starting Ad Script Generator Agent Tests...\n")
    
    try:
        await test_default_classification()
        await test_custom_classification()
        await test_ad_script_generation_with_data()
        await test_dynamic_class_update()
        print("All tests completed successfully!")
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())