"""Health content for the About section. Statements per category follow the official CPCB AQI health statements;
guidance is general public-health advice, NOT medical advice. Keep wording cautious ("linked to", "may")."""

DISCLAIMER = (
    "This is general information, not medical advice. People with heart or lung disease, pregnant women, children and "
    "older adults should follow their doctor's guidance. Air quality values here are PM-based estimates and can differ "
    "from official station readings."
)

REFERENCE_VALUES = {
    "unit": "ug/m3",
    "india_naaqs": {"pm25_24h": 60, "pm25_annual": 40, "pm10_24h": 100, "pm10_annual": 60,
                    "note": "India's National Ambient Air Quality Standards"},
    "who_2021": {"pm25_24h": 15, "pm25_annual": 5, "pm10_24h": 45, "pm10_annual": 15,
                 "note": "WHO global air quality guidelines (2021)"},
}

WHY_PM25 = (
    "PM2.5 are particles smaller than 2.5 micrometres - about 30 times finer than a human hair. They travel deep into the "
    "lungs and some pass into the bloodstream. Long-term exposure is linked to asthma and COPD, heart attacks, stroke, "
    "lung cancer, and reduced lung growth in children. PM10 (up to 10 micrometres) mostly irritates the nose, throat and airways."
)

# Ordered best -> worst. `range` is the AQI band; `group` is the three-way split the About page shows.
CATEGORIES = [
    {
        "key": "good", "label": "Good", "range": "0-50", "group": "low",
        "cpcb_statement": "Minimal impact.",
        "who_is_affected": "Almost no one.",
        "what_you_may_feel": "Nothing noticeable.",
        "what_to_do": ["Normal outdoor activity is fine for everyone."],
    },
    {
        "key": "satisfactory", "label": "Satisfactory", "range": "51-100", "group": "low",
        "cpcb_statement": "May cause minor breathing discomfort to sensitive people.",
        "who_is_affected": "Unusually sensitive people, e.g. some with asthma.",
        "what_you_may_feel": "Occasional mild cough or throat irritation in sensitive people.",
        "what_to_do": ["Outdoor activity is fine for most people.", "Sensitive people can watch for symptoms."],
    },
    {
        "key": "moderate", "label": "Moderate", "range": "101-200", "group": "medium",
        "cpcb_statement": "May cause breathing discomfort to people with lung disease such as asthma, and discomfort to "
                          "people with heart disease, children and older adults.",
        "who_is_affected": "People with asthma, COPD or heart disease; children; older adults.",
        "what_you_may_feel": "Cough, wheeze or breathlessness in at-risk groups, especially during exercise.",
        "what_to_do": ["At-risk groups: shorten or ease strenuous outdoor activity.",
                       "Keep rescue inhalers and prescribed medicines at hand.",
                       "Healthy adults can usually continue normal activity."],
    },
    {
        "key": "poor", "label": "Poor", "range": "201-300", "group": "high",
        "cpcb_statement": "May cause breathing discomfort to most people on prolonged exposure, and discomfort to people "
                          "with heart disease.",
        "who_is_affected": "Most people on prolonged exposure; at-risk groups more strongly.",
        "what_you_may_feel": "Throat and eye irritation, cough, tiredness, breathlessness when active.",
        "what_to_do": ["Reduce prolonged or heavy outdoor exercise.",
                       "Consider a well-fitted N95/FFP2 mask outdoors (cloth and surgical masks filter little PM2.5).",
                       "Keep windows closed in the worst hours; use an air purifier if you have one."],
    },
    {
        "key": "very_poor", "label": "Very Poor", "range": "301-400", "group": "high",
        "cpcb_statement": "May cause respiratory illness to people on prolonged exposure. Effect may be more pronounced "
                          "in people with lung and heart diseases.",
        "who_is_affected": "Everyone on prolonged exposure; at-risk groups can become seriously unwell.",
        "what_you_may_feel": "Persistent cough, chest tightness, worsening asthma or heart symptoms.",
        "what_to_do": ["Avoid outdoor exercise; limit time outside.",
                       "Wear a well-fitted N95/FFP2 mask if you must go out.",
                       "Seek medical advice early if you have chest pain, severe breathlessness or worsening symptoms."],
    },
    {
        "key": "severe", "label": "Severe", "range": "401-500", "group": "high",
        "cpcb_statement": "Affects healthy people and seriously impacts those with existing diseases.",
        "who_is_affected": "Everyone; people with existing disease are seriously affected.",
        "what_you_may_feel": "Marked breathing difficulty, eye and throat irritation, fatigue; serious risk for at-risk groups.",
        "what_to_do": ["Stay indoors with windows closed where possible; avoid all outdoor exertion.",
                       "Use an N95/FFP2 mask outdoors and an air purifier indoors if available.",
                       "Get medical help promptly for chest pain, severe breathlessness, fainting or confusion."],
    },
]

GROUPS = {
    "low": {"label": "Low AQI (Good - Satisfactory, 0-100)",
            "summary": "Air is largely safe. Only unusually sensitive people may notice minor discomfort."},
    "medium": {"label": "Medium AQI (Moderate, 101-200)",
               "summary": "Healthy adults are usually fine; asthma, heart and lung patients, children and older adults may "
                          "feel symptoms and should take it easier outdoors."},
    "high": {"label": "High AQI (Poor - Severe, 201-500)",
             "summary": "Health effects reach most people on prolonged exposure and become serious for everyone, and "
                        "especially at-risk groups, at the top of the scale."},
}


def health_payload() -> dict:
    from ..services.aqi import CATEGORIES as AQI_CATS

    colors = {key: color for _, key, _, color in AQI_CATS}
    return {
        "groups": GROUPS,
        "categories": [{**c, "color": colors[c["key"]]} for c in CATEGORIES],
        "why_pm25_matters": WHY_PM25,
        "reference_values": REFERENCE_VALUES,
        "disclaimer": DISCLAIMER,
        "sources": ["CPCB National Air Quality Index (2014)", "WHO Global Air Quality Guidelines (2021)",
                    "India NAAQS (2009)"],
    }
