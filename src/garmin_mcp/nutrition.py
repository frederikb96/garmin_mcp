"""
Nutrition management tools for Garmin Connect MCP Server.

Uses garth nutrition module directly (not garminconnect) since
python-garminconnect has no nutrition API support.
"""

import json
from typing import Optional

from garth.nutrition import (
    CustomFood,
    CustomMeal,
    DailyNutritionLog,
    FavoriteFoods,
    FoodLog,
    FoodSearch,
    MealDefinitions,
    NutritionSettings,
    QuickAdd,
)

garmin_client = None


def configure(client) -> None:
    """Configure the module with the Garmin client instance."""
    global garmin_client
    garmin_client = client


def _garth():
    """Get the garth client from the garminconnect Garmin instance."""
    return garmin_client.garth


def _resolve_meal_id(meal: str, day: str | None = None) -> int:
    """Resolve a meal name to its numeric meal_id.

    Args:
        meal: Meal name (BREAKFAST, LUNCH, DINNER, SNACKS)
        day: Optional date in YYYY-MM-DD format

    Returns:
        The meal_id for the given meal name

    Raises:
        ValueError: If meal name not found in user's meal definitions
    """
    meals = MealDefinitions.get(day=day, client=_garth())
    upper = meal.strip().upper()
    for m in meals:
        if m.meal_name.upper() == upper:
            return m.meal_id
    available = [m.meal_name for m in meals]
    raise ValueError(f"Unknown meal '{meal}'. Available: {available}")


def _curate_nutrition_content(nc) -> dict:
    """Extract key fields from a NutritionContent object."""
    if nc is None:
        return {}
    curated = {
        "serving_id": nc.serving_id,
        "serving_unit": nc.serving_unit,
        "number_of_units": nc.number_of_units,
        "calories": nc.calories,
        "protein": nc.protein,
        "fat": nc.fat,
        "carbs": nc.carbs,
        "fiber": nc.fiber,
        "sugar": nc.sugar,
    }
    return {k: v for k, v in curated.items() if v is not None}


def _curate_food_meta(fm) -> dict:
    """Extract key fields from a FoodMetaData object."""
    if fm is None:
        return {}
    curated = {
        "food_id": fm.food_id,
        "food_name": fm.food_name,
        "brand_name": fm.brand_name,
        "source": fm.source,
    }
    return {k: v for k, v in curated.items() if v is not None}


def _curate_search_result(sr) -> dict:
    """Extract key fields from a SearchResult-like object."""
    result = _curate_food_meta(sr.food_meta_data)
    if sr.nutrition_contents:
        result["servings"] = [
            _curate_nutrition_content(nc) for nc in sr.nutrition_contents
        ]
    if sr.is_favorite is not None:
        result["is_favorite"] = sr.is_favorite
    return result


def _curate_logged_food(lf) -> dict:
    """Extract key fields from a LoggedFood object."""
    curated: dict = {}
    if lf.log_id:
        curated["log_id"] = lf.log_id
    curated.update(_curate_food_meta(lf.food_meta_data))
    if lf.serving_qty is not None:
        curated["serving_qty"] = lf.serving_qty
    if lf.selected_nutrition_content:
        curated["nutrition"] = _curate_nutrition_content(
            lf.selected_nutrition_content
        )
    return curated


