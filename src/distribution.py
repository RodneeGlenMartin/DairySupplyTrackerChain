import hashlib
from typing import Dict, Any, List

def generate_batch_hash(
    previous_hash: str,
    batch_identifier: str,
    volume: float,
    pasteur_temp: float,
    coliform_status: str,
    timestamp: str
) -> str:
    """
    Computes the cryptographic SHA-256 signature for a finished product batch.
    Formula: H(B_i) = SHA256( H(B_{i-1}) || B_i || V_batch || T_pasteur || P_coliform || t_stamp )
    """
    if not previous_hash:
        # Standard zero-hash initialization for first batch
        previous_hash = "0" * 64
        
    # We use a consistent string formatting with || delimiter to ensure deterministic concatenation
    data = (
        f"{previous_hash}||"
        f"{batch_identifier}||"
        f"{float(volume):.2f}||"
        f"{float(pasteur_temp):.2f}||"
        f"{coliform_status}||"
        f"{timestamp}"
    )
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def verify_batch_chain(batches: List[Dict[str, Any]]) -> bool:
    """
    Verifies that the entire cryptographic chain of finished product batches is intact.
    Each batch dictionary must contain:
    - 'previous_hash'
    - 'batch_identifier'
    - 'volume'
    - 'pasteur_temp'
    - 'coliform_status'
    - 'timestamp'
    - 'cryptographic_signature'
    """
    for i in range(len(batches)):
        batch = batches[i]
        
        # Recalculate signature
        expected_sig = generate_batch_hash(
            previous_hash=batch.get("previous_hash", ""),
            batch_identifier=batch.get("batch_identifier", ""),
            volume=batch.get("volume", 0.0),
            pasteur_temp=batch.get("pasteur_temp", 0.0),
            coliform_status=batch.get("coliform_status", ""),
            timestamp=batch.get("timestamp", "")
        )
        
        # Verify match
        if expected_sig != batch.get("cryptographic_signature"):
            return False
            
        # Verify linkage with subsequent batch
        if i < len(batches) - 1:
            next_batch = batches[i + 1]
            if batch.get("cryptographic_signature") != next_batch.get("previous_hash"):
                return False
                
    return True
