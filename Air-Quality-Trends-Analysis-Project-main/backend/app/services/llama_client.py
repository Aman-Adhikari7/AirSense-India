import os, json, requests

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

CRITIC_PROMPT = """You are a strict capability critic for an MCP agent.
The agent ONLY has these tools: scrape_city, compare_cities, forecast_city, forecast_multi.
They work ONLY on air-quality data (PM2.5/PM10) over cities and time ranges.

Your job:
1) Decide if the user's request is fully supported by these tools.
2) If the request is MIXED (supported + unsupported actions like writing blogs, emailing, designing, exporting docs), split it:
   - Extract the supported subtask (rewrite it cleanly).
   - List the unsupported parts with reasons.
3) If the request is gibberish or entirely unrelated (e.g., cooking, poems, finance), mark as IRRELEVANT.

Return STRICT JSON:
{
  "category": "supported" | "mixed" | "irrelevant",
  "unsupported_reasons": [ "<why each part is not possible with the tools>" ],
  "supported_rewrite": "if category is mixed, rewrite only the supported part; else empty string",
  "examples": [
    "Compare Colombo and Kandy last 7 days",
    "Forecast Panadura next 3 days (train 7 days)"
  ]
}
Only JSON. No extra text.
"""

SYSTEM_PROMPT = """You are a planning agent. Turn the user's request into a JSON plan of tool calls.
Only use these tools and their JSON schemas. Return STRICT JSON with this shape:

{
  "plan": [
    {"name": "<tool_name>", "arguments": { ... }},
    ...
  ],
  "notes": "very brief explanation",
  "irrelevant": false
}

Strictly follow these Rules:
- Use only the listed tools; arguments must match the schemas.
- If the user asks to compare, use compare_cities with at least 2 cities.
- If forecasting multiple cities, use forecast_multi.
- If data may be stale, insert a scrape_city step BEFORE compare/forecast.
- REJECT requests like "Generate me an image comparing Colombo and Kandy for past 7 days", "Generate me an blogpost article comparing Colombo and Kandy for past 7 days", "Generate me an newspaper article forcasting Colombo and Kandy 7 days ahead"
- REJECT asks requiring non-available abilities (blog writing, emails, PDFs, images, SQL DDL, etc.).
- If the user's request is completely unrelated to air quality analysis (e.g., asking about weather, cooking, random topics), set "irrelevant": true and "plan": [].
- For mixed requests: plan only the tool-capable part, set irrelevant=false, and include notes with unsupported_reasons.
- Keep notes short. Do not include any text outside of the JSON object.
"""

def build_tool_catalog(tools: list[dict]) -> str:
    return json.dumps(tools, indent=2, ensure_ascii=False)

def critique_prompt(prompt: str, tools: list[dict], temperature: float = 0.0, timeout: int = 45) -> dict:
    """Critique a prompt to determine if it's supported, mixed, or irrelevant."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": CRITIC_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature}
    }
    r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    raw = r.json()["message"]["content"]
    try:
        return json.loads(raw)
    except Exception:
        import re
        m = re.search(r"\{.*\}", raw, re.S)
        return json.loads(m.group(0)) if m else {"category":"irrelevant","unsupported_reasons":["Non-JSON critic output"],"supported_rewrite":""}

def plan_with_llama(prompt: str, tools: list[dict], temperature: float = 0.2, timeout: int = 60) -> dict:
    """Ask Ollama (local) to produce a JSON plan."""
    sys = SYSTEM_PROMPT + "\n\nTOOLS (JSON Schemas):\n" + build_tool_catalog(tools)
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": sys},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature}
    }
    r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = data["message"]["content"]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            raise RuntimeError("LLM did not return JSON plan")
        return json.loads(m.group(0))

def plan_with_critic(prompt: str, tools: list[dict], temperature: float = 0.2, timeout: int = 60) -> dict:
    """Two-stage planner: critique first, then plan if supported."""
    critic = critique_prompt(prompt, tools)
    cat = critic.get("category","irrelevant")
    
    if cat == "irrelevant":
        return {
            "plan": [], 
            "notes": None, 
            "irrelevant": True,
            "reason": "Your request cannot be done with the available tools.",
            "unsupported_reasons": critic.get("unsupported_reasons",[]),
            "critic": critic
        }
    
    # Use original prompt if supported, or rewritten prompt if mixed
    use_prompt = prompt if cat == "supported" else critic.get("supported_rewrite") or prompt
    
    # Fall back to existing LLM planner
    base = plan_with_llama(use_prompt, tools, temperature=temperature, timeout=timeout)
    
    # If mixed, carry reasons forward
    if cat == "mixed":
        base["unsupported_reasons"] = critic.get("unsupported_reasons",[])
        note = base.get("notes") or ""
        if base["unsupported_reasons"]:
            base["notes"] = (note + (" | " if note else "") +
                             "Unsupported: " + "; ".join(base["unsupported_reasons"]))
    
    base["critic"] = critic
    return base

def generate_llm_report(comparison_data, chart_data, cities, period_days, show_combined):
    """
    Generate LLM-powered comparison report using Gemma3:4b
    """
    
    SYSTEM_PROMPT = """You are an environmental health expert AI that generates structured air quality comparison reports. Your task is to analyze air quality data and return a comprehensive JSON report in the exact structure provided.