def _curate_daily_log(log: DailyNutritionLog) -> dict:
    """Curate a DailyNutritionLog into a clean response dict."""
    goals = {}
    if log.daily_nutrition_goals:
        g = log.daily_nutrition_goals
        goals = {
            "calories": g.calories,
            "protein": g.protein,
            "fat": g.fat,
            "carbs": g.carbs,
        }
        goals = {k: v for k, v in goals.items() if v is not None}

    totals = {}
    if log.daily_nutrition_content:
        t = log.daily_nutrition_content
        totals = {
            "calories": t.calories,
            "protein": t.protein,
            "fat": t.fat,
            "carbs": t.carbs,
        }
        totals = {k: v for k, v in totals.items() if v is not None}

    meals = []
    for md in log.meal_details:
        meal_data: dict = {
            "meal_name": md.meal.meal_name,
            "meal_id": md.meal.meal_id,
        }
        if md.meal_nutrition_content:
            meal_data["totals"] = _curate_nutrition_content(
                md.meal_nutrition_content
            )
        if md.logged_foods:
            meal_data["foods"] = [
                _curate_logged_food(f) for f in md.logged_foods
            ]
        meals.append(meal_data)

    curated = {
        "date": log.meal_date,
        "daily_goals": goals,
        "daily_totals": totals,
        "meals": meals,
    }
    return {k: v for k, v in curated.items() if v is not None}


