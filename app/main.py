from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Annotated
from uuid import UUID as PyUUID
from datetime import timedelta

from . import models
from .database import SessionLocal, engine, Base
from . import schemas, crud, auth, utils

app = FastAPI(
    title="Dermatologist Rating and Recommendation API",
    version="1.0.0",
    description="API for rating dermatologists and managing product recommendations."
)

@app.on_event("startup")
async def startup_event_handler():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[models.User, Depends(auth.get_current_user)]

@app.post("/api/v1/auth/token", response_model=schemas.Token, tags=["Authentication"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbDep
):
    user = crud.authenticate_user(db, username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/users/", response_model=schemas.User, status_code=status.HTTP_201_CREATED, tags=["Users"])
def create_new_user(user: schemas.UserCreate, db: DbDep):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/api/v1/users/me", response_model=schemas.User, tags=["Users"])
async def read_users_me(current_user: CurrentUserDep):
    return current_user

@app.post("/api/v1/doctors/", response_model=schemas.DoctorOut, status_code=status.HTTP_201_CREATED, tags=["Doctors"])
def create_new_doctor(
    doctor_data: schemas.DoctorCreate,
    db: DbDep,
    current_user: CurrentUserDep
):
    existing_doctor_profile = crud.get_doctor_profile_by_user_id(db, user_id=current_user.id)
    if existing_doctor_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user account is already linked to a doctor profile."
        )
    db_doctor_model_instance = models.Doctor(
        **doctor_data.model_dump(),
        user_id=current_user.id
    )
    db.add(db_doctor_model_instance)
    db.commit()
    db.refresh(db_doctor_model_instance)
    return schemas.DoctorOut(
        id=db_doctor_model_instance.id,
        name=db_doctor_model_instance.name,
        specialization=db_doctor_model_instance.specialization,
        average_rating=db_doctor_model_instance.average_rating,
        reviews=[]
    )

@app.get("/api/v1/doctors/", response_model=List[schemas.DoctorOut], tags=["Doctors"])
def get_all_doctors(
    db: DbDep,
    min_rating: float = 0.0,
    skip: int = 0,
    limit: int = 10
):
    doctors_db = crud.get_doctors_by_rating(db, min_rating=min_rating, skip=skip, limit=limit)
    results = []
    for doc in doctors_db:
        reviews_out = [schemas.ReviewOut.model_validate(rev) for rev in doc.reviews]
        doc_out = schemas.DoctorOut(
            id=doc.id,
            name=doc.name,
            specialization=doc.specialization,
            average_rating=doc.average_rating,
            reviews=reviews_out
        )
        results.append(doc_out)
    return results

@app.get("/api/v1/doctors/{doctor_id}", response_model=schemas.DoctorOut, tags=["Doctors"])
def get_doctor_details(doctor_id: int, db: DbDep):
    doctor = crud.get_doctor(db, doctor_id=doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    reviews_out = [schemas.ReviewOut.model_validate(rev) for rev in doctor.reviews]
    return schemas.DoctorOut(
        id=doctor.id,
        name=doctor.name,
        specialization=doctor.specialization,
        average_rating=doctor.average_rating,
        reviews=reviews_out
    )

@app.post("/api/v1/doctors/{doctor_id}/reviews", response_model=schemas.ReviewOut, status_code=status.HTTP_201_CREATED, tags=["Reviews"])
def create_doctor_review(
    doctor_id: int,
    review: schemas.ReviewCreate,
    db: DbDep,
    current_user: CurrentUserDep
):
    doctor = crud.get_doctor(db, doctor_id=doctor_id)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return crud.create_review(db=db, review=review, doctor_id=doctor_id, user_id=current_user.id)

@app.post("/api/v1/doctors/{doctor_id}/recommendations", response_model=schemas.RecommendationOut, status_code=status.HTTP_201_CREATED, tags=["Recommendations"])
def create_new_recommendation(
    doctor_id: int,
    recommendation_data: schemas.RecommendationCreate,
    db: DbDep,
    current_user: CurrentUserDep
):
    doctor = crud.get_doctor(db, doctor_id=doctor_id)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    db_recommendation = crud.create_recommendation(
        db=db,
        rec_data=recommendation_data,
        doctor_id=doctor_id
    )
    product_details_list: List[schemas.ProductDetail] = []
    for prod_link in db_recommendation.products_in_recommendation:
        details = utils.fetch_product_details_by_id(prod_link.product_id)
        if details:
            product_details_list.append(details)
        else:
            print(f"Warning: Could not fetch details for product_id {prod_link.product_id}")
    return schemas.RecommendationOut(
        uuid=PyUUID(db_recommendation.uuid),
        doctor_id=db_recommendation.doctor_id,
        notes=db_recommendation.notes,
        timestamp=db_recommendation.timestamp,
        expires_at=db_recommendation.expires_at,
        products=product_details_list
    )

@app.get("/api/v1/recommendations/{recommendation_uuid}", response_model=schemas.RecommendationOut, tags=["Recommendations"])
def get_public_recommendation(recommendation_uuid: PyUUID, db: DbDep):
    db_recommendation = crud.get_recommendation_by_uuid(db, uuid_str=str(recommendation_uuid))
    if not db_recommendation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found or has expired")
    product_details_list: List[schemas.ProductDetail] = []
    for prod_link in db_recommendation.products_in_recommendation:
        details = utils.fetch_product_details_by_id(prod_link.product_id)
        if details:
            product_details_list.append(details)
        else:
            print(f"Warning: Could not fetch details for product_id {prod_link.product_id}")
    return schemas.RecommendationOut(
        uuid=PyUUID(db_recommendation.uuid),
        doctor_id=db_recommendation.doctor_id,
        notes=db_recommendation.notes,
        timestamp=db_recommendation.timestamp,
        expires_at=db_recommendation.expires_at,
        products=product_details_list
    )

# --- Doctor Analytics Endpoint ---
@app.get("/api/v1/doctors/analytics/me", response_model=schemas.DoctorAnalyticsData, tags=["Doctors Analytics"])
async def get_my_doctor_analytics(
    db: DbDep,
    current_user: CurrentUserDep
):
    doctor_profile = crud.get_doctor_profile_by_user_id(db, user_id=current_user.id)
    if not doctor_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found for the authenticated user. Ensure your user account is linked to a doctor profile."
        )
    doctor_id = doctor_profile.id
    overall_avg, total_rev, total_reco_events, total_prods_reco = crud.get_doctor_overall_stats(db, doctor_id=doctor_id)
    rating_trends = crud.calculate_rating_trends(db, doctor_id=doctor_id)
    top_products = crud.get_top_recommended_products(db, doctor_id=doctor_id, limit=5)
    sentiment_breakdown = crud.analyze_review_sentiments(db, doctor_id=doctor_id)
    return schemas.DoctorAnalyticsData(
        overall_average_rating=overall_avg,
        total_reviews=total_rev,
        total_recommendations_made=total_reco_events,
        total_products_recommended=total_prods_reco,
        rating_trends=rating_trends,
        top_recommended_products=top_products,
        review_sentiment_breakdown=sentiment_breakdown
    )

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Dermatologist API. Visit /docs for API documentation."}