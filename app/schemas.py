
from pydantic import BaseModel, conint, constr, HttpUrl, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID as PyUUID



class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserInDBBase(UserBase):
    id: int
    
    class Config:
        from_attributes = True 

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase): 
    hashed_password: str



class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None



class ReviewBase(BaseModel):
    rating: conint(ge=1, le=5)
    comment: constr(max_length=700) 

class ReviewCreate(ReviewBase):
    pass 

class ReviewOut(ReviewBase):
    id: int
    doctor_id: int
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True



class DoctorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    specialization: str = Field(..., min_length=1, max_length=100)

class DoctorCreate(DoctorBase):
    pass

class DoctorOut(DoctorBase):
    id: int
    average_rating: float
    reviews: List[ReviewOut] = []

    class Config:
        from_attributes = True



class ProductIdInput(BaseModel): 
    product_id: int

class ProductDetail(BaseModel): 
    id: int
    title: str
    price: float
    description: str
    category: str
    image: HttpUrl 
    rating: Dict[str, Any]
    
    class Config:
        from_attributes = True



class RecommendationBase(BaseModel):
    
    notes: Optional[str] = None
    products: List[ProductIdInput] 

class RecommendationCreate(RecommendationBase):
   
    pass

class RecommendationOut(BaseModel):
    uuid: PyUUID 
    doctor_id: int
    
    notes: Optional[str]
    timestamp: datetime
    expires_at: Optional[datetime]
    products: List[ProductDetail] 

    class Config:
        from_attributes = True


class RatingTrendPoint(BaseModel):
    period: str 
    average_rating: float
    total_ratings: int

class FrequentlyRecommendedProduct(BaseModel):
    product_id: int
    product_title: Optional[str] = "Unknown Product" 
    recommendation_count: int

class SentimentBreakdown(BaseModel):
    positive_reviews: int
    neutral_reviews: int
    negative_reviews: int
    total_analyzed: int
    positive_percentage: float = 0.0
    neutral_percentage: float = 0.0
    negative_percentage: float = 0.0

class DoctorAnalyticsData(BaseModel):
    overall_average_rating: float
    total_reviews: int
    total_recommendations_made: int 
    total_products_recommended: int 
    rating_trends: List[RatingTrendPoint]
    top_recommended_products: List[FrequentlyRecommendedProduct]
    review_sentiment_breakdown: SentimentBreakdown        