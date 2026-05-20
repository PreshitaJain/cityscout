from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from cityscout import get_recommendations, CATEGORY_LABELS

app = FastAPI(title="CityScout")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/search")
def search(city: str = ""):
    city = city.strip()
    if not city:
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url=f"/city/{city.lower()}", status_code=303)


@app.get("/city/{city}", response_class=HTMLResponse)
def city_page(request: Request, city: str):
    data = get_recommendations(city)
    if not data:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": f"Couldn't find recommendations for '{city}'. Try a different spelling or city.",
            },
            status_code=404,
        )
    return templates.TemplateResponse(
        "city.html",
        {
            "request": request,
            "city": data.get("city", city),
            "categories": data.get("categories", {}),
            "category_labels": CATEGORY_LABELS,
        },
    )


@app.get("/api/city/{city}")
def city_api(city: str):
    data = get_recommendations(city)
    if not data:
        return JSONResponse({"error": "not found", "city": city}, status_code=404)
    return data