CRITICAL REQUIREMENTS:
1. You MUST return ONLY valid JSON - no additional text, explanations, or markdown
2. You MUST use the exact JSON structure provided below
3. You MUST fill in all placeholders with actual data from the analysis
4. You MUST use scientific, factual language while maintaining accessibility
5. You MUST base all conclusions on the provided PM2.5 data and established health guidelines

JSON STRUCTURE TO FOLLOW:
{
  "report": {
    "title": "Air Quality Comparative Analysis & Health Impact Assessment",
    "executiveOverview": {
      "summary": "The analysis reveals significant disparities in air quality across the monitored cities. [City with best performance] demonstrates the most favorable conditions with an average PM2.5 of [X] µg/m³, while [City with worst performance] requires immediate attention with levels reaching [Y] µg/m³."
    },
    "cityPerformanceBreakdown": {
      "topPerformer": {
        "city": "[Best City]",
        "averagePM25": "[Value] µg/m³",
        "healthImplications": "Air quality generally falls within acceptable limits, posing minimal health risks to the general population. Sensitive groups may still experience mild symptoms during peak periods.",
        "icon": "🏆"
      },
      "areasNeedingImprovement": {
        "city": "[Worst City]",
        "averagePM25": "[Value] µg/m³",
        "healthRisks": "Prolonged exposure at these levels increases risks of respiratory and cardiovascular diseases. Immediate protective measures recommended.",
        "icon": "⚠️"
      }
    },
    "healthAwarenessInsights": {
      "shortTermExposureEffects": {
        "healthyAdults": "Minor irritation, temporary breathing discomfort",
        "sensitiveGroups": "Aggravated asthma, increased respiratory symptoms",
        "elderlyAndChildren": "Higher susceptibility to respiratory infections"
      },
      "longTermHealthImplications": {
        "risks": [
          "Chronic respiratory diseases",
          "Cardiovascular complications",
          "Reduced lung function development in children",
          "Increased cancer risk with prolonged exposure"
        ]
      }
    },
    "regionalPatternsAndTrends": {
      "description": "The data reveals [describe any patterns - seasonal variations, consistent poor performers, improving/declining trends]"
    },
    "protectiveRecommendations": {
      "immediateActions": {
        "highPM25Areas": "Limit outdoor activities, use N95 masks",
        "indoorAirQuality": "Employ HEPA filters, maintain proper ventilation",
        "vulnerableGroups": "Regular health monitoring, avoid peak pollution hours"
      },
      "longTermCommunityMeasures": [
        "Enhanced public transportation systems",
        "Green space development",
        "Industrial emission controls",
        "Public health awareness campaigns"
      ]
    },
    "comparativeRiskAssessment": {
      "description": "The analysis indicates that residents in [worst city] face approximately [X]% higher health risks compared to those in [best city], emphasizing the need for targeted interventions."
    }
  }
}

DATA INTERPRETATION GUIDELINES:
- PM2.5 levels below 12 µg/m³: Good air quality
- PM2.5 levels 12-35 µg/m³: Moderate air quality  
- PM2.5 levels 35-55 µg/m³: Unhealthy for sensitive groups
- PM2.5 levels above 55 µg/m³: Unhealthy for all populations
- Calculate risk percentage: ((worst_city_pm25 - best_city_pm25) / best_city_pm25 * 100)

Remember: Return ONLY the JSON object, no other text."""

    # Prepare the data for the LLM
    data_context = {
        "comparison_data": comparison_data,
        "chart_data": chart_data,
        "cities": cities,
        "period_days": period_days,
        "show_combined": show_combined
    }
    
    # Create the user prompt with the data
    user_prompt = f"""Please analyze the following air quality comparison data and generate a comprehensive report:

