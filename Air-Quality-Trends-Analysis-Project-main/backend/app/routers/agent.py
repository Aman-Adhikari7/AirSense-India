from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..schemas import AgentPlanIn, AgentPlanOut, ToolStep, AgentExecIn, AgentExecOut
from ..core.config import settings
from ..core.security import require_user
from ..models import Place, utcnow
from ..services.live import snapshot
from ..services.scraper import ensure_window_for_city
from ..services.forecast import forecast_city, forecast_cities
from ..services.llama_client import chat_with_llm, plan_with_llama
from ..utils.compare import compare_logic
from .places import _recent_rows

public_router = APIRouter()
router = APIRouter(dependencies=[Depends(require_user)])


class ChatIn(BaseModel):
    message: str
    place_id: Optional[int] = None


@public_router.post("/chat")
def chat_agent(payload: ChatIn, db: Session = Depends(get_db)):
    context = None
    if payload.place_id:
        place = db.get(Place, payload.place_id)
        if place:
            now = utcnow()
            snap = snapshot(_recent_rows(db, [place.name], now).get(place.name, []), now)
            aqi = snap.get("aqi")
            context = {
                "place_name": place.name,
                "state": place.state,
                "aqi": aqi.get("aqi") if aqi else None,
                "label": aqi.get("label") if aqi else "Moderate",
            }
    reply, provider = chat_with_llm(payload.message, context)
    return {"reply": reply, "provider": provider, "context": context}

TOOLS = [
    {
        "name": "scrape_city",
        "description": "Fetch & cache hourly PM2.5/PM10 for a city over the last N days using Open-Meteo; upserts into MySQL.",
        "input_schema": {"type":"object","properties":{"city":{"type":"string"},"days":{"type":"integer","minimum":1,"maximum":90,"default":7}},"required":["city"]},
        "output_schema": {"type":"object"}
    },
    {
        "name": "compare_cities",
        "description": "Compute KPIs over the last N days per city (n_points, mean_pm25, min_pm25, max_pm25) and pick best/worst (lower is better).",
        "input_schema": {"type":"object","properties":{"cities":{"type":"array","items":{"type":"string"}},"days":{"type":"integer","minimum":1,"maximum":90,"default":7}},"required":["cities"]},
        "output_schema": {"type":"object"}
    },
    {
        "name": "forecast_city",
        "description": "Forecast next H days of PM2.5 for one city with SARIMAX; returns yhat + CI.",
        "input_schema": {"type":"object","properties":{"city":{"type":"string"},"horizonDays":{"type":"integer","minimum":1,"maximum":30,"default":7},"trainDays":{"type":"integer","minimum":7,"maximum":120,"default":30},"use_cache":{"type":"boolean","default":True}},"required":["city"]},
        "output_schema": {"type":"object"}
    },
    {
        "name": "forecast_multi",
        "description": "Forecast next H days for multiple cities and rank best/worst by mean predicted PM2.5.",
        "input_schema": {"type":"object","properties":{"cities":{"type":"array","items":{"type":"string"}},"horizonDays":{"type":"integer","minimum":1,"maximum":30,"default":7},"trainDays":{"type":"integer","minimum":7,"maximum":120,"default":30},"use_cache":{"type":"boolean","default":True}},"required":["cities"]},
        "output_schema": {"type":"object"}
    },
]

