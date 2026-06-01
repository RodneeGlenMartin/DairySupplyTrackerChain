from datetime import datetime, timedelta
from typing import Dict, Any, List, Set, Tuple

def calculate_genetic_blood_fraction(sire_percentage: float, dam_percentage: float) -> float:
    """
    Calculates the genetic dairy blood percentage in the offspring.
    Formula: G_n = (S_n + D_{n-1}) / 2
    Where S_n is sire's dairy purity, and D_{n-1} is the dam's dairy purity.
    """
    if not (0.0 <= sire_percentage <= 1.0) or not (0.0 <= dam_percentage <= 1.0):
        raise ValueError("Dairy blood percentages must be between 0.0 and 1.0 (inclusive).")
    return (sire_percentage + dam_percentage) / 2.0

def calculate_relationship_coefficient(animal_a_id: Any, animal_b_id: Any, pedigree_dict: Dict[Any, Dict[str, Any]]) -> float:
    """
    Parses ancestral paths up to 5 generations deep, identifies common ancestors,
    calculates generation distance paths (p and q), and returns Wright's coefficient of relationship R.
    Formula: R = Sum of (0.5)^(p + q) for each independent path to a common ancestor.
    
    If R >= 0.0625, raises a ValueError to prevent inbreeding.
    """
    # Helper to find all ancestral paths from start_id up to 5 generations deep.
    # A path is a list of node IDs: [start_id, parent_1, ..., ancestor]
    def find_ancestral_paths(start_id: Any, depth: int = 0) -> List[List[Any]]:
        if start_id is None or depth > 5:
            return []
        
        paths = [[start_id]]
        parent_info = pedigree_dict.get(start_id)
        if parent_info:
            dam_id = parent_info.get("dam_id")
            sire_id = parent_info.get("sire_id")
            
            if dam_id is not None:
                for p in find_ancestral_paths(dam_id, depth + 1):
                    paths.append([start_id] + p)
            if sire_id is not None:
                for p in find_ancestral_paths(sire_id, depth + 1):
                    paths.append([start_id] + p)
        return paths

    # Get paths for both animals
    paths_a = find_ancestral_paths(animal_a_id)
    paths_b = find_ancestral_paths(animal_b_id)

    # Group paths by their ending ancestor
    from collections import defaultdict
    ancestor_paths_a = defaultdict(list)
    for path in paths_a:
        ancestor_paths_a[path[-1]].append(path)

    ancestor_paths_b = defaultdict(list)
    for path in paths_b:
        ancestor_paths_b[path[-1]].append(path)

    # Common ancestors are endpoints shared by both path sets
    common_ancestors = set(ancestor_paths_a.keys()) & set(ancestor_paths_b.keys())
    
    R = 0.0
    for ancestor in common_ancestors:
        for p_a in ancestor_paths_a[ancestor]:
            for p_b in ancestor_paths_b[ancestor]:
                # Check if paths are independent (they share NO nodes other than the ancestor itself)
                intersection = set(p_a) & set(p_b)
                if intersection == {ancestor}:
                    p = len(p_a) - 1 # steps from A to ancestor
                    q = len(p_b) - 1 # steps from B to ancestor
                    R += (0.5) ** (p + q)

    # Raise error if R is greater than or equal to the threshold of 0.0625 (cousin breeding)
    if R >= 0.0625:
        raise ValueError(f"Inbreeding risk: Coefficient of relationship R ({R:.4f}) is >= 0.0625. Breeding blocked.")

    return R

def calculate_repayment_due_date(actual_calving_date: Any) -> Any:
    """
    Calculates the 18-month heifer repayment due date.
    18 months is mapped to exactly 540 days post actual calving date.
    """
    if isinstance(actual_calving_date, str):
        # Handle string inputs in standard formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(actual_calving_date, fmt).date()
                return dt + timedelta(days=540)
            except ValueError:
                continue
        raise ValueError(f"Unable to parse date string: {actual_calving_date}")
    
    # Handle datetime or date objects
    return actual_calving_date + timedelta(days=540)
