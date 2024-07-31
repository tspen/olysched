import json
import re
from collections import defaultdict
from datetime import datetime
from typing import List, Optional

import pytz
import requests
from dateutil import parser
from pydantic import BaseModel, Field, model_validator

COMMON_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
MEDAL_EMOJI = "🏅"


# Pydantic models
class CompetitorResult(BaseModel):
    position: str = ""
    mark: str = ""
    medalType: str = ""
    irm: str = ""
    penalty: Optional[str] = None


class Competitor(BaseModel):
    code: str
    noc: str
    name: str
    order: int
    results: Optional[CompetitorResult] = None


class ExtraData(BaseModel):
    detailUrl: Optional[str] = None


class EventUnit(BaseModel):
    disciplineName: str
    eventUnitName: str
    id: str
    disciplineCode: str
    genderCode: str
    eventCode: str
    phaseCode: str
    eventId: str
    eventName: str
    phaseId: str
    phaseName: str
    disciplineId: str
    eventOrder: int
    phaseType: str
    eventUnitType: str
    olympicDay: str
    startDate: datetime
    endDate: datetime
    hideStartDate: bool
    hideEndDate: bool
    startText: str
    order: int
    venue: str
    venueDescription: str
    location: str
    locationDescription: str
    status: str
    statusDescription: str
    medalFlag: int
    liveFlag: bool
    scheduleItemType: str
    unitNum: str
    sessionCode: str
    groupId: Optional[str] = None
    competitors: List[Competitor] = Field(default_factory=list)
    extraData: ExtraData

    @model_validator(mode='before')
    @classmethod
    def filter_competitors(cls, values):
        if "competitors" in values:
            values["competitors"] = [
                comp
                for comp in values["competitors"]
                if comp.get("code") != "TBD" and comp.get("name") != "TBD"
            ]
        return values


class OlympicSchedule(BaseModel):
    units: List[EventUnit]

    @classmethod
    def fetch_olympic_schedule(cls, date):
        base_url = "https://sph-s-api.olympics.com/summer/schedules/api/ENG/schedule/day/"
        url = f"{base_url}{date}"

        headers = {"User-Agent": COMMON_USER_AGENT}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            with open("response.json", "w") as f:
                json.dump(response.json(), f)

            schedule_data = response.json()
            return cls(**schedule_data)
        except requests.RequestException as e:
            print(f"An error occurred while fetching data: {e}")
            return None

    def format_schedule(self, today):
        if not self.units:
            return "No schedule data available."

        formatted_schedule = f"# 🇦🇺 Olympic Events\n\n## {today.strftime('%-d %B')}\n\n"

        australian_events = [
            event for event in self.units
            if any(comp.noc == "AUS" for comp in event.competitors)
        ]
        grouped_events = group_events(australian_events)

        for (discipline, event_name), events in grouped_events.items():
            australian_competitors = [
                comp for event in events for comp in event.competitors if comp.noc == "AUS"
            ]
            australian_events = [
                event for event in events
                if any(comp.noc == "AUS" for comp in event.competitors)
            ]

            if not australian_competitors:
                continue

            start_time_aest = convert_to_aest(str(events[0].startDate))

            medal_event = any(event.medalFlag == 1 for event in events)
            event_title = f"{discipline}: {event_name}"
            if medal_event:
                event_title = f"{MEDAL_EMOJI} {event_title}"

            if len(australian_events) > 1:
                end_time_aest = convert_to_aest(str(events[-1].startDate))
                formatted_schedule += f"### {start_time_aest.strftime('%H:%M')} - {end_time_aest.strftime('%H:%M')} - {event_title}\n"
                race_numbers = [
                    re.search(r"Race (\d+)", event.eventUnitName).group(1)
                    for event in events
                    if re.search(r"Race (\d+)", event.eventUnitName)
                ]
                formatted_schedule += f"#### Races: {', '.join(race_numbers)}\n"
            else:
                formatted_schedule += f"### {start_time_aest.strftime('%H:%M')} - {event_title}\n"

            if len(australian_competitors) == 1 and len(events[0].competitors) == 2:
                aus_comp = australian_competitors[0]
                opponent = next(comp for comp in events[0].competitors if comp.noc != "AUS")
                aus_name = format_name(aus_comp.name)
                opp_name = format_name(opponent.name)
                opp_country = opponent.noc
                if aus_name == "Australia":
                    formatted_schedule += f"* AUS vs {opp_country}\n"
                else:
                    formatted_schedule += f"* {aus_name} (AUS) vs {opp_name} ({opp_country})\n"
            else:
                for competitor in sorted(set(comp.name for comp in australian_competitors)):
                    formatted_schedule += f"* {format_name(competitor)}\n"

            formatted_schedule += "\n"

        return formatted_schedule


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
            event.disciplineName,
            re.sub(r" - Race \d+", "", event.eventUnitName),
        )
        grouped_events[key].append(event)
    return grouped_events


def main():
    today = datetime.now(pytz.timezone("Australia/Sydney")).date()
    schedule = OlympicSchedule.fetch_olympic_schedule(today.isoformat())

    if schedule:
        formatted_schedule = schedule.format_schedule(today)
        print(formatted_schedule)

        with open("index.md", "w", encoding="utf-8") as f:
            f.write(formatted_schedule)
    else:
        print("Failed to fetch the schedule.")


if __name__ == "__main__":
    main()