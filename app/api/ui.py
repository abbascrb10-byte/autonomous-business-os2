import html
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_provider import llm_provider
from app.config.settings import settings
from app.database.models import DemandSignal
from app.database.session import get_db_session
from app.merchants.adapters import amazon_adapter, ebay_adapter, etsy_adapter

router = APIRouter()

API_ROUTES = [
    ("GET", "/health", "فحص أساسي لخدمة التطبيق."),
    ("GET", "/readiness", "فحص قاعدة البيانات ومزود الذكاء الاصطناعي."),
    ("POST", "/api/v1/demand", "إرسال إشارة طلب جديدة وتشغيل سير العمل."),
    ("GET", "/api/v1/intents/{intent_id}", "عرض نية شراء محددة."),
    ("GET", "/api/v1/offers", "عرض العروض المرتبطة بنوايا الشراء."),
    ("GET", "/api/v1/dashboard/stats", "إحصاءات التحويل والتعلم."),
    ("GET", "/api/v1/analytics/funnel", "مقاييس مسار التحويل."),
    ("GET", "/api/v1/learning/metrics", "ملخص نتائج التعلم."),
    ("GET", "/api/v1/tracking/click/{tracking_id}", "تسجيل نقرة على عرض."),
    ("POST", "/api/v1/tracking/conversion", "تسجيل تحويل مؤكد."),
]


def _status_chip(value: bool) -> str:
    label = "متصل" if value else "غير متصل"
    state = "ok" if value else "bad"
    return f'<span class="chip {state}">{label}</span>'


async def _redis_ready() -> bool:
    try:
        from redis import asyncio as aioredis

        client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=0.5)
        try:
            await client.ping()
            return True
        finally:
            await client.aclose()
    except Exception:
        return False


async def _dashboard_data(session: AsyncSession) -> dict[str, Any]:
    try:
        await session.execute(select(1))
        database_ready = True
    except Exception:
        database_ready = False

    recent = []
    if database_ready:
        result = await session.execute(
            select(DemandSignal).order_by(desc(DemandSignal.created_at)).limit(10)
        )
        recent = [
            {
                "source_type": signal.source_type,
                "content": signal.normalized_content or signal.raw_content,
                "status": signal.status,
                "created_at": signal.created_at.isoformat(),
            }
            for signal in result.scalars().all()
        ]

    return {
        "database": database_ready,
        "redis": await _redis_ready(),
        "ai_provider": llm_provider.is_configured,
        "keys": {
            "eBay": ebay_adapter.is_configured,
            "Etsy": etsy_adapter.is_configured,
            "Amazon": amazon_adapter.is_configured,
            "Tavily": bool(settings.TAVILY_API_KEY),
            "Twitter": bool(settings.TWITTER_BEARER_TOKEN),
            "OpenAI": bool(settings.OPENAI_API_KEY),
            "Gemini": bool(settings.GEMINI_API_KEY),
        },
        "recent": recent,
    }


@router.get("/ui", response_class=HTMLResponse)
async def dashboard_ui(session: AsyncSession = Depends(get_db_session)):
    data = await _dashboard_data(session)
    return HTMLResponse(_render_page(data))