def _int_arg(args: dict, key: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(args.get(key, default))
    except (TypeError, ValueError):
        raise HTTPException(400, f"'{key}' must be an integer")
    if not lo <= value <= hi:
        raise HTTPException(400, f"'{key}' must be between {lo} and {hi}")
    return value


def _city_arg(args: dict) -> str:
    city = args.get("city")
    if not isinstance(city, str) or not (1 <= len(city.strip()) <= 100):
        raise HTTPException(400, "'city' must be a non-empty string (max 100 chars)")
    return city.strip()


def _cities_arg(args: dict) -> list[str]:
    cities = args.get("cities")
    if not isinstance(cities, list) or not (1 <= len(cities) <= settings.MAX_CITIES_PER_REQUEST):
        raise HTTPException(400, f"'cities' must be a list of 1-{settings.MAX_CITIES_PER_REQUEST} names")
    out = []
    for c in cities:
        if not isinstance(c, str) or not (1 <= len(c.strip()) <= 100):
            raise HTTPException(400, "each city must be a non-empty string (max 100 chars)")
        out.append(c.strip())
    return out


def _run_tool(db: Session, name: str, args: dict) -> dict:
    """Validate arguments, then run one tool. Returns the tool result."""
    if name == "scrape_city":
        city = _city_arg(args)
        days = _int_arg(args, "days", 7, 1, settings.MAX_DAYS)
        inserted, (lat, lon) = ensure_window_for_city(db, city, days)
        return {"city": city, "days": days, "inserted": inserted, "lat": lat, "lon": lon}

    if name == "compare_cities":
        cities = _cities_arg(args)
        days = _int_arg(args, "days", 7, 1, settings.MAX_DAYS)
        for c in cities:
            ensure_window_for_city(db, c, days)
        return compare_logic(db, cities, days)

    if name == "forecast_city":
        return forecast_city(
            db, _city_arg(args),
            _int_arg(args, "horizonDays", 7, 1, 30),
            _int_arg(args, "trainDays", 30, 7, 120),
            bool(args.get("use_cache", True)),
        )

    if name == "forecast_multi":
        return forecast_cities(
            db, _cities_arg(args),
            _int_arg(args, "horizonDays", 7, 1, 30),
            _int_arg(args, "trainDays", 30, 7, 120),
            bool(args.get("use_cache", True)),
        )

    raise HTTPException(404, f"Unknown tool: {name}")


@router.get("/mcp/tools/list")
def mcp_list_tools():
    return {"tools": TOOLS}


@router.post("/mcp/tools/call")
def mcp_call_tool(call: dict, db: Session = Depends(get_db)):
    name = call.get("name")
    args = call.get("arguments", {})
    if not isinstance(name, str) or not isinstance(args, dict):
        raise HTTPException(400, "Expected {name: str, arguments: object}")
    return {"ok": True, "result": _run_tool(db, name, args)}


@router.post("/plan", response_model=AgentPlanOut)
def agent_plan(payload: AgentPlanIn):
    plan_obj = plan_with_llama(payload.prompt, TOOLS, temperature=0.2)
    steps = [ToolStep(**step) for step in plan_obj.get("plan", [])]
    return {"plan": steps, "notes": plan_obj.get("notes"), "irrelevant": plan_obj.get("irrelevant", False)}


@router.post("/execute", response_model=AgentExecOut)
def agent_execute(payload: AgentExecIn, db: Session = Depends(get_db)):
    trace: list = []
    steps: list[ToolStep] = []
    last_ok = None

    if payload.plan:
        steps = payload.plan
    elif payload.prompt:
        plan_obj = plan_with_llama(payload.prompt, TOOLS, temperature=0.2)
        steps = [ToolStep(**step) for step in plan_obj.get("plan", [])][:10]
        trace.append({"planner": {"notes": plan_obj.get("notes"), "steps": [s.model_dump() for s in steps]}})
    else:
        raise HTTPException(400, "Provide either prompt or plan")

    for step in steps:
        try:
            result = {"tool": step.name, "ok": True, "args": step.arguments, "result": _run_tool(db, step.name, step.arguments or {})}
        except HTTPException as e:
            result = {"tool": step.name, "ok": False, "args": step.arguments, "error": e.detail}
        except Exception:
            result = {"tool": step.name, "ok": False, "args": step.arguments, "error": "Tool failed"}
        trace.append(result)
        if result.get("ok"):
            last_ok = result
        else:
            break

    successes = [t for t in trace if t.get("ok")]
    return {"answer": f"Executed {len(successes)} step(s).", "trace": trace, "final": (last_ok.get("result") if last_ok else None)}
