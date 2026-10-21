"""
Activity Management functions for Garmin Connect MCP Server
"""
import json
import datetime
from typing import Any, Dict, List, Optional, Union

# The garmin_client will be set by the main file
garmin_client = None

# Output field -> Garmin keys that may carry it, in priority order. The detail
# summary and the activity lists name some of these differently.
BALANCE_FIELDS = {
    "avg_ground_contact_balance_left_percent": (
        "groundContactBalanceLeft", "avgGroundContactBalance", "groundContactBalance",
    ),
    "avg_vertical_ratio_percent": ("verticalRatio", "avgVerticalRatio"),
    "avg_power_balance_left_percent": (
        "leftBalance", "avgLeftBalance", "leftRightBalance", "powerBalanceLeft",
    ),
}


def _balance_metrics(source):
    """Pick the left/right balance and running dynamics values out of an activity dict"""
    return {
        name: next((source[k] for k in keys if source.get(k) is not None), None)
        for name, keys in BALANCE_FIELDS.items()
    }


def configure(client):
    """Configure the module with the Garmin client instance"""
    global garmin_client
    garmin_client = client


def register_tools(app):
    """Register all activity management tools with the MCP server app"""

    @app.tool()
    async def get_activities_by_date(start_date: str, end_date: str, activity_type: str = "") -> str:
        """Get activities data between specified dates, optionally filtered by activity type

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            activity_type: Optional activity type filter (e.g., cycling, running, swimming)
        """
        try:
            activities = garmin_client.get_activities_by_date(start_date, end_date, activity_type)
            if not activities:
                return json.dumps({
                    "count": 0,
                    "date_range": {"start": start_date, "end": end_date},
                    "activity_type": activity_type or None,
                    "activities": []
                }, indent=2)

            # Curate the activity list
            curated = {
                "count": len(activities),
                "date_range": {"start": start_date, "end": end_date},
                "activities": []
            }

            for a in activities:
                activity = {
                    "id": a.get('activityId'),
                    "name": a.get('activityName'),
                    "type": a.get('activityType', {}).get('typeKey'),
                    "start_time": a.get('startTimeLocal'),
                    "distance_meters": a.get('distance'),
                    "duration_seconds": a.get('duration'),
                    "calories": a.get('calories'),
                    "avg_hr_bpm": a.get('averageHR'),
                    "max_hr_bpm": a.get('maxHR'),
                    "steps": a.get('steps'),
                    "elevation_gain_meters": a.get('elevationGain'),
                    "elevation_loss_meters": a.get('elevationLoss'),
                    **_balance_metrics(a),
                }
                curated["activities"].append(activity)

            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error retrieving activities by date: {str(e)}"

    @app.tool()
    async def get_activities_fordate(date: str) -> str:
        """Get activities for a specific date

        Args:
            date: Date in YYYY-MM-DD format
        """
        try:
            data = garmin_client.get_activities_fordate(date)
            if not data:
                return f"No activities found for {date}"

            # Extract just the activities, not the embedded HR data
            activities_data = data.get('ActivitiesForDay', {})
            payload = activities_data.get('payload', [])

            if not payload:
                return f"No activities found for {date}"

            curated = {
                "date": date,
                "count": len(payload),
                "activities": []
            }

            for a in payload:
                activity = {
                    "id": a.get('activityId'),
                    "name": a.get('activityName'),
                    "type": a.get('activityType', {}).get('typeKey'),
                    "start_time": a.get('startTimeLocal'),
                    "distance_meters": a.get('distance'),
                    "duration_seconds": a.get('duration'),
                    "calories": a.get('calories'),
                    "avg_hr_bpm": a.get('averageHR'),
                    "steps": a.get('steps'),
                    "elevation_gain_meters": a.get('elevationGain'),
                    "elevation_loss_meters": a.get('elevationLoss'),
                    **_balance_metrics(a),
                    "lap_count": a.get('lapCount'),
                    "moderate_intensity_minutes": a.get('moderateIntensityMinutes'),
                    "vigorous_intensity_minutes": a.get('vigorousIntensityMinutes'),
                }
                curated["activities"].append(activity)

            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error retrieving activities for date: {str(e)}"

    @app.tool()
    async def get_activity(activity_id: int) -> str:
        """Get basic activity information

        Args:
            activity_id: ID of the activity to retrieve
        """
        try:
            activity = garmin_client.get_activity(activity_id)
            if not activity:
                return f"No activity found with ID {activity_id}"

            # Extract summary data
            summary = activity.get('summaryDTO', {})
            activity_type = activity.get('activityTypeDTO', {})
            metadata = activity.get('metadataDTO', {})

            curated = {
                "id": activity.get('activityId'),
                "name": activity.get('activityName'),
                "type": activity_type.get('typeKey'),
                "parent_type": activity_type.get('parentTypeId'),

                # Timing
                "start_time_local": summary.get('startTimeLocal'),
                "start_time_gmt": summary.get('startTimeGMT'),
                "duration_seconds": summary.get('duration'),
                "moving_duration_seconds": summary.get('movingDuration'),
                "elapsed_duration_seconds": summary.get('elapsedDuration'),

                # Distance and speed
                "distance_meters": summary.get('distance'),
                "avg_speed_mps": summary.get('averageSpeed'),
                "max_speed_mps": summary.get('maxSpeed'),

                # Heart rate
                "avg_hr_bpm": summary.get('averageHR'),
                "max_hr_bpm": summary.get('maxHR'),
                "min_hr_bpm": summary.get('minHR'),

                # Calories
                "calories": summary.get('calories'),
                "bmr_calories": summary.get('bmrCalories'),

                # Running metrics
                "avg_cadence": summary.get('averageRunCadence'),
                "max_cadence": summary.get('maxRunCadence'),
                "avg_stride_length_cm": summary.get('strideLength'),
                "avg_ground_contact_time_ms": summary.get('groundContactTime'),
                "avg_vertical_oscillation_cm": summary.get('verticalOscillation'),
                **_balance_metrics(summary),
                "steps": summary.get('steps'),

                # Elevation
                "elevation_gain_meters": summary.get('elevationGain'),
                "elevation_loss_meters": summary.get('elevationLoss'),
                "max_elevation_meters": summary.get('maxElevation'),
                "min_elevation_meters": summary.get('minElevation'),

                # Power
                "avg_power_watts": summary.get('averagePower'),
                "max_power_watts": summary.get('maxPower'),
                "normalized_power_watts": summary.get('normalizedPower'),

                # Training effect
                "training_effect": summary.get('trainingEffect'),
                "anaerobic_training_effect": summary.get('anaerobicTrainingEffect'),
                "training_effect_label": summary.get('trainingEffectLabel'),
                "training_load": summary.get('activityTrainingLoad'),

                # Intensity minutes
                "moderate_intensity_minutes": summary.get('moderateIntensityMinutes'),
                "vigorous_intensity_minutes": summary.get('vigorousIntensityMinutes'),

                # Recovery
                "recovery_hr_bpm": summary.get('recoveryHeartRate'),
                "body_battery_impact": summary.get('differenceBodyBattery'),

                # Workout feedback
                "workout_feel": summary.get('directWorkoutFeel'),
                "workout_rpe": summary.get('directWorkoutRpe'),

                # Metadata
                "lap_count": metadata.get('lapCount'),
                "has_splits": metadata.get('hasSplits'),
                "device_manufacturer": metadata.get('manufacturer'),
            }

            # Remove None values
            curated = {k: v for k, v in curated.items() if v is not None}

            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error retrieving activity: {str(e)}"

    @app.tool()
    async def get_activity_splits(activity_id: int) -> str:
        """Get splits for an activity

        Args:
            activity_id: ID of the activity to retrieve splits for
        """
        try:
            splits = garmin_client.get_activity_splits(activity_id)
            if not splits:
                return f"No splits found for activity with ID {activity_id}"

            # Curate the splits data
            laps = splits.get('lapDTOs', [])

            curated = {
                "activity_id": splits.get('activityId'),
                "lap_count": len(laps),
                "laps": []
            }

            for lap in laps:
                lap_data = {
                    "lap_number": lap.get('lapIndex'),
                    "start_time": lap.get('startTimeGMT'),
                    "distance_meters": lap.get('distance'),
                    "duration_seconds": lap.get('duration'),
                    "avg_speed_mps": lap.get('averageSpeed'),
                    "max_speed_mps": lap.get('maxSpeed'),
                    "avg_hr_bpm": lap.get('averageHR'),
                    "max_hr_bpm": lap.get('maxHR'),
                    "calories": lap.get('calories'),
                    "avg_cadence": lap.get('averageRunCadence'),
                    "avg_power_watts": lap.get('averagePower'),
                    "intensity_type": lap.get('intensityType'),
                }
                # Remove None values
                lap_data = {k: v for k, v in lap_data.items() if v is not None}
                curated["laps"].append(lap_data)

            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error retrieving activity splits: {str(e)}"

    @app.tool()
    async def get_activity_typed_splits(activity_id: int) -> str:
        """Get typed splits for an activity

        Args:
            activity_id: ID of the activity to retrieve typed splits for
        """
        try:
            typed_splits = garmin_client.get_activity_typed_splits(activity_id)
            if not typed_splits:
                return f"No typed splits found for activity with ID {activity_id}"

            return json.dumps(typed_splits, indent=2)
        except Exception as e:
            return f"Error retrieving activity typed splits: {str(e)}"

    @app.tool()
    async def get_activity_split_summaries(activity_id: int) -> str:
        """Get split summaries for an activity

        Args:
            activity_id: ID of the activity to retrieve split summaries for
        """
        try:
            split_summaries = garmin_client.get_activity_split_summaries(activity_id)
            if not split_summaries:
                return f"No split summaries found for activity with ID {activity_id}"

            return json.dumps(split_summaries, indent=2)
        except Exception as e:
            return f"Error retrieving activity split summaries: {str(e)}"

    @app.tool()
    async def get_activity_weather(activity_id: int) -> str:
        """Get weather data for an activity.

        Garmin's weather endpoint returns temperatures in Fahrenheit (from the
        weather-station source) with no unit indicator, regardless of account
        settings. This tool converts them to the account's display unit: metric
        accounts get Celsius, statute_us accounts keep Fahrenheit. The
        temperature_unit field ("F" or "C") states which unit was returned.

        Wind speed, unlike temperature, is already returned in the account's
        display unit (km/h for metric, mph for statute_us), so it is passed
        through unconverted and labeled via the wind_speed_unit field.

        Args:
            activity_id: ID of the activity to retrieve weather data for
        """
        try:
            weather = garmin_client.get_activity_weather(activity_id)
            if not weather:
                return f"No weather data found for activity with ID {activity_id}"

            # Garmin's activity-weather endpoint returns temperatures in
            # FAHRENHEIT (from the METAR/station source), regardless of the
            # account's measurement system — the payload carries no unit field.
            # (Confirmed: a metric account still gets °F here, e.g. temp 57.)
            # So convert the raw Fahrenheit values to the account's display unit.
            def _f_to_c(value):
                return round((value - 32) * 5 / 9, 1) if value is not None else None

            try:
                unit_system = garmin_client.get_unit_system()
            except Exception:
                unit_system = None

            raw_temp = weather.get('temp')
            raw_apparent = weather.get('apparentTemp')
            raw_dew = weather.get('dewPoint')

            if unit_system is not None and unit_system != "statute_us":
                # Metric (or non-US-statute) account → present in Celsius.
                temp_unit = "C"
                out_temp, out_apparent, out_dew = (
                    _f_to_c(raw_temp), _f_to_c(raw_apparent), _f_to_c(raw_dew)
                )
            else:
                # statute_us account (or unknown) → leave the raw Fahrenheit.
                temp_unit = "F" if unit_system == "statute_us" else None
                out_temp, out_apparent, out_dew = raw_temp, raw_apparent, raw_dew

            # Wind, unlike temperature, IS already returned in the account's
            # display unit (verified against a local weather station: metric
            # accounts get km/h, not mph). So don't convert it — just label it.
            wind_unit = "mph" if unit_system == "statute_us" else (
                "km/h" if unit_system is not None else None
            )

            weather_type_dto = weather.get('weatherTypeDTO') or {}
            station_dto = weather.get('weatherStationDTO') or {}

            curated = {
                "activity_id": activity_id,
                "temperature": out_temp,
                "temperature_unit": temp_unit,
                "apparent_temperature": out_apparent,
                "dew_point": out_dew,
                "humidity_percent": weather.get('relativeHumidity'),
                "wind_speed": weather.get('windSpeed'),
                "wind_speed_unit": wind_unit,
                "wind_direction_degrees": weather.get('windDirection'),
                "wind_direction_compass": weather.get('windDirectionCompassPoint'),
                "wind_gust": weather.get('windGust'),
                "weather_type": weather_type_dto.get('weatherTypeName'),
                "weather_description": weather_type_dto.get('desc') or weather_type_dto.get('weatherTypeDesc'),
                "location": weather.get('issueLocation'),
                "station_id": station_dto.get('id'),
                "station_name": station_dto.get('name'),
                "issue_time": weather.get('issueDate'),
            }

            # Remove None values
            curated = {k: v for k, v in curated.items() if v is not None}

            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error retrieving activity weather data: {str(e)}"

    @app.tool()
    async def get_activity_hr_in_timezones(activity_id: int) -> str:
        """Get heart rate data in different time zones for an activity

        Args:
            activity_id: ID of the activity to retrieve heart rate time zone data for
        """
        try:
            hr_zones = garmin_client.get_activity_hr_in_timezones(activity_id)
            if not hr_zones:
                return f"No heart rate time zone data found for activity with ID {activity_id}"

            return json.dumps(hr_zones, indent=2)
        except Exception as e:
            return f"Error retrieving activity heart rate time zone data: {str(e)}"

    @app.tool()
    async def get_activity_gear(activity_id: int) -> str:
        """Get gear data used for an activity

        Args:
            activity_id: ID of the activity to retrieve gear data for
        """
        try:
            gear = garmin_client.get_activity_gear(activity_id)
            if not gear:
                return f"No gear data found for activity with ID {activity_id}"

            return json.dumps(gear, indent=2)
        except Exception as e:
            return f"Error retrieving activity gear data: {str(e)}"

    @app.tool()
    async def get_activity_exercise_sets(activity_id: int) -> str:
        """Get exercise sets for strength training activities

        Args:
            activity_id: ID of the activity to retrieve exercise sets for
        """
        try:
            exercise_sets = garmin_client.get_activity_exercise_sets(activity_id)
            if not exercise_sets:
                return f"No exercise sets found for activity with ID {activity_id}"

            return json.dumps(exercise_sets, indent=2)
        except Exception as e:
            return f"Error retrieving activity exercise sets: {str(e)}"

    @app.tool()
    async def count_activities() -> str:
        """Get total count of activities in the user's Garmin account

        Returns the total number of activities recorded.
        """
        try:
            count = garmin_client.count_activities()
            if count is None:
                return "Unable to retrieve activity count"

            return json.dumps({
                "total_activities": count,
                "note": "Use get_activities() with pagination to retrieve activity details"
            }, indent=2)
        except Exception as e:
            return f"Error counting activities: {str(e)}"

    @app.tool()
    async def get_activities(start: int = 0, limit: int = 20) -> str:
        """Get activities with pagination support

        Retrieves a paginated list of activities. Use this for browsing through
        large activity lists more efficiently than get_activities_by_date.

        Args:
            start: Starting index (default 0, activities are ordered newest first)
            limit: Maximum number of activities to return (default 20, max 100)
        """
        try:
            # Cap limit at 100 for safety and performance
            limit = min(max(1, limit), 100)

            activities = garmin_client.get_activities(start, limit)
            if not activities:
                return f"No activities found at index {start}"

            # Curate the activity list
            curated = {
                "start": start,
                "limit": limit,
                "count": len(activities),
                "has_more": len(activities) == limit,
                "next_start": start + limit if len(activities) == limit else None,
                "activities": []
            }

            for a in activities:
                activity = {
                    "id": a.get('activityId'),
                    "name": a.get('activityName'),
                    "type": a.get('activityType', {}).get('typeKey'),
                    "start_time": a.get('startTimeLocal'),
                    "distance_meters": a.get('distance'),
                    "duration_seconds": a.get('duration'),
                    "moving_duration_seconds": a.get('movingDuration'),
                    "calories": a.get('calories'),
                    "avg_hr_bpm": a.get('averageHR'),
                    "max_hr_bpm": a.get('maxHR'),
                    "steps": a.get('steps'),
                    "elevation_gain_meters": a.get('elevationGain'),
                    "elevation_loss_meters": a.get('elevationLoss'),
                    **_balance_metrics(a),
                    "owner_display_name": a.get('ownerDisplayName'),
                }
                curated["activities"].append(activity)

            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error retrieving activities: {str(e)}"

    @app.tool()
    async def get_activity_types() -> str:
        """Get all available activity types

        Returns a list of all activity types supported by Garmin Connect,
        useful for filtering activities by type.
        """
        try:
            activity_types = garmin_client.get_activity_types()
            if not activity_types:
                return "No activity types found"

            # Curate the activity types list
            curated = {
                "count": len(activity_types),
                "activity_types": []
            }

            for at in activity_types:
                activity_type = {
                    "type_id": at.get('typeId'),
                    "type_key": at.get('typeKey'),
                    "display_name": at.get('displayName'),
                    "parent_type_id": at.get('parentTypeId'),
                    "is_hidden": at.get('isHidden'),
                }
                # Remove None values
                activity_type = {k: v for k, v in activity_type.items() if v is not None}
                curated["activity_types"].append(activity_type)

            return json.dumps(curated, indent=2)
        except Exception as e:
            return f"Error retrieving activity types: {str(e)}"

    return app
