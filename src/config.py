import os

# Database configurations
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dairy_supplychain")

# Arrhenius Spoilage Kinetic Model constants
KINETIC_MODEL_ACTIVATION_ENERGY = float(os.getenv("KINETIC_MODEL_ACTIVATION_ENERGY", "64000.0")) # J/mol
GAS_CONSTANT = 8.314 # J/(mol*K)
REFERENCE_TEMPERATURE_KELVIN = 277.15 # 4 degrees Celsius in Kelvin
REFERENCE_SPECIFIC_GROWTH_RATE = 0.05 # hours^-1

# High-risk microbial load threshold (CFU/ml)
HIGH_RISK_CFU_THRESHOLD = 1.0e5

# Strict production database durability flag
DISABLE_IN_MEMORY_FALLBACK = os.getenv("DISABLE_IN_MEMORY_FALLBACK", "false").lower() in ("true", "1", "yes")
