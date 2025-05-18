
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime 
from uuid import uuid4 

from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
   
    doctor_profile = relationship("Doctor", back_populates="user_account", uselist=False, cascade="all, delete-orphan")

class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True) 
    
    name = Column(String, nullable=False)
    specialization = Column(String, nullable=False)
    average_rating = Column(Float, default=0.0)

    reviews = relationship("Review", back_populates="doctor", cascade="all, delete-orphan")
    recommendations_made = relationship("Recommendation", back_populates="doctor", cascade="all, delete-orphan")
    

    user_account = relationship("User", back_populates="doctor_profile")


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    rating = Column(Integer, nullable=False)
    comment = Column(Text) 
    timestamp = Column(DateTime, default=datetime.utcnow)

    doctor = relationship("Doctor", back_populates="reviews")
    user = relationship("User")

class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    doctor = relationship("Doctor", back_populates="recommendations_made")
    products_in_recommendation = relationship("ProductRecommendationLink", back_populates="recommendation", cascade="all, delete-orphan")

class ProductRecommendationLink(Base):
    __tablename__ = "product_recommendation_links"
    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=False)
    product_id = Column(Integer, nullable=False)

    recommendation = relationship("Recommendation", back_populates="products_in_recommendation")

