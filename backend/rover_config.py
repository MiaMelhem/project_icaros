"""
Rover configuration profiles for ICAROS route planning.

Specs provided by the project team for the MVP.
"""

# Each rover is a simple dictionary so Mia can read and modify values easily.
ROVER_PROFILES = {
    "Astrolab CLV-1": {
        "name": "Astrolab CLV-1",
        "max_slope_deg": 20.0,
        "nominal_speed_mps": 2.8,
        "roughness_tolerance": 0.3,
        "energy_factor": 1.18,
        "max_range_m": 4000.0,
        "psr_capable": False,
        "cargo_kg": 0.0,
        "night_survival_hours": 0.0,
        "wireless_charge": False,
        "description": (
            "Crewed Lunar Vehicle 1, an adapted, 2,000-pound version of Astrolab's "
            "FLEX architecture built with Axiom Space. Prioritizes structural "
            "robustness and cargo volume with a top speed of 10 kph."
        ),
    },
    "Lunar Outpost Pegasus": {
        "name": "Lunar Outpost Pegasus",
        "max_slope_deg": 20.0,
        "nominal_speed_mps": 4.0,
        "roughness_tolerance": 0.3,
        "energy_factor": 1.10,
        "max_range_m": 6000.0,
        "psr_capable": False,
        "cargo_kg": 0.0,
        "night_survival_hours": 0.0,
        "wireless_charge": False,
        "description": (
            "A lighter, highly agile evolution of the Eagle rover built with GM and "
            "Lockheed Martin. Optimized for human-centered mobility with speeds "
            "exceeding 9 mph over frozen, rugged South Pole terrain."
        ),
    },
}


def get_rover_config(rover_name):
    """
    Return the configuration dictionary for a rover by name.

    Raises KeyError if the rover name is not recognized.
    """
    if rover_name not in ROVER_PROFILES:
        available = ", ".join(ROVER_PROFILES.keys())
        raise KeyError(f"Unknown rover '{rover_name}'. Available: {available}")
    return dict(ROVER_PROFILES[rover_name])


def validate_rover_config(config: dict) -> dict:
    """
    Validate and normalize a rover configuration from the client.

    Used for session overrides and user-created custom rovers.
    """
    name = str(config.get("name", "")).strip()
    if not name:
        raise ValueError("Rover name is required")

    max_slope_deg = float(config["max_slope_deg"])
    nominal_speed_mps = float(config["nominal_speed_mps"])
    roughness_tolerance = float(config["roughness_tolerance"])
    energy_factor = float(config["energy_factor"])
    max_range_m = float(config["max_range_m"])
    cargo_kg = float(config.get("cargo_kg", 0.0))
    night_survival_hours = float(config.get("night_survival_hours", 0.0))
    psr_capable = bool(config.get("psr_capable", False))
    wireless_charge = bool(config.get("wireless_charge", False))

    if not 5.0 <= max_slope_deg <= 45.0:
        raise ValueError("max_slope_deg must be between 5 and 45")
    if nominal_speed_mps <= 0:
        raise ValueError("nominal_speed_mps must be greater than 0")
    if not 0.0 <= roughness_tolerance <= 1.0:
        raise ValueError("roughness_tolerance must be between 0 and 1")
    if energy_factor <= 0:
        raise ValueError("energy_factor must be greater than 0")
    if not 500.0 <= max_range_m <= 15000.0:
        raise ValueError("max_range_m must be between 500 and 15000")
    if not 0.0 <= cargo_kg <= 1000.0:
        raise ValueError("cargo_kg must be between 0 and 1000")
    if not 0.0 <= night_survival_hours <= 5000.0:
        raise ValueError("night_survival_hours must be between 0 and 5000")

    description = str(config.get("description", "")).strip()
    if not description:
        description = "Custom rover profile for mission what-if analysis."

    return {
        "name": name,
        "max_slope_deg": max_slope_deg,
        "nominal_speed_mps": nominal_speed_mps,
        "roughness_tolerance": roughness_tolerance,
        "energy_factor": energy_factor,
        "max_range_m": max_range_m,
        "psr_capable": psr_capable,
        "cargo_kg": cargo_kg,
        "night_survival_hours": night_survival_hours,
        "wireless_charge": wireless_charge,
        "description": description,
    }


def resolve_rover_config(rover_name: str, override: dict | None = None) -> dict:
    """
    Return rover config from a built-in preset or a client-provided override.

    When override is supplied, built-in presets are not modified — the override
    is validated and used as-is for this request.
    """
    if override is not None:
        merged = dict(override)
        if not str(merged.get("name", "")).strip():
            merged["name"] = rover_name
        return validate_rover_config(merged)
    return get_rover_config(rover_name)


def list_rovers():
    """Return a list of all available rover configuration dictionaries."""
    return list(ROVER_PROFILES.values())
