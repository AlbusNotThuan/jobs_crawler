import yaml
import os
from typing import Dict, Any


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path (str): Path to the YAML configuration file
        
    Returns:
        Dict[str, Any]: Dictionary containing the configuration data
        
    Raises:
        FileNotFoundError: If the config file doesn't exist
        yaml.YAMLError: If there's an error parsing the YAML file
        Exception: For other general errors
    """
    try:
        # Check if file exists
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Load and parse YAML file
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            
        # Validate that config is not empty
        if config is None:
            config = {}
            
        print(f"Successfully loaded configuration from: {config_path}")
        return config
        
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {config_path}: {e}")
        raise
    except FileNotFoundError as e:
        print(f"Configuration file error: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error loading config from {config_path}: {e}")
        raise


def validate_required_keys(config: Dict[str, Any], required_keys: list) -> bool:
    """
    Validate that all required keys are present in the configuration.
    
    Args:
        config (Dict[str, Any]): Configuration dictionary to validate
        required_keys (list): List of required configuration keys
        
    Returns:
        bool: True if all required keys are present, False otherwise
    """
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        print(f"Missing required configuration keys: {missing_keys}")
        return False
    
    return True