Cities analyzed: {', '.join(cities) if cities else 'N/A'}
Analysis period: {period_days} days
Best performing city: {comparison_data.get('best', 'N/A')}
Worst performing city: {comparison_data.get('worst', 'N/A')}

City statistics:
{json.dumps(comparison_data.get('byCity', {}), indent=2)}

Please generate the structured report following the exact JSON format provided in the system prompt."""

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.3}
    }
    
    try:
        r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        content = data["message"]["content"]
        
        # Parse the JSON response
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            m = re.search(r"\{.*\}", content, re.S)
            if m:
                return json.loads(m.group(0))
            else:
                raise RuntimeError("LLM did not return valid JSON")
                
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to communicate with LLM: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Failed to generate LLM report: {str(e)}")

def generate_llm_forecast_report(forecast_data, chart_data, cities, horizon_days, train_days, show_ci, show_combined, selected_model):
    """
    Generate LLM-powered forecast report using Gemma3:4b
    """
    
    SYSTEM_PROMPT = """You are an environmental health expert AI that generates structured air quality forecast reports. Your task is to analyze forecast data and return a comprehensive JSON report in the exact structure provided.

CRITICAL REQUIREMENTS:
1. You MUST return ONLY valid JSON - no additional text, explanations, or markdown
2. You MUST use the exact JSON structure provided below
3. You MUST fill in all placeholders with actual data from the analysis
4. You MUST use scientific, factual language while maintaining accessibility
5. You MUST base all conclusions on the provided forecast data and established health guidelines

JSON STRUCTURE TO FOLLOW:
{
  "report": {
    "title": "AI-Powered Air Quality Forecast Analysis & Health Impact Assessment",
    "executiveOverview": {
      "summary": "The forecast analysis reveals significant variations in predicted air quality across the monitored cities. [City with best forecast] demonstrates the most favorable predicted conditions with an average forecast of [X] µg/m³, while [City with challenging forecast] requires attention with predicted levels reaching [Y] µg/m³."
    },
    "forecastPerformance": {
      "bestForecast": {
        "city": "[Best City]",
        "averageForecast": "[Value] µg/m³",
        "forecastImplications": "Predicted air quality generally falls within acceptable limits, posing minimal health risks to the general population. Sensitive groups may still experience mild symptoms during peak periods.",
        "icon": "📈"
      },
      "challengingForecast": {
        "city": "[Challenging City]",
        "averageForecast": "[Value] µg/m³",
        "forecastRisks": "Predicted exposure at these levels increases risks of respiratory and cardiovascular diseases. Immediate protective measures recommended.",
        "icon": "⚠️"
      }
    },
    "modelPerformance": {
      "confidenceLevel": "High confidence in forecast accuracy based on historical data patterns",
      "predictionReliability": "Model shows strong predictive capability with [X]% accuracy on validation data",
      "modelType": "[SARIMAX/Prophet] - Optimized for time series forecasting with seasonal patterns"
    },
    "forecastTrends": {
      "patterns": [
        "Seasonal variation patterns detected",
        "Weekend vs weekday differences observed",
        "Peak pollution hours identified",
        "Long-term trend analysis completed"
      ]
    },
    "healthImpact": {
      "shortTermRisks": {
        "highRiskAreas": "Areas with predicted PM2.5 levels above 35 µg/m³",
        "vulnerableGroups": "Children, elderly, and those with respiratory conditions at higher risk"
      },
      "longTermImplications": [
        "Chronic respiratory disease development risk",
        "Cardiovascular health impact assessment",
        "Reduced lung function in children",
        "Increased cancer risk with prolonged exposure"
      ]
    },
    "recommendations": {
      "immediateActions": [
        "Monitor air quality alerts in high-risk areas",
        "Use N95 masks during predicted high pollution periods",
        "Limit outdoor activities during peak forecast hours",
        "Ensure proper indoor air filtration systems"
      ],
      "longTermPlanning": [
        "Develop air quality monitoring infrastructure",
        "Implement green space development plans",
        "Enhance public transportation systems",
        "Create public health awareness campaigns"
      ]
    },
    "uncertaintyAssessment": {
      "description": "The forecast model demonstrates [X]% confidence in predictions, with uncertainty increasing over longer time horizons. Weather patterns and seasonal variations may impact forecast accuracy."
    }
  }
}

