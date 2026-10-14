from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..core.security import require_user
from ..schemas import ReportIn
from ..services.llama_client import generate_llm_forecast_report, generate_llm_report
from ..services.reporter import make_report

router = APIRouter(dependencies=[Depends(require_user)])


@router.post("/report/generate")
def generate_report(payload: ReportIn):
    pdf_bytes = make_report(payload)
    filename = f"{payload.report_type}_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/llm-comparison-note")
def generate_llm_comparison_report(report_data: Dict[str, Any]):
    """LLM-written comparison note. Needs the optional AI backend (see AGENT_ENABLED / Ollama)."""
    try:
        return generate_llm_report(
            report_data.get("comparisonData", {}),
            report_data.get("chartData", {}),
            report_data.get("cities", []),
            report_data.get("periodDays", 7),
            report_data.get("showCombined", False),
        )
    except Exception:
        raise HTTPException(status_code=503, detail="AI report notes are unavailable right now.")


@router.post("/llm-forecast-note")
def generate_llm_forecast_report_endpoint(report_data: Dict[str, Any]):
    """LLM-written forecast note. Needs the optional AI backend (see AGENT_ENABLED / Ollama)."""
    try:
        return generate_llm_forecast_report(
            report_data.get("forecastData", {}),
            report_data.get("chartData", {}),
            report_data.get("cities", []),
            report_data.get("horizonDays", 7),
            report_data.get("trainDays", 30),
            report_data.get("showCI", False),
            report_data.get("showCombined", False),
            report_data.get("selectedModel", "sarimax"),
        )
    except Exception:
        raise HTTPException(status_code=503, detail="AI report notes are unavailable right now.")
