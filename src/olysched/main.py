import requests
from datetime import datetime
import pytz
from dateutil import parser
from collections import defaultdict
import re
import json

COMMON_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
MEDAL_EMOJI = "🏅"


def fetch_olympic_schedule(date):
    base_url = "https://sph-s-api.olympics.com/summer/schedules/api/ENG/schedule/day/"
    url = f"{base_url}{date}"

    headers = {"User-Agent": COMMON_USER_AGENT}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # with open("response.json", "w") as f:
        #     json.dump(data, f)

        return data
    except requests.RequestException as e:
        print(f"An error occurred while fetching data: {e}")
        return None


def convert_to_aest(time_str):
    dt = parser.parse(time_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    aest = pytz.timezone("Australia/Sydney")
    return dt.astimezone(aest)


def format_name(name):
    def capitalize_name(n):
        parts = n.split()
        formatted_parts = []
        for part in parts:
            if part.lower() in ["von", "van", "de", "du", "la", "le"]:
                formatted_parts.append(part.lower())
            elif "-" in part:
                formatted_parts.append(
                    "-".join(word.capitalize() for word in part.split("-"))
                )
            else:
                formatted_parts.append(part.capitalize())
        return " ".join(formatted_parts)

    if "/" in name:
        names = name.split("/")
        return " / ".join(capitalize_name(n.strip()) for n in names)
    else:
        return capitalize_name(name)


def group_events(events):
    grouped_events = defaultdict(list)
    for event in events:
        key = (
            event["disciplineName"],
            re.sub(r" - Race \d+", "", event["eventUnitName"]),
        )
        grouped_events[key].append(event)
    return grouped_events


def format_schedule(schedule_data):
    if not schedule_data or "units" not in schedule_data:
        return "No schedule data available."

    formatted_schedule = (
        "# 🇦🇺 Olympic Events\n\n"
    )

    # Group events
    australian_events = [
            event
            for event in schedule_data.get("units", [])
            if any(comp.get("noc") == "AUS" for comp in event.get("competitors", []))
        ]
    grouped_events = group_events(australian_events)

    for (discipline, event_name), events in grouped_events.items():
        australian_competitors = [
            comp
            for event in events
            for comp in event.get("competitors", [])
            if comp.get("noc") == "AUS"
        ]
        australian_events = [
            event
            for event in events
            if any(comp.get("noc") == "AUS" for comp in event.get("competitors", []))
        ]

        if not australian_competitors:
            continue  # Skip events without Australian competitors

        start_time_aest = convert_to_aest(events[0].get("startDate", ""))

        medal_event = any(event.get("medalFlag") == 1 for event in events)
        event_title = f"{discipline}: {event_name}"
        if medal_event:
            event_title = f"{MEDAL_EMOJI} {event_title}"

        if len(australian_events) > 1:
            end_time_aest = convert_to_aest(events[-1].get("startDate", ""))
            formatted_schedule += f"### {start_time_aest.strftime('%Y-%m-%d %H:%M')} - {end_time_aest.strftime('%H:%M')} - {event_title}\n"
            race_numbers = [
                re.search(r"Race (\d+)", event["eventUnitName"]).group(1)
                for event in events
                if re.search(r"Race (\d+)", event["eventUnitName"])
            ]
            formatted_schedule += f"#### Races: {', '.join(race_numbers)}\n"
        else:
            formatted_schedule += f"### {start_time_aest.strftime('%Y-%m-%d %H:%M')} - {event_title}\n"

        if (
            len(australian_competitors) == 1
            and len(events[0].get("competitors", [])) == 2
        ):
            # One-on-one match
            aus_comp = australian_competitors[0]
            opponent = next(
                comp
                for comp in events[0].get("competitors", [])
                if comp.get("noc") != "AUS"
            )
            aus_name = format_name(aus_comp.get("name", "Unknown"))
            opp_name = format_name(opponent.get("name", "Unknown"))
            opp_country = opponent.get("noc", "???")
            if aus_name == "Australia":
                formatted_schedule += f"* AUS vs {opp_country}\n"
            else:
                formatted_schedule += (
                    f"* {aus_name} (AUS) vs {opp_name} ({opp_country})\n"
                )
        else:
            # Multi-competitor event
            for competitor in set(comp["name"] for comp in australian_competitors):
                formatted_schedule += f"* {format_name(competitor)}\n"

        formatted_schedule += "\n"

    return formatted_schedule


def main():
    today = datetime.now(pytz.timezone("Australia/Sydney")).date()
    schedule_data = fetch_olympic_schedule(today.isoformat())

    if schedule_data:
        schedule = format_schedule(schedule_data)
        print(schedule)

        with open("index.md", "w", encoding="utf-8") as f:
            f.write(schedule)
        # print("Schedule has been saved to australian_olympic_schedule.md")
    else:
        print("Failed to fetch the schedule.")


if __name__ == "__main__":
    main()
