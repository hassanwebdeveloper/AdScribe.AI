from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from fastapi.responses import Response, JSONResponse
from app.core.deps import get_current_user
from app.models.user import User
from ..core.database import get_database
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
):
    """
    Generate a faceted scatter plot of ad performance segments
    """
    try:
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
                "revenue": "Revenue ($)",
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
                x=0.5
            ),
            margin=dict(l=100, r=40, t=80, b=80),
        )

        for annotation in fig.layout.annotations:
            if "fatigue_risk=" in annotation.text:
                annotation.text = f"Fatigue Risk: {annotation.text.split('=')[-1]}"
                annotation.font.size = 13
            elif "engagement_type=" in annotation.text:
                annotation.text = annotation.text.split('=')[-1]
                annotation.font.size = 12

        fig.update_xaxes(title_text="Date", tickformat="%b %d")
        fig.update_yaxes(title_text="Revenue ($)")

        return {"figure": fig.to_json()}

    except Exception as e:
        logger.error(f"Failed to generate visualization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate visualization: {str(e)}")