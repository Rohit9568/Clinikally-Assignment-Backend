
from sqlalchemy.orm import Session
from sqlalchemy import func, extract 
from statistics import mean
from datetime import datetime, timedelta
from typing import List, Optional, Dict 
from collections import Counter 

from . import models, schemas, auth, utils 

RECOMMENDATION_EXPIRY_DAYS = 7  

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    user = get_user_by_username(db, username)
    if not user or not auth.verify_password(password, user.hashed_password):
        return None
    return user

def create_doctor(db: Session, doctor: schemas.DoctorCreate) -> models.Doctor:
   
    db_doctor = models.Doctor(**doctor.model_dump())
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    return db_doctor

def get_doctor(db: Session, doctor_id: int) -> Optional[models.Doctor]:
    return db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()

def get_doctors_by_rating(
    db: Session, min_rating: float = 0.0, skip: int = 0, limit: int = 10
) -> List[models.Doctor]:
    return (
        db.query(models.Doctor)
        .filter(models.Doctor.average_rating >= min_rating)
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_review(
    db: Session, review: schemas.ReviewCreate, doctor_id: int, user_id: int
) -> models.Review:
    db_review = models.Review(
        **review.model_dump(), doctor_id=doctor_id, user_id=user_id
    )
    db.add(db_review)
    db.commit()
    
    doctor = get_doctor(db, doctor_id)
    if doctor:
        all_ratings_for_doctor = [r.rating for r in doctor.reviews]
        if all_ratings_for_doctor:
            doctor.average_rating = round(mean(all_ratings_for_doctor), 2)
        else:
            doctor.average_rating = 0.0
        db.commit()
        db.refresh(doctor)

    db.refresh(db_review)
    return db_review

def create_recommendation(
    db: Session, rec_data: schemas.RecommendationCreate, doctor_id: int
  
) -> models.Recommendation:
    
    expires_at_value = datetime.utcnow() + timedelta(days=RECOMMENDATION_EXPIRY_DAYS)
    
    db_recommendation = models.Recommendation(
        doctor_id=doctor_id,
      
        notes=rec_data.notes,
        expires_at=expires_at_value,
        timestamp=datetime.utcnow()
    )
    db.add(db_recommendation)
    db.commit()

    for prod_input in rec_data.products:
        link_entry = models.ProductRecommendationLink(
            recommendation_id=db_recommendation.id,
            product_id=prod_input.product_id
        )
        db.add(link_entry)
    
    db.commit()
    db.refresh(db_recommendation)
    return db_recommendation

def get_recommendation_by_uuid(db: Session, uuid_str: str) -> Optional[models.Recommendation]:
    recommendation = db.query(models.Recommendation).filter(models.Recommendation.uuid == uuid_str).first()
    if not recommendation:
        return None
    
    if recommendation.expires_at and recommendation.expires_at < datetime.utcnow():
        return None  
    
    return recommendation


def get_doctor_profile_by_user_id(db: Session, user_id: int) -> Optional[models.Doctor]:
    """Fetches a doctor's profile linked to a user ID."""
    return db.query(models.Doctor).filter(models.Doctor.user_id == user_id).first()

def calculate_rating_trends(db: Session, doctor_id: int) -> List[schemas.RatingTrendPoint]:
    """Calculates monthly average ratings for a doctor."""
    trends_data = (
        db.query(
            extract('year', models.Review.timestamp).label('year'),
            extract('month', models.Review.timestamp).label('month'),
            func.avg(models.Review.rating).label('average_rating'),
            func.count(models.Review.id).label('total_ratings')
        )
        .filter(models.Review.doctor_id == doctor_id)
        .group_by(extract('year', models.Review.timestamp), extract('month', models.Review.timestamp)) # Group by the expressions
        .order_by(extract('year', models.Review.timestamp), extract('month', models.Review.timestamp)) # Order by the expressions
        .all()
    )
    
    trends = []
    for row in trends_data:
        
        year_val = row.year if hasattr(row, 'year') else None
        month_val = row.month if hasattr(row, 'month') else None
        avg_rating_val = row.average_rating if hasattr(row, 'average_rating') else 0.0
        total_ratings_val = row.total_ratings if hasattr(row, 'total_ratings') else 0

        if year_val is not None and month_val is not None:
            period_str = f"{int(year_val)}-{int(month_val):02d}"
            trends.append(
                schemas.RatingTrendPoint(
                    period=period_str,
                    average_rating=round(float(avg_rating_val), 2) if avg_rating_val else 0.0,
                    total_ratings=int(total_ratings_val)
                )
            )
    return trends

def get_top_recommended_products(db: Session, doctor_id: int, limit: int = 5) -> List[schemas.FrequentlyRecommendedProduct]:
    """Gets the most frequently recommended products by a doctor."""
    product_counts_query = (
        db.query(
            models.ProductRecommendationLink.product_id,
            func.count(models.ProductRecommendationLink.product_id).label('recommendation_count') 
        )
        .join(models.Recommendation, models.ProductRecommendationLink.recommendation_id == models.Recommendation.id)
        .filter(models.Recommendation.doctor_id == doctor_id)
        .group_by(models.ProductRecommendationLink.product_id)
        .order_by(func.count(models.ProductRecommendationLink.product_id).desc())
        .limit(limit)
        .all()
    )

    top_products = []
    
    for row in product_counts_query: 
        prod_id = row.product_id
        count = row.recommendation_count
        
        product_details = utils.fetch_product_details_by_id(prod_id)
        title = product_details.title if product_details else f"Product ID {prod_id}"
        top_products.append(
            schemas.FrequentlyRecommendedProduct(
                product_id=prod_id,
                product_title=title,
                recommendation_count=count
            )
        )
    return top_products

def _simple_sentiment_analyzer(text: str) -> str:
    """Extremely basic keyword-based sentiment analyzer."""
    if not text: 
        return "neutral"
    text_lower = text.lower()
   
    positive_keywords = ["good", "great", "excellent", "fantastic", "helpful", "positive", "love", "best", "amazing", "satisfied", "recommend", "pleased", "impressed", "wonderful", "effective"]
    negative_keywords = ["bad", "poor", "terrible", "awful", "negative", "hate", "worst", "avoid", "disappointed", "unhelpful", "rush", "problem", "issue", "concern", "not good"]

    positive_score = sum(1 for keyword in positive_keywords if keyword in text_lower)
    negative_score = sum(1 for keyword in negative_keywords if keyword in text_lower)

    if positive_score > negative_score:
        return "positive"
    elif negative_score > positive_score:
        return "negative"
    else:
      
        return "neutral"

def analyze_review_sentiments(db: Session, doctor_id: int) -> schemas.SentimentBreakdown:
    """Analyzes the sentiment of reviews for a doctor."""
 
    reviews_comments = db.query(models.Review.comment).filter(
        models.Review.doctor_id == doctor_id,
        models.Review.comment.isnot(None), 
        models.Review.comment != ""        
    ).all()
    
    sentiments = {"positive": 0, "neutral": 0, "negative": 0}
    total_analyzed = 0

    for review_tuple in reviews_comments:
        comment = review_tuple[0]
    
        if comment and comment.strip(): 
            sentiment = _simple_sentiment_analyzer(comment)
            sentiments[sentiment] += 1
            total_analyzed += 1
            
    positive_perc = (sentiments["positive"] / total_analyzed * 100) if total_analyzed > 0 else 0.0
    neutral_perc = (sentiments["neutral"] / total_analyzed * 100) if total_analyzed > 0 else 0.0
    negative_perc = (sentiments["negative"] / total_analyzed * 100) if total_analyzed > 0 else 0.0

    return schemas.SentimentBreakdown(
        positive_reviews=sentiments["positive"],
        neutral_reviews=sentiments["neutral"],
        negative_reviews=sentiments["negative"],
        total_analyzed=total_analyzed,
        positive_percentage=round(positive_perc, 2),
        neutral_percentage=round(neutral_perc, 2),
        negative_percentage=round(negative_perc, 2)
    )

def get_doctor_overall_stats(db: Session, doctor_id: int) -> tuple[float, int, int, int]:
    """Helper to get overall rating, total reviews, and recommendation counts."""
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        return 0.0, 0, 0, 0

    overall_average_rating = doctor.average_rating if doctor.average_rating is not None else 0.0
    
   
    total_reviews = db.query(func.count(models.Review.id)).filter(models.Review.doctor_id == doctor_id).scalar() or 0
    
    total_recommendations_made = db.query(func.count(models.Recommendation.id)).filter(models.Recommendation.doctor_id == doctor_id).scalar() or 0
    
    total_products_recommended = (
        db.query(func.count(models.ProductRecommendationLink.id))
        .join(models.Recommendation, models.ProductRecommendationLink.recommendation_id == models.Recommendation.id)
        .filter(models.Recommendation.doctor_id == doctor_id)
        .scalar() or 0
    )
    return overall_average_rating, total_reviews, total_recommendations_made, total_products_recommended
