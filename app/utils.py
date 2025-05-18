
import requests
from typing import Optional
from .schemas import ProductDetail 

DUMMY_API_URL = "https://fakestoreapi.com/products" 

def fetch_product_details_by_id(product_id: int) -> Optional[ProductDetail]:
    """
    Fetches product details for a given product_id from the fakestoreapi.
    Returns a ProductDetail Pydantic model instance or None if an error occurs.
    """
    try:
        response = requests.get(f"{DUMMY_API_URL}/{product_id}")
        response.raise_for_status()  
        product_data = response.json()
        return ProductDetail(**product_data)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching product {product_id} from API: {e}")
        return None
    except Exception as e:
        print(f"Error processing product data for product {product_id}: {e}")
        return None