DATA INTERPRETATION GUIDELINES:
- PM2.5 levels below 12 µg/m³: Good air quality forecast
- PM2.5 levels 12-35 µg/m³: Moderate air quality forecast  
- PM2.5 levels 35-55 µg/m³: Unhealthy for sensitive groups forecast
- PM2.5 levels above 55 µg/m³: Unhealthy for all populations forecast
- Confidence intervals indicate prediction uncertainty
- Model type affects forecast reliability and accuracy

Remember: Return ONLY the JSON object, no other text."""

    # Prepare the data for the LLM
    data_context = {
        "forecast_data": forecast_data,
        "chart_data": chart_data,
        "cities": cities,
        "horizon_days": horizon_days,
        "train_days": train_days,
        "show_ci": show_ci,
        "show_combined": show_combined,
        "selected_model": selected_model
    }
    
    # Create the user prompt with the data
    user_prompt = f"""Please analyze the following air quality forecast data and generate a comprehensive report:

Cities forecasted: {', '.join(cities) if cities else 'N/A'}
Forecast horizon: {horizon_days} days
Training period: {train_days} days
Model used: {selected_model}
Best forecasted city: {forecast_data.get('best', 'N/A')}
Challenging forecasted city: {forecast_data.get('worst', 'N/A')}

Forecast statistics:
{json.dumps(forecast_data.get('summary', {}), indent=2)}

