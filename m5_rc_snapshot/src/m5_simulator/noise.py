"""
Declared noise models for the M5 simulator (Step 6).

This module is strictly separated from statevector evolution (Step 4) and
finite-shot sampling (Step 5).  It defines an explicit, serializable noise
configuration and provides functions that apply noise effects to probability
distributions or sampled outcomes.

Implemented models
------------------
* **Readout noise – ``bit_flip``**: independently flips each measured bit
  with a configured probability.  Applied to a probability distribution by
  constructing and applying the classical readout confusion matrix.
* **Gate noise – ``depolarizing``**: mixes the ideal probability distribution
  toward the uniform distribution.  ``p_noisy = (1 - p) * p_ideal + p * U``,
  where ``U`` is the uniform distribution over all basis states.
* **Decoherence – ``none``**: accepted as a no-op.  Any other decoherence
  model is explicitly rejected as unsupported.

Design decisions
----------------
* Noise is applied to the *probability distribution*, not to the statevector
  amplitudes.  This keeps noise processing separate from unitary evolution
  and avoids mutating the statevector.
* The original probability array is **never mutated**; all operations return
  new arrays / dicts.
* Invalid or unknown configurations raise ``NoiseConfigError``
  (a subclass of ``ConfigRejectedError``) with an ``E_CONFIG_REJECTED`` tag.
* All stochastic behaviour is controlled by a supplied random seed for
  deterministic reproducibility.
"""

import json
import math
from typing import Any, Dict, List, Optional

import numpy as np

from src.m5_simulator.gates import ConfigRejectedError

# Numerical tolerance – matches the statevector / sampling engines.
TOLERANCE = 1e-10

# Supported model names per section.
_SUPPORTED_GATE_NOISE_MODELS = frozenset({"depolarizing"})
_SUPPORTED_READOUT_NOISE_MODELS = frozenset({"bit_flip"})
_SUPPORTED_DECOHERENCE_MODELS = frozenset({"none"})


# ======================================================================
# Exceptions
# ======================================================================

class NoiseConfigError(ConfigRejectedError):
    """Raised for invalid or unsupported noise configurations (E_CONFIG_REJECTED)."""
    pass


# ======================================================================
# Noise configuration
# ======================================================================

