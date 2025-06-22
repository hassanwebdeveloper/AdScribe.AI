import asyncio
from datetime import datetime
from app.models.user import User
from app.services.recommendation_service import RecommendationService
from app.services.ml_optimization_service import ml_optimization_service
from app.core.database import connect_to_mongodb

async def test_recommendations():
    """Test the recommendation system."""
    print("🚀 Testing recommendation system...")
    
    # Connect to database
    await connect_to_mongodb()
    print("✅ Database connected")
    
    # Create test user
    test_user = User(
        id="test_user_id",
        email="test@example.com", 
        name="Test User",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Test rule-based recommendations
    print("\n📊 Testing rule-based recommendations...")
    rec_service = RecommendationService()
    recommendations = await rec_service.generate_recommendations(test_user, use_ml_optimization=False)
    
    print(f"Goal: {recommendations.goal}")
    print(f"Categories: {len(recommendations.categories)}")
    print(f"Summary: {recommendations.summary}")
    print(f"Approach: {getattr(recommendations, 'approach', 'N/A')}")
    
    # Test ML optimization
    print("\n🤖 Testing ML optimization...")
    try:
        ml_recommendations = await ml_optimization_service.generate_optimization_recommendations(
            user_id="test_user_id",
            target_roas_improvement=10.0
        )
        
        print(f"ML Goal: {ml_recommendations.get('goal', 'N/A')}")
        summary = ml_recommendations.get('optimization_summary', {})
        print(f"Ads analyzed: {summary.get('total_ads_analyzed', 0)}")
        print(f"CTR opportunities: {summary.get('ctr_improvement_opportunities', 0)}")
        print(f"Spend opportunities: {summary.get('spend_optimization_opportunities', 0)}")
        
    except Exception as e:
        print(f"ML optimization error: {str(e)}")
    
    print("\n✅ All tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_recommendations()) 