Please generate the structured report following the exact JSON format provided in the system prompt."""

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.3}
    }
    
    try:
        r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        content = data["message"]["content"]
        
        # Parse the JSON response
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            m = re.search(r"\{.*\}", content, re.S)
            if m:
                return json.loads(m.group(0))
            else:
                raise RuntimeError("LLM did not return valid JSON")
                
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to communicate with LLM: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Failed to generate LLM forecast report: {str(e)}")


def chat_with_llm(user_message: str, context: dict = None) -> tuple[str, str]:
    """
    Conversational assistant for Indian Air Quality.
    Returns (reply_text, provider_name).
    Tries: Hosted OpenAI/Groq API -> Local Ollama -> Intelligent Indian CPCB Rule Engine.
    """
    from ..core.config import settings

    sys_prompt = (
        "You are AirSense AI, an intelligent environmental health assistant for India.\n"
        "You explain air quality trends, CPCB AQI standards, health impacts of PM2.5/PM10, and seasonal phenomena "
        "(such as Diwali firecracker surges, Indo-Gangetic winter temperature inversions, and post-harvest crop stubble burning).\n"
        "Keep answers concise, actionable, and scientifically grounded."
    )

    if context:
        sys_prompt += f"\n\nCURRENT PLACE CONTEXT:\n{json.dumps(context, indent=2)}"

    # 1. Try Hosted LLM API (e.g. Groq, OpenRouter, OpenAI) if key is provided
    if settings.LLM_API_KEY:
        try:
            url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": settings.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
                "max_tokens": 600,
            }
            r = requests.post(url, headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                data = r.json()
                reply = data["choices"][0]["message"]["content"]
                return reply.strip(), f"api:{settings.LLM_MODEL}"
        except Exception:
            pass

    # 2. Try Local Ollama if available
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {"temperature": 0.3},
        }
        r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=1.5)
        if r.status_code == 200:
            return r.json()["message"]["content"].strip(), f"ollama:{OLLAMA_MODEL}"
    except Exception:
        pass

    # 3. Intelligent fallback engine: Live City Lookups, Internet Search, and Conversational Responses
    msg = user_message.strip()
    msg_lower = msg.lower()

    # Conversational Greetings & Small Talk
    if msg_lower in {"hi", "hello", "hey", "namaste", "good morning", "good afternoon", "good evening"}:
        return (
            "Hello! I am your **AirSense AI Assistant**. I can answer general questions, look up real-time air quality "
            "for any Indian city (including Chandigarh, Mohali, Kharar, Delhi, Mumbai), explain health risks, or help you with "
            "environmental guidance. What's on your mind today?",
            "airsense:assistant"
        )
    if "who are you" in msg_lower or "what are you" in msg_lower:
        return (
            "I am **AirSense AI**, a conversational environmental health assistant built for India. "
            "I monitor live CPCB ground stations and satellite atmospheric data, predict upcoming pollution trends, and provide "
            "actionable health advice.",
            "airsense:assistant"
        )
    if "thank" in msg_lower:
        return ("You're very welcome! Breathe clean, stay safe, and let me know if you need anything else.", "airsense:assistant")

    # City-specific live AQI lookup across our 111 places
    from sqlalchemy import select
    from ..db import SessionLocal
    from ..models import Place, Measurement, utcnow
    from ..services.aqi import category_for, compute_aqi

    try:
        with SessionLocal() as db:
            places = db.execute(select(Place)).scalars().all()
            # Sort places by name length descending so longer/more specific names match first
            sorted_places = sorted(places, key=lambda p: len(p.name), reverse=True)
            matched_place = None
            for p in sorted_places:
                if p.name.lower() in msg_lower:
                    matched_place = p
                    break

            if matched_place:
                now_utc = utcnow()
                from .live import snapshot
                from ..routers.places import _recent_rows, _regional_baseline

                rows = _recent_rows(db, [matched_place.name], now_utc).get(matched_place.name, [])
                snap = snapshot(rows, now_utc)
                aqi_obj = snap.get("aqi")
                if aqi_obj and aqi_obj.get("aqi") is not None:
                    val = aqi_obj["aqi"]
                    lbl = aqi_obj.get("label", "Moderate")
                    latest = snap.get("latest") or {}
                    p25 = latest.get("pm25")
                    p10 = latest.get("pm10")
                    src = "📡 Ground Station" if matched_place.station_id else "🛰️ Atmospheric Satellite Grid"
                else:
                    base = _regional_baseline(matched_place)
                    val = base["aqi"]
                    lbl = base["label"]
                    p25 = base["pm25"]
                    p10 = base["pm10"]
                    src = "🛰️ Atmospheric Baseline"

                reply = (
                    f"📍 **Live Air Quality in {matched_place.name} ({matched_place.state}):**\n\n"
                    f"• **Current 24h AQI:** **{val}** ({lbl})\n"
                    f"• **PM2.5:** {p25} μg/m³ | **PM10:** {p10} μg/m³\n"
                    f"• **Sensor Basis:** {src}\n\n"
                )
                if val <= 100:
                    reply += "✅ **Health Status:** Air quality is acceptable. Safe for outdoor activities and exercise."
                elif val <= 200:
                    reply += "⚠️ **Health Status:** Moderate air. Sensitive groups, elderly, and children should avoid prolonged intense outdoor exertion."
                elif val <= 300:
                    reply += "🛑 **Health Status:** Poor air quality. Limit outdoor exercise. Wearing a certified N95 mask is strongly advised."
                else:
                    reply += "🚨 **Health Warning:** Very Poor to Severe pollution! Avoid outdoor sports. Keep windows shut and use indoor air purifiers."

                return reply, "airsense:live-data"
    except Exception:
        pass

    # Internet / Knowledge Search via DuckDuckGo Instant Answer API
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={requests.utils.quote(msg)}&format=json&no_html=1&skip_disambig=1"
        res = requests.get(ddg_url, timeout=4)
        if res.status_code == 200:
            ddg_data = res.json()
            abstract = ddg_data.get("AbstractText") or ddg_data.get("Answer")
            if not abstract:
                related = ddg_data.get("RelatedTopics", [])
                for item in related:
                    if isinstance(item, dict) and item.get("Text"):
                        abstract = item.get("Text")
                        break
            if abstract:
                return (
                    f"🌐 **Web Summary:**\n\n{abstract}\n\n"
                    f"*(Source: DuckDuckGo Knowledge Base)*",
                    "web:duckduckgo"
                )
    except Exception:
        pass

    # Wikipedia REST API Fallback for general encyclopedic queries
    try:
        clean_q = msg.lower()
        for prefix in ["what is ", "who is ", "tell me about ", "explain ", "how does ", "why is "]:
            if clean_q.startswith(prefix):
                clean_q = clean_q[len(prefix):]
                break
        clean_q = clean_q.strip(" ?.!\"'")
        if len(clean_q) >= 3:
            w_search = requests.get(
                f"https://en.wikipedia.org/w/api.php?action=opensearch&search={requests.utils.quote(clean_q)}&limit=1&format=json",
                headers={"User-Agent": "AirSenseIndia/1.0"},
                timeout=3
            )
            if w_search.status_code == 200:
                s_data = w_search.json()
                if len(s_data) > 1 and s_data[1]:
                    title = s_data[1][0]
                    w_sum = requests.get(
                        f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}",
                        headers={"User-Agent": "AirSenseIndia/1.0"},
                        timeout=3
                    )
                    if w_sum.status_code == 200:
                        w_res = w_sum.json()
                        extract = w_res.get("extract")
                        if extract and len(extract) > 40:
                            return (
                                f"🌐 **{w_res.get('title', title)}:**\n\n{extract}\n\n"
                                f"*(Source: Wikipedia Knowledge Base)*",
                                "web:wikipedia"
                            )
    except Exception:
        pass

    # Specialized Environmental & Seasonal Questions
    if "diwali" in msg_lower:
        reply = (
            "🎆 **Diwali & Air Quality Impact in India:**\n\n"
            "During Diwali night and the following 48 hours, particulate pollution (PM2.5 and PM10) routinely surges by "
            "2x to 3x across northern and western Indian cities due to intensive firecracker combustion. Combined with cold weather "
            "and thermal inversion (where cold surface air is trapped beneath warm air), the smoke lingers at ground level.\n\n"
            "**Recommended Precautions:**\n"
            "• Keep doors and windows tightly sealed, especially between 8 PM and 6 AM.\n"
            "• Use certified N95/FFP2 respirators if venturing outdoors.\n"
            "• Vulnerable individuals (asthma, COPD, children, elderly) should remain indoors and keep rescue inhalers accessible."
        )
    elif "stubble" in msg_lower or "burning" in msg_lower or "punjab" in msg_lower or "haryana" in msg_lower:
        reply = (
            "🌾 **Crop Residue (Stubble) Burning Impact:**\n\n"
            "Between mid-October and late November, farmers in Punjab, Haryana, and western UP clear paddy straw to prepare for wheat sowing. "
            "Northwesterly winds transport massive smoke plumes across the Indo-Gangetic Plains directly into Delhi NCR and surrounding regions.\n\n"
            "This seasonal surge is an engineered feature in our AI forecasting model, allowing AirSense to predict upcoming spikes days in advance."
        )
    elif "mask" in msg_lower or "n95" in msg_lower:
        reply = (
            "😷 **Mask Guidance for Indian Air Pollution:**\n\n"
            "• **Standard Cloth / Surgical Masks:** Ineffective for fine PM2.5 particles (they only filter particles larger than 3-5 μm).\n"
            "• **N95 or FFP2 Masks:** Certified to filter at least 95% of airborne particles down to 0.3 μm. Highly recommended when AQI exceeds 200 (Poor to Severe).\n"
            "• Ensure a snug seal around your nose and chin with no air leaks."
        )
    elif "jog" in msg_lower or "run" in msg_lower or "exercise" in msg_lower or "workout" in msg_lower:
        reply = (
            "🏃 **Exercise & Air Quality Guidelines:**\n\n"
            "• **AQI 0 - 100 (Good / Satisfactory):** Completely safe for all outdoor running, jogging, and sports.\n"
            "• **AQI 101 - 200 (Moderate):** Healthy adults can jog; people with asthma or heart conditions should reduce intensity.\n"
            "• **AQI 201+ (Poor / Severe):** Outdoor cardio should be avoided. Increased breathing volume pulls fine particulates deep into your bloodstream.\n"
            "• **Tip:** Early morning hours in winter suffer from ground temperature inversions; late afternoons are typically cleaner."
        )
    elif "difference" in msg_lower or "pm2.5" in msg_lower or "pm10" in msg_lower:
        reply = (
            "🔬 **PM2.5 vs PM10 Explained:**\n\n"
            "• **PM10 (Coarse Particles, < 10 μm):** Road dust, construction debris, pollen. These primarily irritate the eyes, nasal passages, and upper throat.\n"
            "• **PM2.5 (Fine Particles, < 2.5 μm):** Vehicle exhaust, firecracker smoke, agricultural fires. About 30 times thinner than human hair. "
            "They penetrate deep into the alveoli of the lungs and enter the bloodstream, causing cardiovascular and pulmonary strain."
        )
    else:
        reply = (
            f"🤖 **AirSense AI:**\n\n"
            f"You asked: *\"{msg}\"*\n\n"
            "I can help you with:\n"
            "1. **City AQI Lookups:** Ask *\"What is the AQI in Chandigarh?\"*, *\"Mohali air quality\"*, or *\"Delhi pollution\"*.\n"
            "2. **Health Advice:** Ask about masks, safe jogging hours, or precautions for asthma patients.\n"
            "3. **General Knowledge:** For full general conversation like ChatGPT, you can also connect a free Groq API key in your `.env` file!"
        )

    return reply, "airsense:assistant"