class NoiseConfig:
    """
    Explicit, serializable noise configuration.

    Sections
    --------
    gate_noise : dict
        ``{"model": str, "probability": float}``
    readout_noise : dict
        ``{"model": str, "probability": float}``
    decoherence : dict
        ``{"model": str}``  (plus optional model-specific parameters)

    The special ``mode="ideal"`` sets all sections to identity / none.
    """

    def __init__(
        self,
        mode: str = "ideal",
        gate_noise: Optional[Dict[str, Any]] = None,
        readout_noise: Optional[Dict[str, Any]] = None,
        decoherence: Optional[Dict[str, Any]] = None,
    ):
        self.mode = mode

        if mode == "ideal":
            # Ideal defaults – no noise whatsoever.
            self.gate_noise: Dict[str, Any] = gate_noise or {
                "model": "depolarizing", "probability": 0.0,
            }
            self.readout_noise: Dict[str, Any] = readout_noise or {
                "model": "bit_flip", "probability": 0.0,
            }
            self.decoherence: Dict[str, Any] = decoherence or {
                "model": "none",
            }
        elif mode == "noisy":
            if gate_noise is None:
                raise NoiseConfigError(
                    "gate_noise section is required in noisy mode "
                    "(E_CONFIG_REJECTED)."
                )
            if readout_noise is None:
                raise NoiseConfigError(
                    "readout_noise section is required in noisy mode "
                    "(E_CONFIG_REJECTED)."
                )
            self.gate_noise = dict(gate_noise)
            self.readout_noise = dict(readout_noise)
            self.decoherence = dict(decoherence) if decoherence else {"model": "none"}
        else:
            raise NoiseConfigError(
                f"Unknown noise mode '{mode}' (E_CONFIG_REJECTED)."
            )

        # Validate all sections.
        self._validate()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Run full validation on all noise sections."""
        self._validate_gate_noise()
        self._validate_readout_noise()
        self._validate_decoherence()

    def _validate_gate_noise(self) -> None:
        model = self.gate_noise.get("model")
        if model not in _SUPPORTED_GATE_NOISE_MODELS:
            raise NoiseConfigError(
                f"Unknown gate-noise model '{model}' (E_CONFIG_REJECTED)."
            )
        prob = self.gate_noise.get("probability")
        _validate_probability(prob, "gate_noise.probability")

    def _validate_readout_noise(self) -> None:
        model = self.readout_noise.get("model")
        if model not in _SUPPORTED_READOUT_NOISE_MODELS:
            raise NoiseConfigError(
                f"Unknown readout-noise model '{model}' (E_CONFIG_REJECTED)."
            )
        prob = self.readout_noise.get("probability")
        _validate_probability(prob, "readout_noise.probability")

    def _validate_decoherence(self) -> None:
        model = self.decoherence.get("model")
        if model not in _SUPPORTED_DECOHERENCE_MODELS:
            raise NoiseConfigError(
                f"Unsupported decoherence model '{model}' — only 'none' is "
                f"implemented in this step (E_CONFIG_REJECTED)."
            )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible dictionary representation."""
        return {
            "mode": self.mode,
            "gate_noise": dict(self.gate_noise),
            "readout_noise": dict(self.readout_noise),
            "decoherence": dict(self.decoherence),
        }

    def to_json(self) -> str:
        """Return a deterministic JSON string (sorted keys)."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NoiseConfig":
        """Create a NoiseConfig from a dictionary."""
        return cls(
            mode=data.get("mode", "ideal"),
            gate_noise=data.get("gate_noise"),
            readout_noise=data.get("readout_noise"),
            decoherence=data.get("decoherence"),
        )

    def __repr__(self) -> str:
        return (
            f"NoiseConfig(mode={self.mode!r}, gate_noise={self.gate_noise!r}, "
            f"readout_noise={self.readout_noise!r}, decoherence={self.decoherence!r})"
        )


# ======================================================================
# Parameter helpers
# ======================================================================

def _validate_probability(value: Any, name: str) -> None:
    """
    Validate that *value* is a finite float in [0, 1].

    Raises:
        NoiseConfigError: On any violation.
    """
    if value is None:
        raise NoiseConfigError(
            f"{name} is required (E_CONFIG_REJECTED)."
        )
    if not isinstance(value, (int, float)):
        raise NoiseConfigError(
            f"{name} must be a number, got {type(value).__name__} "
            f"(E_CONFIG_REJECTED)."
        )
    fval = float(value)
    if not math.isfinite(fval):
        raise NoiseConfigError(
            f"{name} must be finite, got {fval} (E_CONFIG_REJECTED)."
        )
    if fval < 0.0:
        raise NoiseConfigError(
            f"{name} must be >= 0, got {fval} (E_CONFIG_REJECTED)."
        )
    if fval > 1.0:
        raise NoiseConfigError(
            f"{name} must be <= 1, got {fval} (E_CONFIG_REJECTED)."
        )


# ======================================================================
# Noise application – readout bit-flip
# ======================================================================

def apply_readout_noise(
    probabilities: List[float],
    config: NoiseConfig,
    seed: Optional[int] = None,
) -> List[float]:
    """
    Apply readout noise to a probability distribution.

    For the ``bit_flip`` model with probability *p*, each qubit's measured
    bit is independently flipped with probability *p*.  This is implemented
    by constructing the classical confusion matrix and multiplying it with
    the ideal distribution.

    The method is fully deterministic (the confusion matrix is analytical)
    and does **not** require a random seed.  The *seed* parameter is
    accepted for API consistency and future extension but is unused for the
    ``bit_flip`` model applied to probabilities.

    Parameters
    ----------
    probabilities : list of float
        Ideal probability distribution (big-endian, length 2^n).
    config : NoiseConfig
        Validated noise configuration.
    seed : int or None
        Random seed (reserved; unused by the analytical bit-flip model).

    Returns
    -------
    list of float
        Noisy probability distribution.  The input list is **not** mutated.
    """
    model = config.readout_noise["model"]
    p = float(config.readout_noise["probability"])

    if model != "bit_flip":
        raise NoiseConfigError(
            f"Unknown readout-noise model '{model}' (E_CONFIG_REJECTED)."
        )

    # Probability 0 → no-op (shortcut).
    if p == 0.0:
        return list(probabilities)

    num_states = len(probabilities)
    num_qubits = int(math.log2(num_states))

    # Build the confusion matrix C[j, i] = P(measure j | true state i).
    # For independent bit-flip with probability p on each qubit:
    #   C[j, i] = product over bits k of:
    #       (1-p) if bit k of j == bit k of i,
    #       p     if bit k of j != bit k of i.
    # Equivalently, C[j, i] = (1-p)^(n - d) * p^d, where d = hamming(i XOR j).
    confusion = np.zeros((num_states, num_states), dtype=np.float64)
    for i in range(num_states):
        for j in range(num_states):
            diff = i ^ j
            d = bin(diff).count("1")
            confusion[j, i] = ((1.0 - p) ** (num_qubits - d)) * (p ** d)

    ideal = np.array(probabilities, dtype=np.float64)
    noisy = confusion @ ideal

    return noisy.tolist()


# ======================================================================
# Noise application – gate depolarizing
# ======================================================================

def apply_gate_noise(
    probabilities: List[float],
    config: NoiseConfig,
    seed: Optional[int] = None,
) -> List[float]:
    """
    Apply gate noise to a probability distribution.

    For the ``depolarizing`` model with probability *p*, the noisy
    distribution is:

        p_noisy = (1 - p) * p_ideal  +  p * U

    where U = 1/dim is the uniform distribution.  This is fully
    deterministic and does not require a seed.

    Parameters
    ----------
    probabilities : list of float
        Ideal probability distribution (big-endian, length 2^n).
    config : NoiseConfig
        Validated noise configuration.
    seed : int or None
        Reserved for future stochastic gate-noise models.

    Returns
    -------
    list of float
        Noisy probability distribution.  The input list is **not** mutated.
    """
    model = config.gate_noise["model"]
    p = float(config.gate_noise["probability"])

    if model != "depolarizing":
        raise NoiseConfigError(
            f"Unknown gate-noise model '{model}' (E_CONFIG_REJECTED)."
        )

    # Probability 0 → identity.
    if p == 0.0:
        return list(probabilities)

    dim = len(probabilities)
    ideal = np.array(probabilities, dtype=np.float64)
    uniform = np.full(dim, 1.0 / dim, dtype=np.float64)

    noisy = (1.0 - p) * ideal + p * uniform
    return noisy.tolist()


# ======================================================================
# Convenience: apply full noise pipeline
# ======================================================================

def apply_noise(
    probabilities: List[float],
    config: NoiseConfig,
    seed: Optional[int] = None,
) -> List[float]:
    """
    Apply the complete noise pipeline to a probability distribution.

    Order: gate noise → readout noise.

    Parameters
    ----------
    probabilities : list of float
        Ideal probability distribution.
    config : NoiseConfig
        Validated noise configuration.
    seed : int or None
        Random seed for any stochastic operations.

    Returns
    -------
    list of float
        Noisy probability distribution.  The input list is **not** mutated.
    """
    result = apply_gate_noise(probabilities, config, seed=seed)
    result = apply_readout_noise(result, config, seed=seed)
    return result
