"""
Recommendation Service for AdScribe.AI

This service generates ROAS-focused recommendations using both:
1. ML-based optimization approach (primary)
2. Rule-based approach (fallback)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from app.core.database import get_database
from app.models.recommendation import (
    AdRecommendation, 
    CreativeMetadata, 
    PerformanceMetrics, 
    RecommendationAction, 
    AIRecommendation,
    RecommendationGoal,
    RecommendationType,
    CreativePattern,
    RecommendationResponse, 
    RecommendationCategory, 
    Recommendation
)
from app.models.user import User
from app.services.openai_service import openai_service
from app.services.ml_optimization_service import ml_optimization_service
import asyncio
from bson import ObjectId

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Service for generating ROAS improvement recommendations.
    
    Uses ML optimization as primary approach with rule-based fallback.
    """
    
    def __init__(self):
        # Use the existing global OpenAI service instance
        self.openai_service = openai_service
        self.db = None
    
    async def generate_recommendations(
        self, 
        user: Union[User, str], 
        use_ml_optimization: bool = True
    ) -> RecommendationResponse:
        """
        Generate comprehensive ROAS improvement recommendations.
        
        Args:
            user: User object or user ID string
            use_ml_optimization: Whether to use ML optimization approach (default: True)
            
        Returns:
            RecommendationResponse with structured recommendations
        """
        # Handle both User objects and strings
        if isinstance(user, str):
            user_id = user
            # Create minimal User object for compatibility
            user = User(
                id=user_id,
                email=f"{user_id}@temp.com",
                name="Temp User",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        else:
            user_id = user.id
        
        logger.info(f"Generating recommendations for user {user_id}, ML optimization: {use_ml_optimization}")
        
        try:
            if use_ml_optimization:
                # Primary approach: ML-based optimization
                ml_recommendations = await ml_optimization_service.generate_optimization_recommendations(
                    user_id=user_id,
                    target_roas_improvement=10.0
                )
                
                # Check if ML optimization was successful
                if ml_recommendations.get("optimization_summary", {}).get("total_ads_analyzed", 0) > 0:
                    logger.info("Using ML optimization recommendations")
                    return await self._format_ml_recommendations(ml_recommendations, user_id)
                else:
                    logger.info("ML optimization insufficient, falling back to rule-based approach")
                    use_ml_optimization = False
            
            if not use_ml_optimization:
                # Fallback approach: Rule-based recommendations
                logger.info("Using rule-based recommendations")
                return await self._generate_rule_based_recommendations(user_id)
                
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            # Emergency fallback
            return await self._generate_emergency_fallback(user_id, str(e))
    
    async def _format_ml_recommendations(
        self, 
        ml_recommendations: Dict[str, Any], 
        user_id: str
    ) -> RecommendationResponse:
        """Format ML optimization results into structured recommendation response."""
        
        categories = []
        summary_stats = {
            "total_opportunities": 0,
            "potential_roas_improvement": 0,
            "ads_analyzed": ml_recommendations.get("optimization_summary", {}).get("total_ads_analyzed", 0)
        }
        
        # Process CTR improvement recommendations
        if "ctr_improvements" in ml_recommendations:
            ctr_data = ml_recommendations["ctr_improvements"]
            ctr_recommendations = []
            
            for rec in ctr_data.get("recommendations", []):
                ctr_recommendations.append(Recommendation(
                    title=f"Increase CTR for {rec['ad_name']}",
                    description=rec["optimization_goal"],
                    impact="High",
                    effort="Medium",
                    details={
                        "current_performance": rec["current_performance"],
                        "target_performance": rec["target_performance"],
                        "current_creative": rec["current_creative"],
                        "ai_optimized_creative": rec["ai_optimized_creative"],
                        "implementation_strategy": rec["implementation_strategy"],
                        "expected_improvement": rec["expected_roas_improvement"]
                    }
                ))
            
            if ctr_recommendations:
                categories.append(RecommendationCategory(
                    name="Creative Improvements",
                    description=ctr_data["description"],
                    recommendations=ctr_recommendations,
                    priority="High"
                ))
                summary_stats["total_opportunities"] += len(ctr_recommendations)
        
        # Process spend optimization recommendations
        if "spend_optimizations" in ml_recommendations:
            spend_data = ml_recommendations["spend_optimizations"]
            spend_recommendations = []
            
            for rec in spend_data.get("recommendations", []):
                action_type = rec["action"]
                title = f"{action_type} Spend: {rec['ad_name']}"
                
                spend_recommendations.append(Recommendation(
                    title=title,
                    description=f"{action_type} from {rec['current_daily_spend']} to {rec['recommended_daily_spend']}",
                    impact="High" if action_type == "Scale Up" else "Medium",
                    effort="Low",
                    details={
                        "action": rec["action"],
                        "current_spend": rec["current_daily_spend"],
                        "recommended_spend": rec["recommended_daily_spend"],
                        "change_percentage": rec.get("increase_percentage", rec.get("decrease_percentage", "0%")),
                        "reasoning": rec["reasoning"],
                        "expected_improvement": rec["expected_roas_improvement"],
                        "risk_level": rec.get("risk_level", "Medium"),
                        "monitoring_period": rec.get("monitoring_period", "7 days")
                    }
                ))
            
            if spend_recommendations:
                categories.append(RecommendationCategory(
                    name="Scale Opportunities",
                    description=spend_data["description"],
                    recommendations=spend_recommendations,
                    priority="High"
                ))
                summary_stats["total_opportunities"] += len(spend_recommendations)
        
        # Process efficiency improvement recommendations
        if "efficiency_improvements" in ml_recommendations:
            efficiency_data = ml_recommendations["efficiency_improvements"]
            efficiency_recommendations = []
            
            for rec in efficiency_data.get("recommendations", []):
                efficiency_recommendations.append(Recommendation(
                    title=f"Improve {rec['optimization_metric']}: {rec['ad_name']}",
                    description=f"Reduce {rec['optimization_metric']} by {rec['improvement_needed']}",
                    impact="Medium",
                    effort="Medium",
                    details={
                        "metric": rec["optimization_metric"],
                        "current_value": rec["current_value"],
                        "target_value": rec["target_value"],
                        "improvement_needed": rec["improvement_needed"],
                        "strategies": rec["optimization_strategies"],
                        "expected_improvement": rec["expected_roas_improvement"]
                    }
                ))
            
            if efficiency_recommendations:
                categories.append(RecommendationCategory(
                    name="Efficiency Improvements",
                    description=efficiency_data["description"],
                    recommendations=efficiency_recommendations,
                    priority="Medium"
                ))
                summary_stats["total_opportunities"] += len(efficiency_recommendations)
        
        # Process conversion improvement recommendations
        if "conversion_improvements" in ml_recommendations:
            conversion_data = ml_recommendations["conversion_improvements"]
            conversion_recommendations = []
            
            for rec in conversion_data.get("recommendations", []):
                conversion_recommendations.append(Recommendation(
                    title=f"Improve Conversions: {rec['ad_name']}",
                    description=f"Increase conversions by {rec['improvement_needed']}",
                    impact="High",
                    effort="High",
                    details={
                        "current_conversions": rec["current_conversions"],
                        "target_conversions": rec["target_conversions"],
                        "improvement_needed": rec["improvement_needed"],
                        "strategies": rec["conversion_strategies"],
                        "expected_improvement": rec["expected_roas_improvement"]
                    }
                ))
            
            if conversion_recommendations:
                categories.append(RecommendationCategory(
                    name="Conversion Optimization",
                    description=conversion_data["description"],
                    recommendations=conversion_recommendations,
                    priority="High"
                ))
                summary_stats["total_opportunities"] += len(conversion_recommendations)
        
        # Calculate average potential improvement
        if summary_stats["total_opportunities"] > 0:
            avg_improvement = ml_recommendations.get("optimization_summary", {}).get("average_predicted_improvement", 0)
            summary_stats["potential_roas_improvement"] = f"{avg_improvement:.1f}%"
        
        return RecommendationResponse(
            goal=ml_recommendations.get("goal", "Improve ROAS by 10%"),
            categories=categories,
            summary=summary_stats,
            generated_at=datetime.now(),
            approach="ML Optimization"
        )
    
    async def _generate_rule_based_recommendations(self, user_id: str) -> RecommendationResponse:
        """Generate rule-based recommendations as fallback."""
        logger.info(f"Generating rule-based recommendations for user {user_id}")
        
        # Get user's ad performance data
        ad_metrics = await self._get_user_ad_metrics(user_id)
        
        if not ad_metrics:
            return await self._generate_emergency_fallback(user_id, "No ad data found")
        
        # Analyze performance and generate recommendations
        categories = []
        
        # Creative improvements (low CTR, decent ROAS)
        creative_recs = await self._generate_creative_recommendations(ad_metrics, user_id)
        if creative_recs:
            categories.append(creative_recs)
        
        # Scale opportunities (high ROAS, good CTR)
        scale_recs = await self._generate_scale_recommendations(ad_metrics, user_id)
        if scale_recs:
            categories.append(scale_recs)
        
        # Pause recommendations (low ROAS)
        pause_recs = await self._generate_pause_recommendations(ad_metrics, user_id)
        if pause_recs:
            categories.append(pause_recs)
        
        total_opportunities = sum(len(cat.recommendations) for cat in categories)
        
        return RecommendationResponse(
            goal="Improve ROAS by 10%",
            categories=categories,
            summary={
                "total_opportunities": total_opportunities,
                "potential_roas_improvement": "8-15%",
                "ads_analyzed": len(ad_metrics)
            },
            generated_at=datetime.now(),
            approach="Rule-based Analysis"
        )
    
    async def _get_user_ad_metrics(self, user_id: str) -> List[Dict]:
        """Get user's ad performance metrics for analysis."""
        db = get_database()
        
        # Get last 30 days of data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "collected_at": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": "$ad_id",
                    "ad_name": {"$first": "$ad_name"},
                    "campaign_id": {"$first": "$campaign_id"},
                    "video_id": {"$first": "$video_id"},
                    "avg_spend": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.spend", 0]}}},
                    "avg_revenue": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.purchases_value", 0]}}},
                    "avg_clicks": {"$avg": {"$toInt": {"$ifNull": ["$additional_metrics.clicks", 0]}}},
                    "avg_impressions": {"$avg": {"$toInt": {"$ifNull": ["$additional_metrics.impressions", 0]}}},
                    "avg_purchases": {"$avg": {"$toInt": {"$ifNull": ["$purchases", 0]}}},
                    "avg_ctr": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.ctr", 0]}}},
                    "avg_cpc": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.cpc", 0]}}},
                    "avg_cpm": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.cpm", 0]}}},
                    "avg_roas": {"$avg": {"$toDouble": {"$ifNull": ["$additional_metrics.roas", 0]}}},
                    "data_points": {"$sum": 1}
                }
            },
            {
                "$match": {
                    "data_points": {"$gte": 2},  # At least 2 data points
                    "avg_spend": {"$gt": 5}      # Minimum spend
                }
            }
        ]
        
        results = await db.ad_metrics.aggregate(pipeline).to_list(length=1000)
        
        # Format results
        formatted_metrics = []
        for result in results:
            spend = float(result.get("avg_spend", 0))
            revenue = float(result.get("avg_revenue", 0))
            clicks = int(result.get("avg_clicks", 0))
            impressions = int(result.get("avg_impressions", 0))
            
            if spend > 0 and impressions > 0:
                roas = revenue / spend if spend > 0 else 0
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                
                formatted_metrics.append({
                    "ad_id": result["_id"],
                    "ad_name": result.get("ad_name", f"Ad {result['_id']}"),
                    "campaign_id": result.get("campaign_id"),
                    "video_id": result.get("video_id"),
                    "spend": spend,
                    "revenue": revenue,
                    "clicks": clicks,
                    "impressions": impressions,
                    "purchases": int(result.get("avg_purchases", 0)),
                    "ctr": ctr,
                    "cpc": float(result.get("avg_cpc", 0)),
                    "cpm": float(result.get("avg_cpm", 0)),
                    "roas": roas,
                    "data_points": result.get("data_points", 0)
                })
        
        logger.info(f"Retrieved {len(formatted_metrics)} ad metrics for rule-based analysis")
        return formatted_metrics
    
    async def _generate_creative_recommendations(self, ad_metrics: List[Dict], user_id: str) -> Optional[RecommendationCategory]:
        """Generate creative improvement recommendations."""
        # Find ads with low CTR but decent ROAS (0.5-2.0)
        creative_candidates = [
            ad for ad in ad_metrics 
            if 0.5 <= ad["roas"] <= 2.0 and ad["ctr"] < 1.5 and ad["impressions"] > 500
        ]
        
        if not creative_candidates:
            return None
        
        recommendations = []
        
        for ad in creative_candidates[:5]:  # Top 5 candidates
            # Get creative analysis if available
            creative_analysis = await self._get_creative_analysis(user_id, ad["ad_id"])
            
            recommendations.append(Recommendation(
                title=f"Improve Creative: {ad['ad_name']}",
                description=f"CTR {ad['ctr']:.2f}% is below 1.5% threshold. ROAS {ad['roas']:.2f} shows potential.",
                impact="High",
                effort="Medium",
                details={
                    "current_ctr": f"{ad['ctr']:.2f}%",
                    "current_roas": f"{ad['roas']:.2f}",
                    "target_ctr": "2.0%+",
                    "expected_roas_improvement": "15-25%",
                    "creative_analysis": creative_analysis,
                    "recommendations": [
                        "Test stronger hooks in first 3 seconds",
                        "Add urgency/scarcity elements",
                        "Improve visual storytelling",
                        "Test different CTAs"
                    ]
                }
            ))
        
        return RecommendationCategory(
            name="Creative Improvements",
            description=f"Optimize creative elements for {len(recommendations)} ads with improvement potential",
            recommendations=recommendations,
            priority="High"
        )
    
    async def _generate_scale_recommendations(self, ad_metrics: List[Dict], user_id: str) -> Optional[RecommendationCategory]:
        """Generate scaling recommendations."""
        # Find ads with high ROAS (>= 2.0) and good CTR (>= 1.5%)
        scale_candidates = [
            ad for ad in ad_metrics 
            if ad["roas"] >= 2.0 and ad["ctr"] >= 1.5 and ad["spend"] >= 20
        ]
        
        if not scale_candidates:
            return None
        
        recommendations = []
        
        for ad in scale_candidates[:5]:  # Top 5 candidates
            current_spend = ad["spend"]
            recommended_spend = current_spend * 1.5  # 50% increase
            
            recommendations.append(Recommendation(
                title=f"Scale Up: {ad['ad_name']}",
                description=f"High ROAS {ad['roas']:.2f} and CTR {ad['ctr']:.2f}% indicate scaling opportunity",
                impact="High",
                effort="Low",
                details={
                    "current_daily_spend": f"${current_spend:.2f}",
                    "recommended_daily_spend": f"${recommended_spend:.2f}",
                    "current_roas": f"{ad['roas']:.2f}",
                    "current_ctr": f"{ad['ctr']:.2f}%",
                    "scaling_confidence": "High",
                    "expected_additional_revenue": f"${(recommended_spend - current_spend) * ad['roas']:.2f}/day",
                    "monitoring_period": "7-10 days"
                }
            ))
        
        return RecommendationCategory(
            name="Scale Opportunities",
            description=f"Scale {len(recommendations)} high-performing ads to maximize returns",
            recommendations=recommendations,
            priority="High"
        )
    
    async def _generate_pause_recommendations(self, ad_metrics: List[Dict], user_id: str) -> Optional[RecommendationCategory]:
        """Generate pause recommendations."""
        # Find ads with low ROAS (< 0.8) and sufficient data
        pause_candidates = [
            ad for ad in ad_metrics 
            if ad["roas"] < 0.8 and ad["spend"] >= 50 and ad["data_points"] >= 5
        ]
        
        if not pause_candidates:
            return None
        
        recommendations = []
        
        for ad in pause_candidates[:3]:  # Top 3 candidates
            daily_loss = ad["spend"] - ad["revenue"]
            monthly_savings = daily_loss * 30
            
            recommendations.append(Recommendation(
                title=f"Consider Pausing: {ad['ad_name']}",
                description=f"Low ROAS {ad['roas']:.2f} is below 0.8 threshold after {ad['data_points']} days",
                impact="Medium",
                effort="Low",
                details={
                    "current_roas": f"{ad['roas']:.2f}",
                    "daily_spend": f"${ad['spend']:.2f}",
                    "daily_revenue": f"${ad['revenue']:.2f}",
                    "daily_loss": f"${daily_loss:.2f}",
                    "potential_monthly_savings": f"${monthly_savings:.2f}",
                    "data_points": ad["data_points"],
                    "alternative_actions": [
                        "Reduce spend by 50% and monitor",
                        "Test new creative variations",
                        "Adjust targeting parameters"
                    ]
                }
            ))
        
        return RecommendationCategory(
            name="Pause Recommendations",
            description=f"Consider pausing {len(recommendations)} underperforming ads",
            recommendations=recommendations,
            priority="Medium"
        )
    
    async def _get_creative_analysis(self, user_id: str, ad_id: str) -> Dict:
        """Get creative analysis for an ad."""
        db = get_database()
        
        analysis = await db.ad_analyses.find_one({
            "user_id": user_id,
            "$or": [
                {"ad_id": ad_id},
                {"campaign_id": ad_id}  # Fallback to campaign_id
            ]
        })
        
        if analysis and analysis.get("ad_analysis"):
            return analysis["ad_analysis"]
        
        return {
            "hook": "Unknown",
            "tone": "Unknown", 
            "visual": "Unknown",
            "power_phrases": "Unknown"
        }
    
    async def _generate_emergency_fallback(self, user_id: str, error_msg: str) -> RecommendationResponse:
        """Generate emergency fallback recommendations."""
        logger.warning(f"Using emergency fallback for user {user_id}: {error_msg}")
        
        fallback_recommendations = [
            Recommendation(
                title="Collect More Performance Data",
                description="Insufficient data for detailed analysis. Run ads for at least 1-2 weeks.",
                impact="High",
                effort="Low",
                details={
                    "minimum_spend": "$20/day per ad",
                    "minimum_duration": "7-14 days",
                    "minimum_impressions": "1000+ per ad"
                }
            ),
            Recommendation(
                title="Focus on Top Performers",
                description="Identify and scale your best-performing ads first.",
                impact="Medium",
                effort="Low",
                details={
                    "criteria": "ROAS > 2.0 and CTR > 1.5%",
                    "action": "Increase budget by 25-50%"
                }
            ),
            Recommendation(
                title="Test Creative Variations",
                description="Create A/B tests for ads with good ROAS but low CTR.",
                impact="Medium",
                effort="Medium",
                details={
                    "focus_areas": ["Hook", "Visual", "CTA", "Offer"],
                    "test_duration": "3-7 days per variation"
                }
            )
        ]
        
        return RecommendationResponse(
            goal="Improve ROAS by 10%",
            categories=[
                RecommendationCategory(
                    name="Basic Optimization",
                    description="Fundamental steps to improve ad performance",
                    recommendations=fallback_recommendations,
                    priority="High"
                )
            ],
            summary={
                "total_opportunities": len(fallback_recommendations),
                "potential_roas_improvement": "5-10%",
                "ads_analyzed": 0,
                "note": f"Limited analysis due to: {error_msg}"
            },
            generated_at=datetime.now(),
            approach="Emergency Fallback"
        )

# Create global instance
recommendation_service = RecommendationService() 