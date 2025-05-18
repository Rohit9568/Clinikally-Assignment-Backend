# Design Document: Dermatologist Rating & Recommendation API

**Version:** 1.1 (Updated with Analytics Feature)
**Date:** May 18, 2025

---

### 1. Architecture and Major Components 🏗️

The backend solution is a RESTful API developed using Python and the FastAPI framework, designed with a layered architecture to promote modularity, testability, and maintainability.

* **API Layer (`main.py`):** Serves as the primary interface for client applications. It defines HTTP endpoints, manages request routing, performs input validation using Pydantic schemas, and orchestrates responses by delegating business logic to the CRUD/service layer. FastAPI's capabilities provide automatic generation of interactive API documentation (Swagger UI & ReDoc).
* **CRUD/Service Layer (`crud.py`):** Encapsulates the core business logic and data manipulation operations (Create, Read, Update, Delete). This layer abstracts direct database interactions from the API endpoints. It includes logic for calculating average ratings, managing recommendation link expiry, and computing analytics for dermatologists.
* **Data Model Layer (`models.py`):** Defines the database schema using SQLAlchemy ORM models. These Python classes map to database tables (`User`, `Doctor`, `Review`, `Recommendation`, `ProductRecommendationLink`) and establish their attributes and interrelationships (e.g., foreign keys, relationships).
* **Schema Layer (`schemas.py`):** Contains Pydantic models that define the expected structure and data types for API request bodies and response payloads. This ensures robust data validation and clear API contracts.
* **Database Layer (`database.py`):** Configures the SQLAlchemy engine and session management for database connectivity. SQLite is utilized as the database engine, configured for a file-based database (`test.db`) to ensure stability and data persistence during development and testing. Database tables are initialized using a FastAPI `on_startup` event handler.
* **Authentication Module (`auth.py`):** Manages security through JWT-based authentication. Responsibilities include user password hashing (using bcrypt via passlib), access token generation upon successful login, and token verification for protecting API endpoints.
* **Utilities Module (`utils.py`):** Contains auxiliary functions, notably for interacting with the external dummy product API (`fakestoreapi.com`) to fetch product details.

---

### 2. Data Models and Their Relationships 🧬

The core entities and their key relationships are:

* **`User`**: Represents both patients/customers and system users (including those who are doctors).
    * Attributes: `id` (PK), `username` (unique), `hashed_password`.
    * Relationship: One-to-one with `Doctor` (via `doctor_profile` back-populating `user_account` on `Doctor`), allowing a user account to be linked to a specific doctor profile.
* **`Doctor`**: Represents dermatologist profiles.
    * Attributes: `id` (PK), `user_id` (FK to `User.id`, unique, nullable), `name`, `specialization`, `average_rating`.
    * Relationships: One-to-many with `Review` and `Recommendation`. One-to-one with `User` (via `user_account`).
* **`Review`**: Captures ratings and textual feedback.
    * Attributes: `id` (PK), `doctor_id` (FK to `Doctor`), `user_id` (FK to `User`), `rating` (1-5), `comment`, `timestamp`.
* **`Recommendation`**: Represents a set of product recommendations.
    * Attributes: `id` (PK), `uuid` (unique string for shareable link), `doctor_id` (FK to `Doctor`), `notes`, `timestamp`, `expires_at`.
    * Relationships: One-to-many with `ProductRecommendationLink`.
* **`ProductRecommendationLink`**: Links a recommendation to a specific product.
    * Attributes: `id` (PK), `recommendation_id` (FK to `Recommendation`), `product_id` (Integer ID from external API).

---

### 3. Key Decisions Made 💡

* **Technology Stack:** Python with FastAPI (for performance, Pydantic integration, auto-docs), SQLAlchemy (ORM), and SQLite (file-based `test.db` for development stability after issues with `:memory:` and Uvicorn's reloader).
* **Database Initialization:** Tables are created via `Base.metadata.create_all(bind=engine)` within a FastAPI `on_startup` event for reliable schema setup.
* **Data Validation:** Pydantic schemas enforce strict data validation for all API inputs and ensure consistent response structures.
* **Authentication:** JWT tokens are used for stateless authentication, with bcrypt for password hashing.
* **Doctor Analytics (`/analytics/me`):** This advanced feature was implemented to provide value to dermatologist users. It requires a `User` account to be linked to a `Doctor` profile (via `Doctor.user_id`). The endpoint then aggregates:
    * Rating trends (monthly average).
    * Top recommended products (names fetched from the dummy API).
    * A basic keyword-based sentiment analysis of reviews.
* **Shareable Recommendation Links:** Unique UUIDs are used for public recommendation links. Expiry is handled via an `expires_at` timestamp.
* **Average Rating Calculation:** Dynamically recalculated and stored on the `Doctor` model upon each new review submission for efficient querying.
* **Review Word Limit:** Approximated by a character limit (`constr(max_length=700)`) in Pydantic schemas for pragmatic API input validation.

---

### 4. Assumptions or Limitations 📝

* **Database Choice:** SQLite is used, making the system suitable for single-server deployment. It's not designed for high-concurrency, distributed environments without switching to a more robust RDBMS (e.g., PostgreSQL).
* **User-Doctor Linking:** The `/doctors/analytics/me` endpoint relies on a `User` account being linked to a `Doctor` profile (via `Doctor.user_id`). The `POST /doctors/` endpoint was modified to facilitate this linking based on the authenticated user creating the profile.
* **Simplified Doctor Authorization:** For general actions like making recommendations for a `{doctor_id}`, the system assumes an authenticated user is authorized. The analytics endpoint is more specific, using the authenticated user's linked profile. A formal role-based access control (RBAC) system is not implemented.
* **Basic Sentiment Analysis:** The sentiment analysis for reviews is rudimentary (keyword-based) due to the project constraint of not using external NLP libraries or services.
* **External API Dependency:** Product details for recommendations are fetched from `fakestoreapi.com`; system functionality depends on this API's availability and consistent structure.
* **Database Migrations:** Schema evolution (e.g., adding/modifying table columns after initial creation) currently requires manual deletion and recreation of the `test.db` file. A tool like Alembic would be used in a production setting.
* **Idempotency:** No explicit mechanism prevents a user from submitting multiple reviews for the same doctor.

---