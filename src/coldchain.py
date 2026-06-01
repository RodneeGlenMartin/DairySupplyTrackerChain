import numpy as np
from datetime import datetime
from typing import List, Tuple
from src.config import (
    GAS_CONSTANT,
    KINETIC_MODEL_ACTIVATION_ENERGY,
    REFERENCE_TEMPERATURE_KELVIN,
    REFERENCE_SPECIFIC_GROWTH_RATE,
    HIGH_RISK_CFU_THRESHOLD
)

def predict_microbial_growth(temp_log: List[float], time_log: List[datetime], initial_cfu: float = 1000.0) -> float:
    """
    Computes predicted microbial load (CFU/ml) based on temperature logs using the Arrhenius model.
    temp_log: List of float values representing temperature readings in Celsius.
    time_log: List of datetime objects representing the time of each reading.
    """
    if len(temp_log) != len(time_log):
        raise ValueError("Temperature log and time log must have the same length.")
    if len(temp_log) < 2:
        return initial_cfu

    R = GAS_CONSTANT
    E_a = KINETIC_MODEL_ACTIVATION_ENERGY
    T_ref = REFERENCE_TEMPERATURE_KELVIN
    mu_ref = REFERENCE_SPECIFIC_GROWTH_RATE
    
    log_ratio = 0.0
    for i in range(1, len(temp_log)):
        # Calculate time difference in hours
        dt = (time_log[i] - time_log[i-1]).total_seconds() / 3600.0
        
        # Calculate average temperature during the interval in Kelvin
        temp_k_prev = temp_log[i-1] + 273.15
        temp_k_curr = temp_log[i] + 273.15
        T_avg = (temp_k_prev + temp_k_curr) / 2.0
        
        # Apply the Arrhenius model
        mu = mu_ref * np.exp(-(E_a / R) * ((1.0 / T_avg) - (1.0 / T_ref)))
        log_ratio += mu * dt
        
    final_cfu = initial_cfu * np.exp(log_ratio)
    return float(final_cfu)

def evaluate_batch_spoilage_risk(temp_log: List[float], time_log: List[datetime], initial_cfu: float = 1000.0) -> Tuple[float, str]:
    """
    Evaluates the spoilage risk of a raw milk batch during transit.
    Returns: Tuple of (final_cfu, status) where status is "High Risk" if final_cfu exceeds 1.0e5 CFU/ml.
    """
    final_cfu = predict_microbial_growth(temp_log, time_log, initial_cfu)
    status = "High Risk" if final_cfu > HIGH_RISK_CFU_THRESHOLD else "Normal"
    return final_cfu, status