def register_tools(app):
    """Register all nutrition tools with the MCP server app."""

    # ── READ TOOLS ──────────────────────────────────────────────────

    @app.tool()
    async def get_nutrition_log(date: str) -> str:
        """Get full daily nutrition log with all meals and logged foods.

        Returns meal-by-meal breakdown including food names, servings, and
        macros. Use get_nutrition_summary for a lightweight totals-only view.

        Args:
            date: Date in YYYY-MM-DD format
        """
        try:
            log = DailyNutritionLog.get(day=date, client=_garth())
            return json.dumps(_curate_daily_log(log), indent=2)
        except Exception as e:
            return f"Error getting nutrition log: {e}"

    @app.tool()
    async def get_nutrition_summary(date: str) -> str:
        """Get lightweight daily nutrition totals vs goals (~300 bytes).

        Returns only aggregate calories and macros compared to goals.
        Use get_nutrition_log for the full meal-by-meal breakdown.

        Args:
            date: Date in YYYY-MM-DD format
        """
        try:
            log = DailyNutritionLog.get(day=date, client=_garth())
            goals = {}
            if log.daily_nutrition_goals:
                g = log.daily_nutrition_goals
                goals = {
                    "calories": g.calories,
                    "protein": g.protein,
                    "fat": g.fat,
                    "carbs": g.carbs,
                }
                goals = {k: v for k, v in goals.items() if v is not None}

            totals = {}
            if log.daily_nutrition_content:
                t = log.daily_nutrition_content
                totals = {
                    "calories": t.calories,
                    "protein": t.protein,
                    "fat": t.fat,
                    "carbs": t.carbs,
                }
                totals = {k: v for k, v in totals.items() if v is not None}

            curated = {
                "date": log.meal_date,
                "totals": totals,
                "goals": goals,
            }
            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error getting nutrition summary: {e}"

    @app.tool()
    async def get_nutrition_settings(
        date: Optional[str] = None,
    ) -> str:
        """Get nutrition goals and settings (calorie target, macro goals, locale).

        Args:
            date: Optional date in YYYY-MM-DD format (defaults to today)
        """
        try:
            s = NutritionSettings.get(day=date, client=_garth())
            curated = {
                "calorie_goal": s.calorie_goal,
                "weight_change_type": s.weight_change_type,
                "auto_calorie_adjustment": s.auto_calorie_adjustment,
                "region_code": s.region_code,
                "language_code": s.language_code,
                "starting_weight_grams": s.starting_weight,
                "target_weight_goal_grams": s.target_weight_goal,
                "target_date": s.target_date,
            }
            if s.macro_goals:
                mg = s.macro_goals
                curated["macro_goals"] = {
                    "calories": mg.calories,
                    "protein": mg.protein,
                    "fat": mg.fat,
                    "carbs": mg.carbs,
                }
            curated = {k: v for k, v in curated.items() if v is not None}
            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error getting nutrition settings: {e}"

    @app.tool()
    async def search_foods(
        query: str,
        start: int = 0,
        limit: int = 20,
    ) -> str:
        """Search the Garmin food database by name or brand.

        Returns food_id and serving_id needed for log_food.
        Each result includes available serving sizes with macros.

        Args:
            query: Search term (e.g. "banana", "oatmeal", brand name)
            start: Pagination offset (default 0)
            limit: Max results to return (default 20, max 50)
        """
        try:
            results = FoodSearch.search(
                query=query, start=start, limit=limit, client=_garth()
            )
            curated = {
                "query": query,
                "results": [_curate_search_result(r) for r in results.results],
                "has_more": results.more_data_available,
            }
            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error searching foods: {e}"

    @app.tool()
    async def get_recent_foods(
        meal: str,
        date: Optional[str] = None,
    ) -> str:
        """Get recently and frequently logged foods for a specific meal.

        Useful for quickly re-logging common foods without searching.

        Args:
            meal: Meal name (BREAKFAST, LUNCH, DINNER, or SNACKS)
            date: Optional date in YYYY-MM-DD format (defaults to today)
        """
        try:
            meal_id = _resolve_meal_id(meal, date)
            recent = FoodSearch.recent(
                meal_id=meal_id, day=date, client=_garth()
            )
            curated = {
                "meal": meal.upper(),
                "frequent_foods": [
                    _curate_search_result(f) for f in recent.frequent_foods
                ],
                "recent_foods": [
                    _curate_search_result(f) for f in recent.recent_foods
                ],
            }
            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error getting recent foods: {e}"

    @app.tool()
    async def list_favorite_foods(
        query: str = "",
        start: int = 0,
        limit: int = 20,
    ) -> str:
        """List or search favorite (starred) foods.

        Args:
            query: Optional search filter within favorites
            start: Pagination offset (default 0)
            limit: Max results (default 20, max 50)
        """
        try:
            favs = FavoriteFoods.list(
                query=query, start=start, limit=limit, client=_garth()
            )
            curated = {
                "favorites": [_curate_search_result(f) for f in favs.items],
                "has_more": favs.has_more,
            }
            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error listing favorites: {e}"

    @app.tool()
    async def list_custom_foods(
        query: str = "",
        start: int = 0,
        limit: int = 20,
    ) -> str:
        """List or search user-created custom foods.

        Args:
            query: Optional search filter
            start: Pagination offset (default 0)
            limit: Max results (default 20)
        """
        try:
            foods = CustomFood.list(
                query=query, start=start, limit=limit, client=_garth()
            )
            curated = {
                "custom_foods": [
                    _curate_search_result(f) for f in foods.items
                ],
                "has_more": foods.more_data_available,
            }
            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error listing custom foods: {e}"

    # ── WRITE TOOLS ─────────────────────────────────────────────────

    @app.tool()
    async def log_food(
        date: str,
        meal: str,
        food_id: str | int,
        serving_id: str | int,
        source: str,
        serving_qty: float = 1,
    ) -> str:
        """Log a food item to a meal. Use search_foods first to find food_id,
        serving_id, and source. For quick calorie/macro entry without searching,
        use quick_add_nutrition instead.

        Args:
            date: Date in YYYY-MM-DD format
            meal: Meal name (BREAKFAST, LUNCH, DINNER, or SNACKS)
            food_id: Food ID from search results
            serving_id: Serving ID from search results
            source: Food source from search results (e.g. FATSECRET, GARMIN)
            serving_qty: Number of servings (default 1)
        """
        try:
            food_id, serving_id = str(food_id), str(serving_id)
            meal_id = _resolve_meal_id(meal, date)
            log = FoodLog.add(
                day=date,
                meal_id=meal_id,
                food_id=food_id,
                serving_id=serving_id,
                source=source,
                serving_qty=serving_qty,
                client=_garth(),
            )
            return json.dumps(_curate_daily_log(log), indent=2)
        except Exception as e:
            return f"Error logging food: {e}"

    @app.tool()
    async def quick_add_nutrition(
        date: str,
        meal: str,
        name: str,
        calories: float,
        protein: float = 0,
        fat: float = 0,
        carbs: float = 0,
    ) -> str:
        """Quick-add a nutrition entry by name and macros without food search.

        Use this when you know the approximate macros (e.g. "Homemade smoothie,
        350 cal, 20g protein"). For logging a specific food from the database,
        use log_food instead.

        Args:
            date: Date in YYYY-MM-DD format
            meal: Meal name (BREAKFAST, LUNCH, DINNER, or SNACKS)
            name: Display name for the entry
            calories: Total calories
            protein: Protein in grams (default 0)
            fat: Fat in grams (default 0)
            carbs: Carbohydrates in grams (default 0)
        """
        try:
            meal_id = _resolve_meal_id(meal, date)
            log = QuickAdd.add(
                day=date,
                meal_id=meal_id,
                name=name,
                calories=calories,
                protein=protein,
                fat=fat,
                carbs=carbs,
                client=_garth(),
            )
            return json.dumps(_curate_daily_log(log), indent=2)
        except Exception as e:
            return f"Error quick-adding nutrition: {e}"

    @app.tool()
    async def update_food_log(
        date: str,
        log_id: str | int,
        meal: str,
        food_id: str | int,
        serving_id: str | int,
        source: str,
        serving_qty: float = 1,
    ) -> str:
        """Update an existing food log entry (e.g. change serving quantity).

        Get the log_id from get_nutrition_log results.

        Args:
            date: Date in YYYY-MM-DD format
            log_id: Log entry ID to update (from get_nutrition_log)
            meal: Meal name (BREAKFAST, LUNCH, DINNER, or SNACKS)
            food_id: Food ID
            serving_id: Serving ID
            source: Food source (e.g. FATSECRET, GARMIN)
            serving_qty: New number of servings (default 1)
        """
        try:
            log_id, food_id, serving_id = str(log_id), str(food_id), str(serving_id)
            meal_id = _resolve_meal_id(meal, date)
            log = FoodLog.update(
                day=date,
                log_id=log_id,
                meal_id=meal_id,
                food_id=food_id,
                serving_id=serving_id,
                source=source,
                serving_qty=serving_qty,
                client=_garth(),
            )
            return json.dumps(_curate_daily_log(log), indent=2)
        except Exception as e:
            return f"Error updating food log: {e}"

    @app.tool()
    async def remove_food_log(
        date: str,
        log_ids: str,
    ) -> str:
        """Remove one or more food entries from a day's log.

        Get log_ids from get_nutrition_log results.

        Args:
            date: Date in YYYY-MM-DD format
            log_ids: Comma-separated log entry IDs to remove
        """
        try:
            ids = [lid.strip() for lid in log_ids.split(",") if lid.strip()]
            if not ids:
                return "Error: no log_ids provided"
            FoodLog.remove(day=date, log_ids=ids, client=_garth())
            return json.dumps({
                "status": "success",
                "date": date,
                "removed_count": len(ids),
            }, indent=2)
        except Exception as e:
            return f"Error removing food log entries: {e}"

    @app.tool()
    async def add_favorite_food(
        food_id: str | int,
        serving_id: str | int,
        source: str,
        serving_qty: float = 1,
    ) -> str:
        """Add a food to favorites for quick access. Get IDs from search_foods.

        Args:
            food_id: Food ID from search results
            serving_id: Serving ID from search results
            source: Food source (e.g. FATSECRET, GARMIN)
            serving_qty: Serving quantity (default 1)
        """
        try:
            food_id, serving_id = str(food_id), str(serving_id)
            FavoriteFoods.add(
                food_id=food_id,
                serving_id=serving_id,
                source=source,
                serving_qty=serving_qty,
                client=_garth(),
            )
            return json.dumps({
                "status": "success",
                "food_id": food_id,
            }, indent=2)
        except Exception as e:
            return f"Error adding favorite: {e}"

    @app.tool()
    async def remove_favorite_food(food_id: str | int) -> str:
        """Remove a food from favorites.

        Args:
            food_id: Food ID to unfavorite
        """
        try:
            food_id = str(food_id)
            FavoriteFoods.remove(food_id=food_id, client=_garth())
            return json.dumps({
                "status": "success",
                "food_id": food_id,
            }, indent=2)
        except Exception as e:
            return f"Error removing favorite: {e}"

    @app.tool()
    async def create_custom_food(
        food_name: str,
        serving_unit: str,
        number_of_units: float,
        calories: float,
        protein: Optional[float] = None,
        fat: Optional[float] = None,
        carbs: Optional[float] = None,
        fiber: Optional[float] = None,
        sugar: Optional[float] = None,
    ) -> str:
        """Create a custom food with nutrition info per serving.

        Args:
            food_name: Name for the custom food
            serving_unit: Unit name (e.g. "g", "piece", "cup", "serving")
            number_of_units: How many units make one serving
            calories: Calories per serving
            protein: Protein grams per serving
            fat: Fat grams per serving
            carbs: Carbohydrate grams per serving
            fiber: Fiber grams per serving
            sugar: Sugar grams per serving
        """
        try:
            result = CustomFood.create(
                food_name=food_name,
                serving_unit=serving_unit,
                number_of_units=number_of_units,
                calories=calories,
                protein=protein,
                fat=fat,
                carbs=carbs,
                fiber=fiber,
                sugar=sugar,
                client=_garth(),
            )
            return json.dumps(_curate_search_result(result), indent=2)
        except Exception as e:
            return f"Error creating custom food: {e}"

    @app.tool()
    async def delete_custom_food(food_id: str | int) -> str:
        """Delete a user-created custom food.

        Args:
            food_id: Custom food ID to delete (from list_custom_foods)
        """
        try:
            food_id = str(food_id)
            CustomFood.delete(food_id=food_id, client=_garth())
            return json.dumps({
                "status": "success",
                "food_id": food_id,
            }, indent=2)
        except Exception as e:
            return f"Error deleting custom food: {e}"

    # ── CUSTOM MEAL TOOLS ───────────────────────────────────────────

    @app.tool()
    async def list_custom_meals(
        query: str = "",
        start: int = 0,
        limit: int = 20,
    ) -> str:
        """List or search user-created custom meals (saved food combinations).

        Args:
            query: Optional search filter
            start: Pagination offset (default 0)
            limit: Max results (default 20)
        """
        try:
            meals = CustomMeal.list(
                query=query, start=start, limit=limit, client=_garth()
            )
            curated = {
                "custom_meals": [
                    _curate_search_result(m) for m in meals.items
                ],
                "has_more": meals.has_more,
            }
            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error listing custom meals: {e}"

    @app.tool()
    async def create_custom_meal(
        name: str,
        foods_json: str | list,
    ) -> str:
        """Create a custom meal from a list of foods.

        The foods_json should be a JSON array where each item contains
        the food data from search results in Garmin's camelCase API format
        (foodId, servingId, source, servingQty, etc.).

        Args:
            name: Name for the custom meal
            foods_json: JSON array of food items with their serving details
        """
        try:
            if isinstance(foods_json, list):
                foods = foods_json
            else:
                foods = json.loads(foods_json)
                if not isinstance(foods, list):
                    return "Error: foods_json must be a JSON array"
            result = CustomMeal.create(
                name=name, foods=foods, client=_garth()
            )
            curated = {
                "custom_meal_id": result.custom_meal_id,
                "name": result.name,
                "food_count": len(result.foods),
            }
            if result.content_summary:
                curated["totals"] = _curate_nutrition_content(
                    result.content_summary
                )
            return json.dumps(curated, indent=2)
        except json.JSONDecodeError:
            return "Error: foods_json is not valid JSON"
        except Exception as e:
            return f"Error creating custom meal: {e}"

    return app
