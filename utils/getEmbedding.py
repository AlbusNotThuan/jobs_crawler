from google import genai
from utils.api_key_manager import get_api_key_manager, APIKeyManager
from google.genai import types

def _get_embedding(content: str, api_key_manager: APIKeyManager) -> list:
    """
    Generate an embedding for the given content using the Gemini API.
    """
    max_retries = len(api_key_manager.api_keys)
    retries = 0
    current_key = api_key_manager.get_current_key()
    while retries < max_retries:
        client = genai.Client(api_key=current_key)
        try:
            result_embeddings = client.models.embed_content(
                model="gemini-embedding-001",
                contents= content,
                config=types.EmbedContentConfig(
                    task_type="CLASSIFICATION"  # Specify the task type if needed
                )
            ).embeddings
            # Check if the result is valid and contains an embedding
            if result_embeddings and result_embeddings[0].values:
                # Extract the list of floats from the first ContentEmbedding object
                return result_embeddings[0].values
            else:
                print("Warning: No embedding was returned from the API.")
                return []
        except Exception as e:
            print(f"Error generating embedding: {e}")
            error_message = str(e).lower()
            api_key_error = any(err in error_message for err in ["api key", "quota", "rate limit", "permission", "unauthorized", "authentication", "internal"])
            if api_key_error:
                retries += 1
                print(f"API key error ({current_key[:12]}...): {e}")
                if retries < max_retries:
                    current_key = api_key_manager.next_key()
                    print(f"Switching to next API key: {current_key[:12]}...")
                else:
                    print("Exhausted all API keys, returning empty embedding.")
                    return []
            else:
                print(f"An unexpected error occurred. Returning empty embedding. Error: {e}")
                return []