def _render_page(data: dict[str, Any]) -> str:
    status_items = [
        ("قاعدة البيانات", data["database"]),
        ("Redis", data["redis"]),
        ("مزود الذكاء الاصطناعي", data["ai_provider"]),
    ]
    statuses = "".join(
        f'<div class="status-card"><strong>{name}</strong>{_status_chip(value)}</div>'
        for name, value in status_items
    )
    keys = "".join(
        f'<li><span>{html.escape(name)}</span>{_status_chip(value)}</li>'
        for name, value in data["keys"].items()
    )
    routes = "".join(
        f'<li><code>{method}</code><strong>{path}</strong><span>{description}</span></li>'
        for method, path, description in API_ROUTES
    )
    signals = "".join(
        f'<tr><td>{html.escape(item["source_type"])}</td>'
        f'<td>{html.escape(item["content"][:100])}</td>'
        f'<td>{html.escape(item["status"])}</td>'
        f'<td>{html.escape(item["created_at"][:19].replace("T", " "))}</td></tr>'
        for item in data["recent"]
    ) or '<tr><td colspan="4" class="empty">لا توجد إشارات واردة بعد.</td></tr>'
    return f'''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>لوحة تشغيل GPIE</title><style>
:root{{--ink:#17211f;--muted:#66736f;--line:#d9e1dc;--paper:#f7f8f4;--card:#fff;--accent:#d96c3b;--green:#237a57;--red:#a53c3c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:Tahoma,Arial,sans-serif;line-height:1.6}}
header{{padding:34px max(22px,calc((100% - 1180px)/2));background:#183b38;color:#fff;display:flex;justify-content:space-between;gap:20px;align-items:end}}
h1{{margin:0;font-size:clamp(1.7rem,4vw,3rem)}}header p{{margin:4px 0 0;color:#c8dad3}}main{{max-width:1180px;margin:26px auto;padding:0 22px;display:grid;gap:22px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.status-card,.panel{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:18px;box-shadow:0 7px 22px #183b3809}}
.status-card{{display:flex;justify-content:space-between;align-items:center}}.panel h2{{margin:0 0 14px;font-size:1.15rem;border-bottom:1px solid var(--line);padding-bottom:10px}}
.chip{{border-radius:999px;padding:2px 9px;font-size:.78rem;font-weight:bold;white-space:nowrap}}.ok{{color:var(--green);background:#e0f2e9}}.bad{{color:var(--red);background:#fbe7e5}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}ul{{list-style:none;padding:0;margin:0}}.keys li,.routes li{{display:flex;align-items:center;gap:10px;border-bottom:1px solid #edf1ed;padding:8px 0}}.keys li span:first-child{{flex:1}}
.routes li span{{color:var(--muted);font-size:.88rem;margin-right:auto}}code{{background:#eef1ec;padding:2px 6px;border-radius:4px;color:var(--accent);font-weight:bold}}.routes strong{{direction:ltr;text-align:left}}
form{{display:grid;gap:10px}}label{{font-weight:bold;font-size:.9rem}}input,textarea{{font:inherit;border:1px solid var(--line);border-radius:5px;padding:10px;background:#fff}}textarea{{min-height:90px;resize:vertical}}button{{border:0;border-radius:5px;background:var(--accent);color:#fff;padding:11px 18px;font:inherit;font-weight:bold;cursor:pointer}}button:hover{{filter:brightness(.94)}}#form-result{{min-height:24px;color:var(--muted)}}.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;min-width:650px}}th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:right}}th{{color:var(--muted);font-size:.82rem}}.empty{{text-align:center;color:var(--muted)}}
@media(max-width:760px){{header{{display:block}}.grid,.two{{grid-template-columns:1fr}}main{{padding:0 14px;margin-top:14px}}.routes li{{display:grid;grid-template-columns:auto 1fr}}.routes li span{{grid-column:1/-1;margin:0}}}}
</style></head><body><header><div><h1>لوحة تشغيل GPIE</h1><p>مراقبة النظام وإرسال إشارات الطلب من مكان واحد</p></div><strong>/ui</strong></header><main>
<section class="grid">{statuses}</section><section class="two"><div class="panel"><h2>حالة مفاتيح التكامل</h2><ul class="keys">{keys}</ul></div><div class="panel"><h2>إرسال إشارة اختبار</h2><form id="demand-form"><label for="content">نص الطلب</label><textarea id="content" required placeholder="أحتاج إلى كاميرا Sony تحت 1800 يورو"></textarea><label for="contact">معرّف التواصل (اختياري)</label><input id="contact" placeholder="buyer@example.com"><button type="submit">إرسال الطلب</button><div id="form-result"></div></form></div></section>
<section class="panel"><h2>مسارات API المتاحة</h2><ul class="routes">{routes}</ul></section><section class="panel"><h2>آخر 10 إشارات واردة</h2><div class="table-wrap"><table><thead><tr><th>المصدر</th><th>المحتوى</th><th>الحالة</th><th>التاريخ</th></tr></thead><tbody>{signals}</tbody></table></div></section>
</main><script>document.getElementById('demand-form').addEventListener('submit',async function(event){{event.preventDefault();const result=document.getElementById('form-result');result.textContent='جار الإرسال...';try{{const response=await fetch('/api/v1/demand',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{source_type:'owned_api',source_id:'ui',content:document.getElementById('content').value,contact_identifier:document.getElementById('contact').value||null}})}});const body=await response.json();if(!response.ok)throw new Error(body.detail||'تعذر إرسال الطلب');result.textContent='تم استلام الطلب: '+body.status;setTimeout(()=>location.reload(),700)}}catch(error){{result.textContent=error.message}}}});</script></body></html>'''
