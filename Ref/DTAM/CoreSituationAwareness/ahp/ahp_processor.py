"""
Analytic Hierarchy Process (AHP) Module for UAM Operations System

This module implements AHP decision-making for risk assessment and advisory generation.
It uses pairwise comparison matrices to weight different safety factors.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from enum import Enum

class RiskLevel(Enum):
    """Risk level categories"""
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    EMERGENCY = "EMERGENCY"

class AdvisoryAction(Enum):
    """Possible advisory actions"""
    MAINTAIN_COURSE = "Maintain current course and speed"
    REDUCE_SPEED = "Reduce speed and monitor closely"
    CHANGE_ALTITUDE = "Consider altitude change"
    CHANGE_HEADING = "Change heading to avoid conflict"
    EMERGENCY_AVOID = "Execute immediate avoidance maneuver"
    LAND_IMMEDIATELY = "Land immediately - critical situation"

@dataclass
class AHPCriteria:
    """AHP criteria with weights and values"""
    distance: float  # Normalized distance metric [0, 1]
    time_to_collision: float  # Normalized TTC metric [0, 1]
    uncertainty: float  # Normalized uncertainty metric [0, 1]
    velocity: float  # Normalized relative velocity metric [0, 1]
    
@dataclass
class AHPResult:
    """Result of AHP analysis"""
    risk_score: float  # Overall risk score [0, 1]
    risk_level: RiskLevel
    recommended_action: AdvisoryAction
    confidence: float  # Confidence in the decision [0, 1]
    criteria_weights: Dict[str, float]
    criteria_scores: Dict[str, float]

class AHPProcessor:
    """Analytic Hierarchy Process processor for UAM risk assessment"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Default pairwise comparison matrix for criteria
        # Rows/Cols: [Distance, TTC, Uncertainty, Velocity]
        # Scale: 1 = equal importance, 3 = moderate importance, 5 = strong importance,
        #        7 = very strong, 9 = extreme importance
        self.default_comparison_matrix = np.array([
            [1.0, 0.5, 3.0, 2.0],    # Distance vs [Distance, TTC, Uncertainty, Velocity]
            [2.0, 1.0, 5.0, 3.0],    # TTC vs [Distance, TTC, Uncertainty, Velocity]
            [1/3, 0.2, 1.0, 0.5],    # Uncertainty vs [Distance, TTC, Uncertainty, Velocity]
            [0.5, 1/3, 2.0, 1.0]     # Velocity vs [Distance, TTC, Uncertainty, Velocity]
        ])
        
        self.criteria_names = ['distance', 'time_to_collision', 'uncertainty', 'velocity']
        self.criteria_weights = self._calculate_criteria_weights(self.default_comparison_matrix)
        
        # Risk thresholds
        self.safe_threshold = 0.3
        self.emergency_threshold = 0.6
        
    def _calculate_criteria_weights(self, comparison_matrix: np.ndarray) -> Dict[str, float]:
        """Calculate criteria weights from pairwise comparison matrix using eigenvector method"""
        try:
            # Calculate eigenvalues and eigenvectors
            eigenvals, eigenvecs = np.linalg.eig(comparison_matrix)
            
            # Find the largest eigenvalue
            max_eigenval_idx = np.argmax(eigenvals.real)
            principal_eigenvec = eigenvecs[:, max_eigenval_idx].real
            
            # Normalize the eigenvector to get weights
            weights = principal_eigenvec / np.sum(principal_eigenvec)
            
            # Ensure all weights are positive
            weights = np.abs(weights)
            weights = weights / np.sum(weights)
            
            # Calculate consistency ratio
            consistency_ratio = self._calculate_consistency_ratio(comparison_matrix, eigenvals[max_eigenval_idx].real)
            
            if consistency_ratio > 0.1:
                self.logger.warning(f"Inconsistent comparison matrix (CR = {consistency_ratio:.3f})")
            
            return dict(zip(self.criteria_names, weights))
            
        except Exception as e:
            self.logger.error(f"Error calculating weights: {e}")
            # Return equal weights as fallback
            equal_weight = 1.0 / len(self.criteria_names)
            return {name: equal_weight for name in self.criteria_names}
            
    def _calculate_consistency_ratio(self, matrix: np.ndarray, lambda_max: float) -> float:
        """Calculate consistency ratio for the comparison matrix"""
        n = matrix.shape[0]
        consistency_index = (lambda_max - n) / (n - 1)
        
        # Random consistency index values for matrices of different sizes
        random_index = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41}
        
        if n in random_index:
            ri = random_index[n]
            consistency_ratio = consistency_index / ri if ri > 0 else 0
        else:
            consistency_ratio = 0
            
        return consistency_ratio
        
    def update_comparison_matrix(self, new_matrix: np.ndarray) -> bool:
        """Update the pairwise comparison matrix"""
        try:
            if new_matrix.shape != (4, 4):
                raise ValueError("Comparison matrix must be 4x4")
                
            # Validate reciprocal property
            for i in range(4):
                for j in range(4):
                    if i != j and abs(new_matrix[i, j] * new_matrix[j, i] - 1.0) > 0.01:
                        self.logger.warning(f"Matrix not reciprocal at ({i}, {j})")
                        
            self.default_comparison_matrix = new_matrix
            self.criteria_weights = self._calculate_criteria_weights(new_matrix)
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating comparison matrix: {e}")
            return False
            
    def process_risk_assessment(self, criteria: AHPCriteria) -> AHPResult:
        """Process risk assessment using AHP methodology"""
        try:
            # Extract criteria values
            criteria_values = {
                'distance': criteria.distance,
                'time_to_collision': criteria.time_to_collision,
                'uncertainty': criteria.uncertainty,
                'velocity': criteria.velocity
            }
            
            # Calculate weighted risk score
            risk_score = 0.0
            for criterion, value in criteria_values.items():
                weight = self.criteria_weights.get(criterion, 0.0)
                risk_score += weight * value
                
            # Determine risk level
            if risk_score <= self.safe_threshold:
                risk_level = RiskLevel.SAFE
            elif risk_score <= self.emergency_threshold:
                risk_level = RiskLevel.CAUTION
            else:
                risk_level = RiskLevel.EMERGENCY
                
            # Determine recommended action
            recommended_action = self._determine_advisory_action(risk_score, criteria_values)
            
            # Calculate confidence based on criteria consistency
            confidence = self._calculate_decision_confidence(criteria_values)
            
            return AHPResult(
                risk_score=risk_score,
                risk_level=risk_level,
                recommended_action=recommended_action,
                confidence=confidence,
                criteria_weights=self.criteria_weights.copy(),
                criteria_scores=criteria_values.copy()
            )
            
        except Exception as e:
            self.logger.error(f"Error in AHP processing: {e}")
            # Return safe default
            return AHPResult(
                risk_score=0.0,
                risk_level=RiskLevel.SAFE,
                recommended_action=AdvisoryAction.MAINTAIN_COURSE,
                confidence=0.5,
                criteria_weights=self.criteria_weights.copy(),
                criteria_scores={'distance': 0, 'time_to_collision': 0, 'uncertainty': 0, 'velocity': 0}
            )
            
    def _determine_advisory_action(self, risk_score: float, criteria: Dict[str, float]) -> AdvisoryAction:
        """Determine recommended advisory action based on risk score and individual criteria"""
        
        # Emergency situations
        if risk_score > 0.8 or criteria['time_to_collision'] > 0.9:
            if criteria['distance'] > 0.9:  # Very close
                return AdvisoryAction.LAND_IMMEDIATELY
            else:
                return AdvisoryAction.EMERGENCY_AVOID
                
        # High caution situations
        elif risk_score > 0.6:
            if criteria['time_to_collision'] > 0.7:
                return AdvisoryAction.CHANGE_HEADING
            elif criteria['velocity'] > 0.7:
                return AdvisoryAction.CHANGE_ALTITUDE
            else:
                return AdvisoryAction.REDUCE_SPEED
                
        # Moderate caution
        elif risk_score > 0.3:
            if criteria['uncertainty'] > 0.6:
                return AdvisoryAction.REDUCE_SPEED
            else:
                return AdvisoryAction.REDUCE_SPEED
                
        # Safe situations
        else:
            return AdvisoryAction.MAINTAIN_COURSE
            
    def _calculate_decision_confidence(self, criteria: Dict[str, float]) -> float:
        """Calculate confidence in the decision based on criteria consistency"""
        # High confidence when criteria agree (all high or all low)
        values = list(criteria.values())
        
        # Calculate variance - low variance means high agreement
        variance = np.var(values)
        
        # Convert variance to confidence (inverse relationship)
        confidence = 1.0 / (1.0 + variance * 4)  # Scale factor of 4
        
        return min(1.0, max(0.1, confidence))
        
    def get_advisory_text(self, result: AHPResult, object_info: Optional[Dict] = None) -> str:
        """Generate human-readable advisory text"""
        risk_level_text = {
            RiskLevel.SAFE: "SAFE",
            RiskLevel.CAUTION: "CAUTION",
            RiskLevel.EMERGENCY: "EMERGENCY"
        }
        
        base_text = f"Risk Level: {risk_level_text[result.risk_level]} ({result.risk_score:.2f})\n"
        base_text += f"Confidence: {result.confidence:.2f}\n\n"
        base_text += f"Advisory: {result.recommended_action.value}\n\n"
        
        # Add criteria breakdown
        base_text += "Risk Factors:\n"
        for criterion, score in result.criteria_scores.items():
            weight = result.criteria_weights[criterion]
            contribution = weight * score
            base_text += f"• {criterion.replace('_', ' ').title()}: {score:.2f} "
            base_text += f"(weight: {weight:.2f}, contribution: {contribution:.3f})\n"
            
        if object_info:
            base_text += f"\nObject Details:\n"
            base_text += f"• Distance: {object_info.get('distance', 'N/A')} m\n"
            base_text += f"• TTC: {object_info.get('ttc', 'N/A')} s\n"
            base_text += f"• Speed: {object_info.get('speed', 'N/A')} m/s\n"
            
        return base_text
        
    def get_risk_color(self, risk_level: RiskLevel) -> str:
        """Get color code for risk level"""
        colors = {
            RiskLevel.SAFE: "#00AA00",
            RiskLevel.CAUTION: "#FFAA00", 
            RiskLevel.EMERGENCY: "#FF0000"
        }
        return colors.get(risk_level, "#CCCCCC")
        
    def analyze_multiple_objects(self, objects_criteria: List[AHPCriteria]) -> AHPResult:
        """Analyze risk from multiple objects and return composite assessment"""
        if not objects_criteria:
            # No objects detected
            return AHPResult(
                risk_score=0.0,
                risk_level=RiskLevel.SAFE,
                recommended_action=AdvisoryAction.MAINTAIN_COURSE,
                confidence=1.0,
                criteria_weights=self.criteria_weights.copy(),
                criteria_scores={'distance': 0, 'time_to_collision': 0, 'uncertainty': 0, 'velocity': 0}
            )
            
        # Process each object
        individual_results = [self.process_risk_assessment(criteria) for criteria in objects_criteria]
        
        # Find highest risk
        max_risk_result = max(individual_results, key=lambda r: r.risk_score)
        
        # Calculate average confidence
        avg_confidence = np.mean([r.confidence for r in individual_results])
        
        # Use the highest risk as the overall assessment but adjust confidence
        max_risk_result.confidence = avg_confidence
        
        return max_risk_result
        
    def export_ahp_configuration(self) -> Dict:
        """Export current AHP configuration"""
        return {
            'comparison_matrix': self.default_comparison_matrix.tolist(),
            'criteria_weights': self.criteria_weights,
            'safe_threshold': self.safe_threshold,
            'emergency_threshold': self.emergency_threshold
        }
        
    def import_ahp_configuration(self, config: Dict) -> bool:
        """Import AHP configuration"""
        try:
            if 'comparison_matrix' in config:
                matrix = np.array(config['comparison_matrix'])
                self.update_comparison_matrix(matrix)
                
            if 'safe_threshold' in config:
                self.safe_threshold = config['safe_threshold']
                
            if 'emergency_threshold' in config:
                self.emergency_threshold = config['emergency_threshold']
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing AHP configuration: {e}")
            return False