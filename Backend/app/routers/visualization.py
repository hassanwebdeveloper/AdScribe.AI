from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from fastapi.responses import Response, JSONResponse
from app.core.deps import get_current_user
from app.models.user import User
from ..core.database import get_database, get_redis
from app.services.prediction_service import PredictionService
import pandas as pd
import numpy as np
import io
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import json
import base64
import itertools
import logging
from datetime import datetime

router = APIRouter(
    prefix="/visualization",
    tags=["visualization"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

@router.get("/ad-performance-segments")
async def get_ad_performance_segments(
    start_date: str = Query(..., description="Start date in format YYYY-MM-DD"),
    end_date: str = Query(..., description="End date in format YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    redis_client: Any = Depends(get_redis)
):
    """
    Generate a faceted scatter plot of ad performance segments
    """
    try:
        # Attempt to serve from cache for the exact date range
        cache_key = f"ad_perf_segments:{current_user.id}:{start_date}:{end_date}"

        cached = redis_client.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass  # proceed to recompute if cache corrupted

        prediction_service = PredictionService()
        user_id = str(current_user.id)
        user_ads = await prediction_service._get_user_ads(user_id)

        if not user_ads:
            return {"figure": None, "message": "No ads found for the selected date range"}

        all_metrics = []

        for ad in user_ads:
            ad_id = ad["ad_id"]
            ad_metrics = await prediction_service._get_ad_historical_metrics(
                user_id=user_id,
                ad_id=ad_id,
                start_date=start_date,
                end_date=end_date
            )

            for metric in ad_metrics:
                metric["ad_name"] = ad.get("ad_name", "Unknown Ad")
                metric["impressions"] = metric.get("impressions", 100)
                impressions = metric["impressions"]
                metric["reach"] = metric.get("reach", max(1, int(impressions / (1 + np.random.random() * 2))))

            all_metrics.extend(ad_metrics)

        if not all_metrics:
            return {"figure": None, "message": "No data available for the selected date range"}

        df = pd.DataFrame(all_metrics)

        required_fields = ['impressions', 'reach', 'ctr', 'cpc', 'roas', 'revenue']
        for field in required_fields:
            if field not in df.columns:
                default_values = {'impressions': 100, 'reach': 50, 'ctr': 1.0, 'cpc': 0.5, 'roas': 1.0, 'revenue': 0.0}
                df[field] = default_values[field]

        df = df.fillna({f: df[f].mean() if f in df else 0 for f in required_fields})

        # === Derived Categories ===
        df['fatigue_risk_ratio'] = df['impressions'] / df['reach']
        df['fatigue_risk'] = pd.cut(
            df['fatigue_risk_ratio'],
            bins=[0, 1.5, 3, float('inf')],
            labels=['Low', 'Moderate', 'High Fatigue Risk']
        )
        # Fill any NaN values (which fall outside defined bins) with a default category to avoid "Fatigue Risk: nan" facet
        df['fatigue_risk'] = df['fatigue_risk'].fillna('Low')

        high_ctr_threshold = 1.5
        high_cpc_threshold = 0.5
        df['high_ctr'] = df['ctr'] > high_ctr_threshold
        df['high_cpc'] = df['cpc'] > high_cpc_threshold

        df['engagement_type'] = np.select(
            [
                df['high_ctr'] & ~df['high_cpc'],
                df['high_ctr'] & df['high_cpc'],
                ~df['high_ctr'] & df['high_cpc'],
                ~df['high_ctr'] & ~df['high_cpc']
            ],
            [
                'High Engagement, Low Cost',
                'High Engagement, High Cost',
                'Low Engagement, High Cost',
                'Low Engagement, Low Cost'
            ],
            default='Low Engagement, Low Cost'
        )

        df['roas_classification'] = pd.cut(
            df['roas'],
            bins=[0, 0.95, 1.05, float('inf')],
            labels=['Unprofitable', 'Breakeven', 'Profitable']
        )

        # Ensure campaign_name column exists and sanitize ad_id type
        if 'campaign_name' not in df.columns:
            df['campaign_name'] = 'Unknown Campaign'
        df['ad_id'] = df['ad_id'].astype(str)        

        # === Ensure All Facets Exist ===
        engagement_types = [
            'High Engagement, Low Cost',
            'High Engagement, High Cost',
            'Low Engagement, High Cost',
            'Low Engagement, Low Cost'
        ]
        fatigue_risks = ['Low', 'Moderate', 'High Fatigue Risk']

        df['engagement_type'] = pd.Categorical(df['engagement_type'], categories=engagement_types)
        df['fatigue_risk'] = pd.Categorical(df['fatigue_risk'], categories=fatigue_risks)
        df['roas_classification'] = pd.Categorical(
            df['roas_classification'],
            categories=['Profitable', 'Breakeven', 'Unprofitable']
        )

        #handle nan values of roas_classification
        df['roas_classification'] = df['roas_classification'].fillna('Unprofitable')

        # Prepare segment information to return (one entry per ad per day)
        segment_data = df[
            [
                'ad_id', 'ad_name', 'campaign_name', 'date',
                'engagement_type', 'fatigue_risk', 'roas_classification',
                'revenue', 'ctr', 'roas', 'impressions', 'reach', 'cpc'
            ]
        ].copy()
        # Ensure dates are JSON serialisable strings
        segment_data['date'] = segment_data['date'].astype(str)
        # Replace NaN with None for JSON serialisation
        segment_data = segment_data.where(pd.notnull(segment_data), None)
        segments = segment_data.to_dict(orient='records')

        facet_combinations = pd.DataFrame(
            list(itertools.product(engagement_types, fatigue_risks)),
            columns=['engagement_type', 'fatigue_risk']
        )

        placeholder_date = pd.to_datetime(datetime.utcnow().date())
        placeholder_data = {
            'date': placeholder_date,
            'revenue': 0,
            'ctr': 0,
            'roas': 0,
            'ad_name': 'No Data',
            'roas_classification': 'Unprofitable'
        }

        placeholder_df = facet_combinations.copy()
        for k, v in placeholder_data.items():
            placeholder_df[k] = v

        df_complete = pd.concat([df, placeholder_df], ignore_index=True)

        # No need for dummy point since there's already an unprofitable item visible
        # Just make sure all categories are included in the color parameter
        
        color_discrete_map = {
            'Profitable': '#4CAF50',
            'Breakeven': '#FFC107',
            'Unprofitable': '#F44336'
        }

        fig = px.scatter(
            df_complete,
            x="date",
            y="revenue",
            color="roas_classification",
            size="ctr",
            size_max=15,
            facet_row="engagement_type",
            facet_col="fatigue_risk",
            hover_name="ad_name",
            hover_data={
                "date": True,
                "revenue": ":.2f",
                "ctr": ":.2f",
                "roas": ":.2f",
                "roas_classification": True
            },
            color_discrete_map=color_discrete_map,
            category_orders={
                "fatigue_risk": fatigue_risks,
                "engagement_type": engagement_types,
                "roas_classification": ['Profitable', 'Breakeven', 'Unprofitable']
            },
            labels={
                "date": "Date",
                "revenue": "Revenue (Rs.)",
                "ctr": "CTR (%)",
                "roas_classification": "ROAS Classification"
            },
            height=1000,
            width=1100
        )

        fig.update_layout(
            legend_title="ROAS Classification",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                itemsizing='constant'  # Ensure consistent legend item sizes
            ),
            margin=dict(l=100, r=40, t=80, b=80),
            showlegend=True,
            # Hide modebar - use only valid properties
            modebar=dict(
                remove=["zoom", "pan", "select", "zoomIn", "zoomOut", "autoScale", 
                       "resetScale", "lasso2d", "toImage", "sendDataToCloud", 
                       "toggleSpikelines", "resetViewMapbox"]
            )
        )

        for annotation in fig.layout.annotations:
            if "fatigue_risk=" in annotation.text:
                annotation.text = f"Fatigue Risk: {annotation.text.split('=')[-1]}"
                annotation.font.size = 13
            elif "engagement_type=" in annotation.text:
                annotation.text = annotation.text.split('=')[-1]
                annotation.font.size = 12

        # Ensure only legend entries for visible circles are shown
        shown = set()
        def legend_visible(trace):
            # Check if trace has at least one visible marker
            has_visible = hasattr(trace, 'x') and trace.x is not None and len(trace.x) > 0 and len(trace.hovertext) > 0 and trace.hovertext[0] != 'No Data'
            if trace.name in shown or not has_visible:
                trace.showlegend = False
            else:
                shown.add(trace.name)
                trace.showlegend = True
        fig.for_each_trace(legend_visible)

        # Format x-axis to show only month and day (e.g., 'Jun 01')
        fig.update_xaxes(tickformat='%b %d')

        # Clear any default axis titles to avoid overlap
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None)
        
        # Add a single x-axis title in the bottom row, center column
        middle_col_idx = len(fatigue_risks) // 2
        bottom_row_idx = len(engagement_types) - 1
        
        # Add custom x-axis title in the bottom center
        fig.add_annotation(
            text="Date",
            x=0.5,  # Center of the figure
            y=-0.08,  # Below the bottom row
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=14),
            align="center"
        )
        
        # Add custom y-axis title in the middle left
        fig.add_annotation(
            text="Revenue (Rs.)",
            x=-0.08,  # Left of the leftmost column
            y=0.5,  # Middle of the figure
            xref="paper",
            yref="paper",
            showarrow=False,
            textangle=-90,  # Rotate for y-axis
            font=dict(size=14),
            align="center"
        )

        # Hide full modebar when displaying the plot in frontend
        config = {
            'displayModeBar': False,
            'staticPlot': False,
            'responsive': True
        }

        response_payload = {"figure": fig.to_json(), "config": config, "segments": segments}

        # Store in cache for 1 hour keyed by full date range
        try:
            redis_client.setex(cache_key, 3600, json.dumps(response_payload))
        except Exception as e:
            logger.warning(f"Failed to cache visualization data: {e}")

        return response_payload

    except Exception as e:
        logger.error(f"Failed to generate visualization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate visualization: {str(e)}")